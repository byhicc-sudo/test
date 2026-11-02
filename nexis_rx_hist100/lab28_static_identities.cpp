// NEXIS-RX LAB28: exact ahead-of-execution algebraic bytecode simplification.
// Every rule is static and checks program bytecode, no nonce-hash oracle / dead store trace.
// Reference RandomX 1.2.1, real Monero block 3300100.
// Candidate is only accepted if complete 256-bit hashes match the official reference.
#include "randomx.h"
#include "bytecode_machine.hpp"
#include "blake2/blake2.h"
#include <array>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using Bytes=std::vector<uint8_t>;
using Type=randomx::InstructionType;
using Code=randomx::InstructionByteCode;
static bool enabled=false;
static uint64_t totalPrograms=0,cfroundRemoved=0,pairsRemoved=0,irorPairs=0,negPairs=0,xorPairs=0,swapPairs=0,fswapPairs=0,fscalPairs=0;
static void clearCounts(){totalPrograms=cfroundRemoved=pairsRemoved=irorPairs=negPairs=xorPairs=swapPairs=fswapPairs=fscalPairs=0;}
static bool branchLandsAt(const Code*p,int count,int instr){
 for(int j=0;j<count;j++){
  if(p[j].type==Type::CBRANCH&&int(p[j].target)+1==instr)return true;
 }
 return false;
}
static bool isFloat(Type t){return t>=Type::FSWAP_R&&t<=Type::FSQRT_R;}
extern "C" void nexis28_optimize(Code*p,unsigned count){
 if(!enabled)return;
 if(count!=256)throw std::runtime_error("RandomX expected program length");
 ++totalPrograms;
 for(unsigned i=0;i<count;i++){
  if(p[i].type!=Type::CFROUND)continue;
  for(unsigned j=i+1;j<count;j++){
   Type t=p[j].type;
   if(t==Type::CBRANCH||isFloat(t))break;
   if(t==Type::CFROUND){
    // Between these two CFROUNDs there is no float operation and no branch.
    // Whenever first is executed, the second overwrites rounding before use.
    p[i].type=Type::NOP;
    ++cfroundRemoved;break;
   }
  }
 }
 for(unsigned i=0;i+1<count;i++){
  Code&a=p[i],&c=p[i+1];
  if(branchLandsAt(p,int(count),int(i+1)))continue;
  bool remove=false;
  if(a.type==Type::INEG_R && c.type==Type::INEG_R && a.idst==c.idst){
   remove=true;++negPairs;
  }else if(a.type==Type::ISWAP_R && c.type==Type::ISWAP_R && a.idst==c.idst&&a.isrc==c.isrc){
   remove=true;++swapPairs;
  }else if(a.type==Type::IXOR_R && c.type==Type::IXOR_R && a.idst==c.idst&&a.isrc==c.isrc&&a.idst!=a.isrc){
   remove=true;++xorPairs;
  }else if(((a.type==Type::IROR_R&&c.type==Type::IROL_R)||(a.type==Type::IROL_R&&c.type==Type::IROR_R))
         &&a.idst==c.idst&&a.isrc==c.isrc&&a.idst!=a.isrc){
   remove=true;++irorPairs;
  }else if(a.type==Type::FSWAP_R && c.type==Type::FSWAP_R && a.fdst==c.fdst){
   remove=true;++fswapPairs;
  }else if(a.type==Type::FSCAL_R && c.type==Type::FSCAL_R && a.fdst==c.fdst){
   remove=true;++fscalPairs;
  }
  if(remove){a.type=Type::NOP;c.type=Type::NOP;++pairsRemoved;i++;}
 }
}
static Bytes unhex(const std::string&s){
 auto digit=[](char c)->int{if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;throw std::runtime_error("hex");};
 if(s.size()%2)throw std::runtime_error("bad hex");
 Bytes v;for(size_t i=0;i<s.size();i+=2)v.push_back(uint8_t((digit(s[i])<<4)|digit(s[i+1])));return v;
}
static std::vector<std::string>cols(const std::string&s){std::istringstream f(s);std::string x;std::vector<std::string>a;while(std::getline(f,x,','))a.push_back(x);return a;}
static size_t nonceOffset(const Bytes&b){
 size_t pos=0;for(int j=0;j<3;j++)for(;;){if(pos>=b.size())throw std::runtime_error("varint");if(!(b[pos++]&128))break;}
 pos+=32;if(pos+4>b.size())throw std::runtime_error("nonce position");return pos;
}
static void setnonce(Bytes&b,size_t p,uint32_t v){for(unsigned i=0;i<4;i++)b[p+i]=uint8_t(v>>(8*i));}
static std::string hex(const std::array<uint8_t,32>&h){const char*dig="0123456789abcdef";std::string s;for(auto x:h){s+=dig[x>>4];s+=dig[x&15];}return s;}
struct Measure{double seconds=0;uint64_t checks=0,prog=0,cfround=0,pairs=0,neg=0,swaps=0,xors=0,rots=0,fswaps=0,fscals=0;};
int main(int argc,char**argv){try{
 if(argc!=5)throw std::runtime_error("use lab28 computed100.csv seedhex summary.txt samples.csv");
 std::ifstream in(argv[1]);if(!in)throw std::runtime_error("historic data missing");
 std::string line;std::getline(in,line);if(!std::getline(in,line))throw std::runtime_error("missing first block");
 auto row=cols(line);if(row.size()<9||row[0]!="3300100")throw std::runtime_error("unexpected block");
 auto blob=unhex(row[4]),seed=unhex(argv[2]),known=unhex(row[3]);
 if(blob.size()!=76||seed.size()!=32||known.size()!=32)throw std::runtime_error("field length");
 auto*cache=randomx_alloc_cache(RANDOMX_FLAG_DEFAULT);if(!cache)throw std::runtime_error("cache");
 randomx_init_cache(cache,seed.data(),seed.size());
 auto*vm=randomx_create_vm(RANDOMX_FLAG_DEFAULT,cache,nullptr);if(!vm)throw std::runtime_error("vm");
 const auto p=nonceOffset(blob),winner=uint32_t(std::stoul(row[1]));
 constexpr unsigned N=16;
 std::array<std::array<uint8_t,32>,N>oracle{};
 enabled=false;
 for(unsigned i=0;i<N;i++){
  setnonce(blob,p,winner+i);
  randomx_calculate_hash(vm,blob.data(),blob.size(),oracle[i].data());
 }
 if(!std::equal(oracle[0].begin(),oracle[0].end(),known.begin()))throw std::runtime_error("authentic winner mismatch");
 std::ofstream report(argv[3]),csv(argv[4]);if(!report||!csv)throw std::runtime_error("output");
 csv<<"round,mode,nonce,hash_equal_to_official,bytecode_programs,dead_cfround,algebraically_cancelling_pairs,hash\n";
 Measure a,b;
 for(unsigned round=0;round<4;round++){
  enabled=round%2!=0;Measure m;clearCounts();
  auto before=std::chrono::steady_clock::now();
  for(unsigned i=0;i<N;i++){
   setnonce(blob,p,winner+i);
   std::array<uint8_t,32>out{};
   randomx_calculate_hash(vm,blob.data(),blob.size(),out.data());
   if(out!=oracle[i])throw std::runtime_error("FULL_HASH_256BIT_MISMATCH_DUE_TO_STATIC_RULE");
   csv<<round<<","<<(enabled?"EXACT_STATIC":"STANDARD")<<","<<winner+i<<",1,"
      <<totalPrograms<<","<<cfroundRemoved<<","<<pairsRemoved<<","<<hex(out)<<"\n";
   m.checks++;
  }
  auto after=std::chrono::steady_clock::now();
  m.seconds=std::chrono::duration<double>(after-before).count();
  m.prog=totalPrograms;m.cfround=cfroundRemoved;m.pairs=pairsRemoved;
  m.neg=negPairs;m.swaps=swapPairs;m.xors=xorPairs;m.rots=irorPairs;m.fswaps=fswapPairs;m.fscals=fscalPairs;
  auto&v=enabled?b:a;v.seconds+=m.seconds;v.checks+=m.checks;v.prog+=m.prog;v.cfround+=m.cfround;
  v.pairs+=m.pairs;v.neg+=m.neg;v.swaps+=m.swaps;v.xors+=m.xors;v.rots+=m.rots;
  v.fswaps+=m.fswaps;v.fscals+=m.fscals;
  std::cout<<"ROUND="<<round<<" OPT="<<enabled<<" HPS="<<double(N)/m.seconds
           <<" CFROUND_DELETED="<<m.cfround<<" PAIRS_DELETED="<<m.pairs<<"\n";
 }
 enabled=false;
 randomx_destroy_vm(vm);randomx_release_cache(cache);
 auto emit=[&](const std::string&s){std::cout<<s<<"\n";report<<s<<"\n";};
 emit("HISTORIC_BLOCK_3300100_WINNER_NONCE="+std::to_string(winner));
 emit("PINNED_OFFICIAL_RANDOMX_256BIT_EXACT=64/64");
 emit("RANDOMX_PROGRAMS_COMPARED_PER_MODE="+std::to_string(b.prog)+"/"+std::to_string(b.checks*8));
 emit("STATIC_CFROUND_OVERWRITTEN_BEFORE_FLOAT="+std::to_string(b.cfround));
 emit("STATIC_ALGEBRAIC_CANCEL_PAIRS="+std::to_string(b.pairs));
 emit("STATIC_INTEGER_NEG_NEG_PAIRS="+std::to_string(b.neg));
 emit("STATIC_SWAP_SWAP_PAIRS="+std::to_string(b.swaps));
 emit("STATIC_XOR_XOR_PAIRS="+std::to_string(b.xors));
 emit("STATIC_ROTATE_INVERSE_PAIRS="+std::to_string(b.rots));
 emit("STATIC_FSWAP_FSWAP_PAIRS="+std::to_string(b.fswaps));
 emit("STATIC_FSCAL_FSCAL_PAIRS="+std::to_string(b.fscals));
 emit("STATIC_BYTECODE_INSTRUCTIONS_REPLACED_BY_NOP="+std::to_string(b.cfround+2*b.pairs));
 emit("STANDARD_MODE_HPS="+std::to_string(a.checks/a.seconds));
 emit("STATIC_SIMPLIFIED_MODE_HPS="+std::to_string(b.checks/b.seconds));
 emit("MEASURED_RATIO_STATIC_TO_STANDARD="+std::to_string((b.checks/b.seconds)/(a.checks/a.seconds)));
 emit("CAVEAT=Only static identities proven safe against branch entry and floating point use. Bytecode NOP still executes interpreter dispatch; real H/s controls whether any useful acceleration exists. No early winning nonce predictor.");
 return 0;
 }catch(const std::exception&e){std::cerr<<"ERROR "<<e.what()<<"\n";return 1;}
}
