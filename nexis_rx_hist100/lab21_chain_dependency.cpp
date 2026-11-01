// NEXIS-RX LAB21: phase-by-phase exact RandomX dependency measurement.
// Real historical block #3300100, winning nonce plus fifteen adjacent values.
// For each phase compare complete 2 MiB scratchpad, 512-bit chain seed,
// and final register. Only sample evidence, no cryptanalytic shortcut claim.
#include "randomx.h"
#include "virtual_machine.hpp"
#include "blake2/blake2.h"
#include "configuration.h"
#include <array>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <cfenv>
using Bytes=std::vector<uint8_t>;
static Bytes unhex(const std::string&s){
 if(s.size()%2)throw std::runtime_error("hex length");
 auto d=[](char c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;throw std::runtime_error("bad hex");};
 Bytes b;for(size_t i=0;i<s.size();i+=2)b.push_back(uint8_t(d(s[i])*16+d(s[i+1])));return b;
}
static std::vector<std::string> fields(const std::string&s){std::stringstream f(s);std::vector<std::string>v;std::string x;while(std::getline(f,x,','))v.push_back(x);return v;}
static std::string hex(const Bytes&v){const char*d="0123456789abcdef";std::string s;for(uint8_t x:v){s+=d[x>>4];s+=d[x&15];}return s;}
static Bytes digest(const void*p,size_t n,size_t output=32){
 Bytes b(output);if(blake2b(b.data(),output,p,n,nullptr,0))throw std::runtime_error("blake2b fail");return b;
}
static size_t npos(const Bytes&blob){
 size_t off=0;for(int j=0;j<3;j++){while(true){if(off>=blob.size())throw std::runtime_error("varint");auto c=blob[off++];if(!(c&128))break;}}
 off+=32;if(off+4>blob.size())throw std::runtime_error("blob too short");return off;
}
static void setnonce(Bytes&b,size_t pos,uint32_t v){for(int k=0;k<4;k++)b[pos+k]=uint8_t(v>>(8*k));}
static int hamming(const Bytes&a,const Bytes&b){
 if(a.size()!=b.size())throw std::runtime_error("size mismatch");
 int cnt=0;for(size_t i=0;i<a.size();i++)cnt+=__builtin_popcount(unsigned(a[i]^b[i]));return cnt;
}
static size_t equalBytes(const Bytes&a,const Bytes&b){
 if(a.size()!=b.size())throw std::runtime_error("size mismatch");
 size_t eq=0;for(size_t i=0;i<a.size();i++)eq+=(a[i]==b[i]);return eq;
}
static size_t equalLines(const Bytes&a,const Bytes&b){
 if(a.size()!=b.size()||a.size()%64)throw std::runtime_error("line size mismatch");
 size_t eq=0;for(size_t i=0;i<a.size();i+=64)eq+=(memcmp(a.data()+i,b.data()+i,64)==0);return eq;
}
struct Stage {Bytes scratch,seed,reg,spDigest;};
struct Trace {std::vector<Stage>steps;Bytes finalHash;Bytes finalReg;};
int main(int argc,char**argv){try{
 if(argc!=5)throw std::runtime_error("args historic_verified.csv seedhex out.tsv perturb.tsv");
 std::ifstream f(argv[1]);if(!f)throw std::runtime_error("missing historic input");
 std::string line;std::getline(f,line);if(!std::getline(f,line))throw std::runtime_error("missing block record");
 auto v=fields(line);if(v.size()<9)throw std::runtime_error("bad historic record");
 if(v[0]!="3300100")throw std::runtime_error("unexpected historic block");
 auto originalBlob=unhex(v[4]),seed=unhex(argv[2]),expected=unhex(v[3]);
 if(originalBlob.size()!=76||seed.size()!=32||expected.size()!=32)throw std::runtime_error("wrong buffer size");
 const uint32_t winningNonce=std::stoul(v[1]);const size_t nonceOffset=npos(originalBlob);
 auto*cache=randomx_alloc_cache(RANDOMX_FLAG_DEFAULT);if(!cache)throw std::runtime_error("alloc cache");
 randomx_init_cache(cache,seed.data(),seed.size());
 auto*machine=randomx_create_vm(RANDOMX_FLAG_DEFAULT,cache,nullptr);if(!machine)throw std::runtime_error("create vm");
 std::ofstream out(argv[3]),pert(argv[4]);if(!out||!pert)throw std::runtime_error("write file");
 out<<"sample,nonce,stage,seed_hd_from_winner_512,register_digest_hd_from_winner_256,scratch_digest_hd_from_winner_256,scratch_equal_bytes_of_2097152,scratch_identical_64byte_lines_of_32768\n";
 pert<<"register_word,final_blake_hamming_256,first_32_bits_modified,first_64_bits_modified\n";
 if(sizeof(randomx::RegisterFile)!=256)throw std::runtime_error("register size assumption invalid");
 if(randomx::ScratchpadSize!=2097152)throw std::runtime_error("scratchpad size assumption invalid");
 auto trace=[&](uint32_t nonce,bool verifyReference)->Trace{
  Bytes blob=originalBlob;setnonce(blob,nonceOffset,nonce);
  Bytes ref(32);
  if(verifyReference)randomx_calculate_hash(machine,blob.data(),blob.size(),ref.data());
  Trace t;
  alignas(16) uint64_t temp[8];if(blake2b(temp,sizeof(temp),blob.data(),blob.size(),nullptr,0))throw std::runtime_error("initial blake fail");
  machine->initScratchpad(&temp);
  machine->resetRoundingMode();
  auto snapshot=[&](){
   Stage st;st.seed=Bytes((uint8_t*)temp,(uint8_t*)temp+64);
   auto*reg=(const uint8_t*)machine->getRegisterFile();
   st.reg=digest(reg,sizeof(randomx::RegisterFile));
   const auto*sp=(const uint8_t*)machine->getScratchpad();
   st.scratch=Bytes(sp,sp+randomx::ScratchpadSize);
   st.spDigest=digest(st.scratch.data(),st.scratch.size());
   t.steps.push_back(std::move(st));
  };
  snapshot(); // stage 0, after initial seed fill
  for(int chain=0;chain<RANDOMX_PROGRAM_COUNT;chain++){
   machine->run(&temp);
   if(chain<RANDOMX_PROGRAM_COUNT-1){
    if(blake2b(temp,sizeof(temp),machine->getRegisterFile(),sizeof(randomx::RegisterFile),nullptr,0))
      throw std::runtime_error("chain blake error");
   }
   snapshot();
  }
  t.finalHash.resize(32);machine->getFinalResult(t.finalHash.data(),32);
  t.finalReg=Bytes((uint8_t*)machine->getRegisterFile(),(uint8_t*)machine->getRegisterFile()+sizeof(randomx::RegisterFile));
  if(verifyReference && t.finalHash!=ref)throw std::runtime_error("MANUAL_CHAIN_MISMATCH_WITH_OFFICIAL_REFERENCE nonce="+std::to_string(nonce));
  return t;
 };
 const Trace winner=trace(winningNonce,true);
 if(winner.finalHash!=expected)throw std::runtime_error("known real block hash mismatch");
 std::cout<<"REFERENCE_FULL_HASH_OK=YES winning_nonce="<<winningNonce<<" hash="<<hex(winner.finalHash)<<"\n";
 std::cout<<"PROGRAMS="<<RANDOMX_PROGRAM_COUNT<<" iterations_per_program="<<RANDOMX_PROGRAM_ITERATIONS
  <<" scratchpad_bytes="<<randomx::ScratchpadSize<<" final_register_file_bytes="<<sizeof(randomx::RegisterFile)<<"\n";
 const unsigned samples=16;
 size_t maxEqualLines=0, maxEqualBytes=0;unsigned seedIdentical=0,regIdentical=0,scratchIdentical=0,finalIdentical=0;
 long long totalEqualLines=0;size_t nComparisons=0;
 for(unsigned sample=0;sample<samples;sample++){
  uint32_t nonce=winningNonce+sample;
  // Reference uses full regular API on every sample, proving exact staging.
  Trace now=(sample==0)?winner:trace(nonce,true);
  finalIdentical+=(now.finalHash==winner.finalHash);
  for(unsigned stage=0;stage<now.steps.size();stage++){
   const auto&a=now.steps[stage],&b=winner.steps[stage];
   int seedHD=hamming(a.seed,b.seed),regHD=hamming(a.reg,b.reg),scratchHD=hamming(a.spDigest,b.spDigest);
   size_t eqByte=equalBytes(a.scratch,b.scratch),eqLine=equalLines(a.scratch,b.scratch);
   if(sample>0){
    seedIdentical+=(seedHD==0);regIdentical+=(regHD==0);scratchIdentical+=(scratchHD==0);
    maxEqualBytes=std::max(maxEqualBytes,eqByte);
    maxEqualLines=std::max(maxEqualLines,eqLine);
    totalEqualLines+=eqLine;nComparisons++;
   }
   out<<sample<<","<<nonce<<","<<stage<<","<<seedHD<<","<<regHD<<","<<scratchHD<<","<<eqByte<<","<<eqLine<<"\n";
  }
  if(sample==0){
   Bytes recalculated=digest(winner.finalReg.data(),winner.finalReg.size());
   if(recalculated!=winner.finalHash)throw std::runtime_error("final register->blake2b mismatch");
   for(unsigned word=0;word<32;word++){
    Bytes perturbed=winner.finalReg;perturbed[word*8]^=1;Bytes after=digest(perturbed.data(),perturbed.size());
    int hd=hamming(winner.finalHash,after);
    bool changed32=!std::equal(winner.finalHash.begin(),winner.finalHash.begin()+4,after.begin());
    bool changed64=!std::equal(winner.finalHash.begin(),winner.finalHash.begin()+8,after.begin());
    pert<<word<<","<<hd<<","<<changed32<<","<<changed64<<"\n";
    if(!changed32||!changed64)throw std::runtime_error("unexpected fixed output prefix in sampled register perturbation");
   }
  }
 }
 randomx_destroy_vm(machine);randomx_release_cache(cache);
 std::cout<<"TRACED_NONCES="<<samples<<" STAGES_PER_NONCE="<<winner.steps.size()
  <<" OFFICIAL_HASH_EXACT="<<samples<<"/"<<samples
  <<" WINNER_FINAL_HASH_MATCHES="<<finalIdentical<<"/"<<samples<<"\n";
 std::cout<<"COMPARED_DIFFERENT_NONCES="<<samples-1
  <<" AT_STAGES="<<winner.steps.size()<<" COMPARISONS="<<nComparisons
  <<" CHAIN_SEED_IDENTICAL="<<seedIdentical
  <<" REGISTER_DIGEST_IDENTICAL="<<regIdentical
  <<" SCRATCHPAD_DIGEST_IDENTICAL="<<scratchIdentical<<"\n";
 std::cout<<"SCRATCHPAD_IDENTICAL_64B_LINES_MAX_PER_PAIR="<<maxEqualLines<<"/32768"
  <<" SCRATCHPAD_MAX_EQUAL_BYTES_PER_PAIR="<<maxEqualBytes<<"/2097152"
  <<" TOTAL_IDENTICAL_64B_LINES_ALL_DIFFERENT_NONCE_STAGE_PAIRS="<<totalEqualLines<<"\n";
 std::cout<<"FINAL_REGISTER_WORD_PERTURBATIONS=32/32 FULL_BLAKE_DIGEST_CHANGED=32/32 FIRST32_PREFIX_CHANGED=32/32\n";
 std::cout<<"NOTE=Empirical dependency observations only. No universal early reject theorem or RandomX shortcut proven.\n";
 return 0;
 }catch(const std::exception&e){std::cerr<<"ERROR "<<e.what()<<"\n";return 1;}
}
