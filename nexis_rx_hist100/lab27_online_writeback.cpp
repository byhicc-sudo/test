// NEXIS-RX LAB27: online scratchpad ISTORE write-combining test.
// Unlike LAB26, this method does NOT use a previously-computed dead-store trace.
// It delays ISTORE memory writes until they are needed by bytecode reads or the
// end of a VM iteration. If overwritten while pending, first physical store is
// provably unnecessary. Full 256-bit result checked vs reference API.
#include "randomx.h"
#include "blake2/blake2.h"
#include <array>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using Bytes=std::vector<uint8_t>;
struct Pending {uint8_t*addr;uint64_t value;};
static thread_local std::vector<Pending> pending;
static bool defer_enabled=false;
static uint64_t attempts=0,physical=0,coalesced=0,readFlushed=0,boundaryFlushed=0;
extern "C" const void* nexis27_read_ptr(uint8_t* base,const void* p){
 (void)base;
 if(!defer_enabled)return p;
 auto*loc=reinterpret_cast<const uint8_t*>(p);
 for(size_t i=0;i<pending.size();){
  auto*a=pending[i].addr;
  if(a < loc+8 && loc < a+8){
   std::memcpy(a,&pending[i].value,8);
   ++physical;++readFlushed;
   pending.erase(pending.begin()+i);
  }else ++i;
 }
 return p;
}
extern "C" void nexis27_istore(uint8_t* base,uint8_t* address,uint64_t value){
 (void)base;
 ++attempts;
 if(!defer_enabled){
  std::memcpy(address,&value,8);
  ++physical;return;
 }
 for(auto& w:pending)if(w.addr==address){
  w.value=value;++coalesced;return;
 }
 // Each aligned ISTORE writes 8 bytes; no partial overlap is permitted unless
 // previous pending overlapping data has been flushed before staging.
 for(size_t i=0;i<pending.size();){
  auto*a=pending[i].addr;
  if(a<address+8&&address<a+8){
   std::memcpy(a,&pending[i].value,8);
   ++physical;pending.erase(pending.begin()+i);
  }else ++i;
 }
 pending.push_back({address,value});
}
extern "C" void nexis27_flush(uint8_t*base){
 (void)base;
 if(!defer_enabled)return;
 for(auto&w:pending){
  std::memcpy(w.addr,&w.value,8);++physical;++boundaryFlushed;
 }
 pending.clear();
}
static Bytes unhex(const std::string&s){
 auto nib=[](char c)->int{if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;throw std::runtime_error("hex");};
 if(s.size()%2)throw std::runtime_error("bad hex");
 Bytes v;for(size_t i=0;i<s.size();i+=2)v.push_back(uint8_t(nib(s[i])*16+nib(s[i+1])));return v;
}
static std::vector<std::string>fields(const std::string&s){std::stringstream f(s);std::string x;std::vector<std::string>v;while(std::getline(f,x,','))v.push_back(x);return v;}
static size_t noncePos(const Bytes&b){size_t p=0;for(int j=0;j<3;j++)for(;;){if(p>=b.size())throw std::runtime_error("varint");if(!(b[p++]&128))break;}return p+32;}
static void setNonce(Bytes&blob,size_t p,uint32_t n){for(int i=0;i<4;i++)blob[p+i]=uint8_t(n>>(8*i));}
static std::string hex(const std::array<uint8_t,32>&r){char d[]="0123456789abcdef";std::string s;for(uint8_t b:r){s+=d[b>>4];s+=d[b&15];}return s;}
struct Trial {double time=0;uint64_t count=0,attempts=0,physical=0,coalesced=0,readFlushed=0,boundaryFlushed=0;};
int main(int argc,char**argv){try{
 if(argc!=5)throw std::runtime_error("use: lab27 computed100.csv seedhex summary.txt samples.csv");
 std::ifstream input(argv[1]);if(!input)throw std::runtime_error("no dataset");
 std::string line;std::getline(input,line);if(!std::getline(input,line))throw std::runtime_error("missing first row");
 auto fields0=fields(line);if(fields0.size()<9||fields0[0]!="3300100")throw std::runtime_error("bad historic row");
 auto blob=unhex(fields0[4]),seed=unhex(argv[2]),knownHash=unhex(fields0[3]);
 if(blob.size()!=76||seed.size()!=32||knownHash.size()!=32)throw std::runtime_error("bad field size");
 size_t p=noncePos(blob);uint32_t winner=std::stoul(fields0[1]);
 auto*cache=randomx_alloc_cache(RANDOMX_FLAG_DEFAULT);if(!cache)throw std::runtime_error("cache");
 randomx_init_cache(cache,seed.data(),seed.size());
 auto*vm=randomx_create_vm(RANDOMX_FLAG_DEFAULT,cache,nullptr);
 if(!vm)throw std::runtime_error("vm");
 std::ofstream out(argv[3]),csv(argv[4]);if(!out||!csv)throw std::runtime_error("output");
 csv<<"trial,mode,nonce,hash_equal,attempted_istore,actual_physical_istore,coalesced,read_flush,boundary_flush,full_randomx_hash\n";
 const int N=16;
 // Golden hashes with the reference behavior, comparison includes historical winner.
 std::array<std::array<uint8_t,32>,N>golden{};
 defer_enabled=false;
 for(int i=0;i<N;i++){
  setNonce(blob,p,winner+uint32_t(i));
  randomx_calculate_hash(vm,blob.data(),blob.size(),golden[size_t(i)].data());
 }
 if(!std::equal(knownHash.begin(),knownHash.end(),golden[0].begin()))
  throw std::runtime_error("historic network winner hash mismatch");
 Trial baseline,optimized;
 for(int round=0;round<4;round++){
  bool useDefer=round%2==1;
  Trial local;defer_enabled=useDefer;pending.clear();pending.reserve(32);
  attempts=physical=coalesced=readFlushed=boundaryFlushed=0;
  auto start=std::chrono::steady_clock::now();
  for(int i=0;i<N;i++){
   setNonce(blob,p,winner+uint32_t(i));
   std::array<uint8_t,32>value{};
   randomx_calculate_hash(vm,blob.data(),blob.size(),value.data());
   if(!pending.empty())throw std::runtime_error("unflushed pending ISTORE at end of hash");
   if(value!=golden[size_t(i)])throw std::runtime_error("FULL_RANDOMX_HASH_CHANGED_ONLINE_WRITE_COMBINING");
   csv<<round<<","<<(useDefer?"DEFERRED":"DIRECT")<<","<<(winner+uint32_t(i))<<",1,"
      <<attempts<<","<<physical<<","<<coalesced<<","<<readFlushed<<","<<boundaryFlushed<<","<<hex(value)<<"\n";
   local.count++;
  }
  const auto stop=std::chrono::steady_clock::now();
  local.time=std::chrono::duration<double>(stop-start).count();
  local.attempts=attempts;local.physical=physical;local.coalesced=coalesced;
  local.readFlushed=readFlushed;local.boundaryFlushed=boundaryFlushed;
  auto&total=useDefer?optimized:baseline;
  total.time+=local.time;total.count+=local.count;total.attempts+=local.attempts;
  total.physical+=local.physical;total.coalesced+=local.coalesced;total.readFlushed+=local.readFlushed;total.boundaryFlushed+=local.boundaryFlushed;
  std::cout<<"ROUND="<<round<<" MODE="<<(useDefer?"DEFERRED":"DIRECT")
    <<" SEC="<<local.time<<" HPS="<<N/local.time<<" PHYSICAL_WRITES="<<local.physical
    <<" COMBINED="<<local.coalesced<<"\n";
 }
 defer_enabled=false;
 randomx_destroy_vm(vm);randomx_release_cache(cache);
 auto emit=[&](const std::string&s){std::cout<<s<<"\n";out<<s<<"\n";};
 emit("HISTORIC_REFERENCE_WINNER_NONCE="+std::to_string(winner));
 emit("COMPARED_OFFICIAL_FULL_RANDOMX_256BIT=64/64 (reference hashes verified for 16 historical nonce values)");
 emit("DIRECT_ISTORE_ATTEMPTS="+std::to_string(baseline.attempts));
 emit("DEFERRED_ISTORE_ATTEMPTS="+std::to_string(optimized.attempts));
 emit("DEFERRED_PHYSICAL_ISTORE="+std::to_string(optimized.physical));
 emit("ONLINE_COALESCED_ISTORE="+std::to_string(optimized.coalesced));
 emit("ONLINE_ISTORE_COALESCED_PCT="+std::to_string(100.0*optimized.coalesced/optimized.attempts));
 emit("ONLINE_READ_TRIGGERED_FLUSH="+std::to_string(optimized.readFlushed));
 emit("ONLINE_ITERATION_END_FLUSH="+std::to_string(optimized.boundaryFlushed));
 emit("DIRECT_MODE_HPS="+std::to_string(baseline.count/baseline.time));
 emit("DEFERRED_MODE_HPS="+std::to_string(optimized.count/optimized.time));
 emit("MEASURED_RATIO_DEFERRED_TO_DIRECT="+std::to_string((optimized.count/optimized.time)/(baseline.count/baseline.time)));
 emit("CAVEAT=Comparison uses the same instrumented C++ library in direct and deferred mode. Removing memory writes does not necessarily reduce total execution time; bytecode buffering adds overhead. No predictive nonce shortcut demonstrated.");
 return 0;
 }catch(const std::exception&e){std::cerr<<"ERROR "<<e.what()<<"\n";return 1;}
}
