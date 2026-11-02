// NEXIS-RX LAB26 — exact byte-granularity scratchpad dead-store tracking.
// Same authentic 76-byte historic Monero job. Fixed official RandomX light VM.
// Traces every VM scratchpad read and write (including bytecode memory ops).
// A write may be suppressed only if ALL written bytes were overwritten before
// being read and all final scratchpad bytes counted as read. Blind rerun tests
// must yield identical official 256-bit PoW hash.
#include "randomx.h"
#include "virtual_machine.hpp"
#include "blake2/blake2.h"
#include "configuration.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using Bytes=std::vector<uint8_t>;
namespace {
constexpr unsigned ScratchBytes=2097152;
enum Mode {OFF,TRACE,REPLAY};
Mode g_mode=OFF;
const uint8_t* g_base=nullptr;
std::vector<uint32_t> g_owner;
std::vector<uint32_t> g_left;
std::vector<uint8_t> g_seen;
std::vector<uint8_t> g_skip;
uint64_t g_reads=0,g_readBytes=0,g_writes=0,g_writeBytes=0,g_retired=0,g_skipped=0,g_skippedBytes=0;
bool g_violation=false;
uint32_t g_seq=0;
void reset(const uint8_t*base,Mode mode) {
 g_base=base;g_mode=mode;g_seq=0;g_reads=0;g_readBytes=0;g_writes=0;
 g_writeBytes=0;g_retired=0;g_skipped=0;g_skippedBytes=0;g_violation=false;
 if(mode==TRACE){
  g_owner.assign(ScratchBytes,0);
  g_left.assign(1,0);g_seen.assign(1,0);g_skip.clear();
 }
}
void finalReads(){
 if(g_mode!=TRACE)throw std::runtime_error("finalRead in non-trace");
 // Official RandomX getFinalResult hashes the entire 2MiB scratchpad.
 for(auto id:g_owner)if(id)g_seen[id]=1;
}
std::string tohex(const uint8_t*p,size_t n){
 const char*s="0123456789abcdef";std::string out;out.reserve(n*2);
 for(size_t i=0;i<n;i++){out+=s[p[i]>>4];out+=s[p[i]&15];}return out;
}
Bytes unhex(const std::string&s){
 auto digit=[](char c)->int{if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;throw std::runtime_error("nonhex");};
 if(s.size()%2)throw std::runtime_error("hex size");
 Bytes b;for(size_t i=0;i<s.size();i+=2)b.push_back(uint8_t(digit(s[i])*16+digit(s[i+1])));return b;
}
std::vector<std::string> fields(const std::string&s){
 std::istringstream f(s);std::string x;std::vector<std::string>v;while(std::getline(f,x,','))v.push_back(x);return v;
}
size_t nonceOffset(const Bytes&b){
 size_t p=0;for(int v=0;v<3;v++)for(;;){
  if(p>=b.size())throw std::runtime_error("invalid varint");
  if(!(b[p++]&128))break;
 }
 p+=32;if(p+4>b.size())throw std::runtime_error("bad nonce offset");return p;
}
void setNonce(Bytes&b,size_t off,uint32_t nonce){
 for(unsigned i=0;i<4;i++)b[off+i]=uint8_t(nonce>>(8*i));
}
}
extern "C" const void* nexis26_read_ptr(const uint8_t*base,const void* addr,unsigned len){
 if(g_mode==OFF)return addr;
 if(g_mode==REPLAY)return addr; // audit read log from first run is authoritative
 if(base!=g_base){g_violation=true;return addr;}
 auto p=reinterpret_cast<const uint8_t*>(addr);
 auto off=p-base;
 if(off<0||unsigned(off)+len>ScratchBytes)throw std::runtime_error("read bounds");
 ++g_reads;g_readBytes+=len;
 for(unsigned i=0;i<len;i++) {
  uint32_t id=g_owner[size_t(off)+i];
  if(id)g_seen[id]=1;
 }
 return addr;
}
extern "C" bool nexis26_before_write(const uint8_t*base,const void*addr,unsigned len){
 if(g_mode==OFF)return true;
 if(base!=g_base){g_violation=true;return true;}
 auto p=reinterpret_cast<const uint8_t*>(addr);auto off=p-base;
 if(off<0||unsigned(off)+len>ScratchBytes)throw std::runtime_error("write bounds");
 ++g_seq;++g_writes;g_writeBytes+=len;
 if(g_mode==REPLAY){
  if(g_seq>=g_skip.size())throw std::runtime_error("replay event count diverged");
  if(g_skip[g_seq]){++g_skipped;g_skippedBytes+=len;return false;}
  return true;
 }
 g_seen.push_back(0);g_left.push_back(len);
 for(unsigned i=0;i<len;i++){
  auto idx=size_t(off)+i;
  uint32_t prior=g_owner[idx];
  if(prior){if(g_left[prior]==0)throw std::runtime_error("prior writer invalid");g_left[prior]--;}
  g_owner[idx]=g_seq;
 }
 return true;
}
int main(int argc,char**argv){try{
 if(argc!=5)throw std::runtime_error("usage lab26 computed100.csv seedhex summary.txt samples.csv");
 std::ifstream data(argv[1]);if(!data)throw std::runtime_error("missing historic input");
 std::string line;std::getline(data,line);if(!std::getline(data,line))throw std::runtime_error("no historic block");
 auto row=fields(line);if(row.size()<9||row[0]!="3300100")throw std::runtime_error("unexpected historic block");
 auto input=unhex(row[4]), expected=unhex(row[3]), seed=unhex(argv[2]);
 if(input.size()!=76||seed.size()!=32||expected.size()!=32)throw std::runtime_error("bad inputs");
 const uint32_t winningNonce=uint32_t(std::stoul(row[1]));
 size_t np=nonceOffset(input);
 auto*cache=randomx_alloc_cache(RANDOMX_FLAG_DEFAULT);if(!cache)throw std::runtime_error("cache");
 randomx_init_cache(cache,seed.data(),seed.size());
 auto*vm=randomx_create_vm(RANDOMX_FLAG_DEFAULT,cache,nullptr);if(!vm)throw std::runtime_error("vm");
 std::ofstream summary(argv[3]),csv(argv[4]);if(!summary||!csv)throw std::runtime_error("output");
 csv<<"sample,nonce,reference_valid,vm_matches_official,write_events,unread_fully_overwritten_writes,write_bytes,dead_write_bytes,skipped_write_events,replayed_hash_matches_reference,trace_read_events,trace_read_bytes\n";
 uint64_t sumWrites=0,sumDead=0,sumBytes=0,sumDeadBytes=0,sumSkipped=0,eq=0;
 const unsigned numberSamples=2;
 for(unsigned sample=0;sample<numberSamples;sample++){
  const uint32_t nonce=winningNonce+sample;
  setNonce(input,np,nonce);
  std::array<uint8_t,32>reference{};
  g_mode=OFF;randomx_calculate_hash(vm,input.data(),input.size(),reference.data());
  if(sample==0&&!std::equal(reference.begin(),reference.end(),expected.begin()))
   throw std::runtime_error("historical winning block official RandomX mismatch");
  auto sequence=[&](Mode mode)->std::array<uint8_t,32>{
   alignas(16) uint64_t temp[8];
   if(blake2b(temp,sizeof(temp),input.data(),input.size(),nullptr,0))throw std::runtime_error("initial hash");
   vm->initScratchpad(temp);
   vm->resetRoundingMode();
   reset(static_cast<const uint8_t*>(vm->getScratchpad()),mode);
   for(int phase=0;phase<RANDOMX_PROGRAM_COUNT;phase++){
    vm->run(temp);
    if(phase+1<RANDOMX_PROGRAM_COUNT){
     if(blake2b(temp,sizeof(temp),vm->getRegisterFile(),sizeof(randomx::RegisterFile),nullptr,0))
      throw std::runtime_error("chain hash");
    }
   }
   if(mode==TRACE)finalReads();
   if(g_violation)throw std::runtime_error("instrumentation base mismatch");
   // Prevent AES final reduction from recording uninstrumented accesses:
   // all bytes already marked read before this line.
   g_mode=OFF;
   std::array<uint8_t,32>output{};
   vm->getFinalResult(output.data(),output.size());
   return output;
  };
  const auto tracked=sequence(TRACE);
  if(tracked!=reference)throw std::runtime_error("instrumented trace not equivalent");
  uint64_t writes=g_writes,bytes=g_writeBytes,readCalls=g_reads,readBytes=g_readBytes;
  uint32_t dead=0;uint64_t deadBytes=0;
  g_skip.assign(size_t(g_seq)+1,0);
  for(uint32_t id=1;id<=g_seq;id++){
   if(g_left[id]==0&&!g_seen[id]){
    g_skip[id]=1;dead++; // whole store can be skipped, not partial bytes
   }
  }
  // To account for skipped store bytes we count in replay; no guarantee all
  // eligible stores are mathematically removable until independent hash test.
  auto replay=sequence(REPLAY);
  if(replay!=reference)throw std::runtime_error("SKIPPING_DEAD_STORES_CHANGED_REAL_RANDOMX_HASH");
  if(g_seq!=writes||g_skipped!=dead)
   throw std::runtime_error("instruction/event sequence changed in dead store replay");
  deadBytes=g_skippedBytes;
  sumWrites+=writes;sumDead+=dead;sumBytes+=bytes;sumDeadBytes+=deadBytes;sumSkipped+=g_skipped;eq++;
  csv<<sample<<","<<nonce<<","<<(sample==0)<<",1,"<<writes<<","<<dead<<","<<bytes<<","<<deadBytes<<","
     <<g_skipped<<",1,"<<readCalls<<","<<readBytes<<"\n";
  std::cout<<"SAMPLE="<<sample<<" nonce="<<nonce<<" OFFICIAL_HASH="<<tohex(reference.data(),32)
   <<" STORE_EVENTS="<<writes<<" DEAD_STORE_EVENTS="<<dead
   <<" DEAD_STORE_BYTES="<<deadBytes<<" REPLAY_VERIFIED=YES\n";
 }
 auto report=[&](const std::string&s){std::cout<<s<<"\n";summary<<s<<"\n";};
 report("AUTHENTIC_HISTORIC_BLOCK_3300100_WINNER_NONCE="+std::to_string(winningNonce));
 report("OFFICIAL_RANDOMX_256BIT_HASH_EXACT="+std::to_string(eq)+"/"+std::to_string(numberSamples));
 report("COMPLETE_SCRATCHPAD_READ_TRACE_COVERS_BYTECODE_AND_VM=YES");
 report("FULL_FINAL_SCRATCHPAD_AES_REDUCTION_TREATED_AS_READ_ALL_BYTES=YES");
 report("TOTAL_DYNAMIC_SCRATCHPAD_WRITE_EVENTS="+std::to_string(sumWrites));
 report("WHOLE_DEAD_WRITE_EVENTS_PROVEN_BY_TRACE="+std::to_string(sumDead));
 report("FULL_HASH_REPLAY_WITH_DEAD_WRITES_SKIPPED="+std::to_string(eq)+"/"+std::to_string(numberSamples));
 report("WHOLE_WRITE_EVENT_ELIMINATION_PERCENT="+std::to_string(100.0*sumDead/sumWrites));
 report("TOTAL_WRITTEN_BYTES="+std::to_string(sumBytes)+" DEAD_WRITE_BYTES="+std::to_string(sumDeadBytes));
 report("DEAD_WRITE_BYTE_PERCENT="+std::to_string(100.0*sumDeadBytes/sumBytes));
 report("REAL_MINING_SPEEDUP_CLAIM=NONE instrumentation overhead and live runtime cost not benchmarked");
 report("NOTE=Dead stores are dynamic for these particular nonce traces; removing the same static instructions for arbitrary nonces is not justified. No cryptanalytic shortcut or guaranteed early nonce rejection obtained.");
 randomx_destroy_vm(vm);randomx_release_cache(cache);return 0;
 }catch(const std::exception&e){std::cerr<<"ERROR "<<e.what()<<"\n";return 1;}
}
