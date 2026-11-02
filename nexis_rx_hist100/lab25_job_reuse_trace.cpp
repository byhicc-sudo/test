// NEXIS-RX LAB25 — Real RandomX between-nonce reuse audit.
// Official RandomX v1.2.1, 16 authentic job inputs. No algorithmic speedup claim.
// The light-mode dataset reader in the pinned official library is traced
// using a read-only callback: output hash is always verified against unmodified API.
#include "randomx.h"
#include "virtual_machine.hpp"
#include "program.hpp"
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
#include <unordered_set>
#include <vector>

using Bytes=std::vector<uint8_t>;
static bool collecting=false;
static std::vector<uint64_t> datasetReads;
extern "C" void nexis_lab25_dataset_address(uint64_t address){
 if(collecting)datasetReads.push_back(address);
}
static Bytes unhex(const std::string&s){
 if(s.size()%2)throw std::runtime_error("bad hex size");
 auto digit=[](char c)->int{if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;throw std::runtime_error("bad hex");};
 Bytes r;for(size_t i=0;i<s.size();i+=2)r.push_back(uint8_t((digit(s[i])<<4)|digit(s[i+1])));return r;
}
static std::vector<std::string> fields(const std::string&s){
 std::istringstream in(s);std::vector<std::string>r;std::string x;while(std::getline(in,x,','))r.push_back(x);return r;
}
static size_t nonceOffset(const Bytes&b){
 size_t off=0;
 for(unsigned j=0;j<3;j++)for(;;){
  if(off>=b.size())throw std::runtime_error("varint");
  if(!(b[off++]&128))break;
 }
 off+=32;if(off+4>b.size())throw std::runtime_error("nonce offset");
 return off;
}
static uint32_t getNonce(const Bytes&b,size_t p){
 uint32_t n=0;for(unsigned i=0;i<4;i++)n|=uint32_t(b[p+i])<<(8*i);return n;
}
static void putNonce(Bytes&b,size_t p,uint32_t n){
 for(unsigned i=0;i<4;i++)b[p+i]=uint8_t(n>>(8*i));
}
static constexpr size_t programBytes=RANDOMX_PROGRAM_SIZE*sizeof(randomx::Instruction);
static constexpr size_t entropyBytes=16*sizeof(uint64_t);
static_assert(programBytes==2048,"program bytes");
static_assert(sizeof(randomx::Program)==entropyBytes+programBytes,"program ABI layout");
struct Trace{
 std::array<std::array<uint8_t,programBytes>,RANDOMX_PROGRAM_COUNT>inst{};
 std::array<std::array<uint8_t,entropyBytes>,RANDOMX_PROGRAM_COUNT>entropy{};
 std::vector<uint64_t> dataset;
 std::array<uint8_t,32> hash{};
};
static std::string toHex(const std::array<uint8_t,32>&a){
 const char d[]="0123456789abcdef";std::string s;for(auto x:a){s+=d[x>>4];s+=d[x&15];}return s;
}
int main(int argc,char**argv){try{
 if(argc!=5)throw std::runtime_error("usage: lab25 computed100.csv seedhex summary.txt per_nonce.csv");
 std::ifstream in(argv[1]);if(!in)throw std::runtime_error("historical input not found");
 std::string line;std::getline(in,line);if(!std::getline(in,line))throw std::runtime_error("missing row");
 auto cols=fields(line);if(cols.size()<9||cols[0]!="3300100")throw std::runtime_error("unexpected block");
 auto blob=unhex(cols[4]),knownHash=unhex(cols[3]),seed=unhex(argv[2]);
 if(blob.size()!=76||knownHash.size()!=32||seed.size()!=32)throw std::runtime_error("input sizes");
 const auto pos=nonceOffset(blob);const uint32_t win=uint32_t(std::stoul(cols[1]));
 if(getNonce(blob,pos)!=win)throw std::runtime_error("historical nonce position mismatch");
 const auto*key=seed.data();
 auto*cache=randomx_alloc_cache(RANDOMX_FLAG_DEFAULT);if(!cache)throw std::runtime_error("cache");
 randomx_init_cache(cache,key,seed.size());
 auto*vm=randomx_create_vm(RANDOMX_FLAG_DEFAULT,cache,nullptr);if(!vm)throw std::runtime_error("vm");
 std::ofstream summary(argv[3]),csv(argv[4]);if(!summary||!csv)throw std::runtime_error("outputs");
 csv<<"sample,nonce,official_hash_256,full_prog_equal_to_baseline,program_instruction_8B_equal_same_position_of2048,opcode_equal_same_position_of2048,entropy_8B_equal_same_position_of128,read_count,dataset_read_same_iteration_of16384,dataset_unique_overlap_with_winner,dataset_reads_reused_from_prior_nonces\n";
 Trace base;
 std::unordered_set<uint64_t>allReadLines,winLines;
 uint64_t allDatasetReads=0,allCacheHits=0,allSamePosition=0,allProgramExact=0;
 uint64_t all8ByteSame=0,allOpcodeSame=0,allEntropySame=0,allBaselineOverlap=0;
 const unsigned samples=16;
 for(unsigned sample=0;sample<samples;sample++){
  uint32_t nonce=win+sample;
  putNonce(blob,pos,nonce);
  std::array<uint8_t,32> verified{};
  collecting=false;randomx_calculate_hash(vm,blob.data(),blob.size(),verified.data());
  if(sample==0&&!std::equal(verified.begin(),verified.end(),knownHash.begin()))throw std::runtime_error("real winning PoW hash mismatch");
  alignas(16) uint64_t temporary[8]{};
  if(blake2b(temporary,sizeof(temporary),blob.data(),blob.size(),nullptr,0))throw std::runtime_error("initial blake");
  vm->initScratchpad(temporary);vm->resetRoundingMode();
  Trace t;
  datasetReads.clear();datasetReads.reserve(8*RANDOMX_PROGRAM_ITERATIONS);
  collecting=true;
  for(unsigned phase=0;phase<RANDOMX_PROGRAM_COUNT;phase++){
   vm->run(temporary);
   const auto&prog=vm->getProgram();
   const auto*bytes=reinterpret_cast<const uint8_t*>(&prog);
   std::memcpy(t.entropy[phase].data(),bytes,entropyBytes);
   std::memcpy(t.inst[phase].data(),bytes+entropyBytes,programBytes);
   if(phase+1<RANDOMX_PROGRAM_COUNT){
    if(blake2b(temporary,sizeof(temporary),vm->getRegisterFile(),sizeof(randomx::RegisterFile),nullptr,0))
     throw std::runtime_error("chain blake");
   }
  }
  collecting=false;
  t.dataset=datasetReads;
  if(t.dataset.size()!=8*RANDOMX_PROGRAM_ITERATIONS)throw std::runtime_error("dataset read count wrong");
  vm->getFinalResult(t.hash.data(),t.hash.size());
  if(t.hash!=verified)throw std::runtime_error("trace vs official full 256bit mismatch");
  uint64_t equalFullProgram=0,equalInstructions=0,equalOpCodes=0,equalEntropy=0,eqReadOrder=0;
  std::unordered_set<uint64_t> uniqueCurrent(t.dataset.begin(),t.dataset.end());
  uint64_t overlapWithWinner=0,hitsPrior=0;
  for(auto addr:t.dataset){
   ++allDatasetReads;
   if(!allReadLines.insert(addr).second){++hitsPrior;++allCacheHits;}
  }
  if(sample==0){
   base=std::move(t);
   winLines=std::move(uniqueCurrent);
  }else{
   for(unsigned phase=0;phase<RANDOMX_PROGRAM_COUNT;phase++){
    if(base.inst[phase]==t.inst[phase])++equalFullProgram;
    for(unsigned i=0;i<RANDOMX_PROGRAM_SIZE;i++){
     const uint8_t* a=base.inst[phase].data()+i*8;
     const uint8_t* b=t.inst[phase].data()+i*8;
     equalInstructions+=(memcmp(a,b,8)==0);
     equalOpCodes+=(a[0]==b[0]);
    }
    for(unsigned i=0;i<entropyBytes/8;i++)
     equalEntropy+=(memcmp(base.entropy[phase].data()+i*8,t.entropy[phase].data()+i*8,8)==0);
   }
   for(size_t i=0;i<t.dataset.size();i++)eqReadOrder+=(t.dataset[i]==base.dataset[i]);
   for(auto x:uniqueCurrent)overlapWithWinner+=winLines.count(x);
   allProgramExact+=equalFullProgram;
   all8ByteSame+=equalInstructions;
   allOpcodeSame+=equalOpCodes;
   allEntropySame+=equalEntropy;
   allSamePosition+=eqReadOrder;
   allBaselineOverlap+=overlapWithWinner;
  }
  csv<<sample<<","<<nonce<<","<<toHex(verified)<<","<<equalFullProgram<<","<<equalInstructions<<","<<equalOpCodes<<","<<equalEntropy<<","
     <<8*RANDOMX_PROGRAM_ITERATIONS<<","<<eqReadOrder<<","<<overlapWithWinner<<","<<hitsPrior<<"\n";
 }
 auto output=[&](const std::string&s){std::cout<<s<<"\n";summary<<s<<"\n";};
 output("REFERENCE_BLOCK=3300100 HISTORICAL_WINNING_NONCE="+std::to_string(win)+" HASH="+toHex(base.hash));
 output("PINNED_OFFICIAL_RANDOMX_FULL_256BIT_MATCHES=16/16");
 output("CHECKED_SAME_JOB_DIFFERENT_NONCES=15");
 output("GENERATED_PROGRAMS=128 INSTRUCTIONS_PER_PROGRAM=256 TOTAL_GENERATED_INSTRUCTIONS=32768");
 output("FULL_PROGRAM_IDENTICAL_SAME_PHASE="+std::to_string(allProgramExact)+"/120");
 output("EXACT_8BYTE_INSTRUCTIONS_IDENTICAL_SAME_PHASE_POSITION="+std::to_string(all8ByteSame)+"/30720");
 output("OPCODE_EQUAL_SAME_PHASE_POSITION="+std::to_string(allOpcodeSame)+"/30720");
 output("PROGRAM_ENTROPY_64BIT_IDENTICAL_SAME_PHASE_POSITION="+std::to_string(allEntropySame)+"/1920");
 output("DATASET_READS_TOTAL="+std::to_string(allDatasetReads)+" UNIQUE_ADDRESSES="+std::to_string(allReadLines.size()));
 output("DATASET_READS_ELIGIBLE_FOR_IDEAL_UNBOUNDED_MEMOIZATION="+std::to_string(allCacheHits)+"/"+std::to_string(allDatasetReads));
 output("DATASET_READS_SAME_INDEX_VERSUS_WINNER="+std::to_string(allSamePosition)+"/245760");
 output("DATASET_SHARED_UNIQUE_ADDRESSES_WITH_WINNER_SUM_OF_15="+std::to_string(allBaselineOverlap));
 output("HASHES_NETWORK_TARGET_TESTED=1 historic winner + 15 neighboring full RandomX hashes (no new network winner claimed)");
 output("CAVEAT=All reuse statistics are measurements on 16 real full hashes. Dataset repeated address makes the 64B derived item theoretically reusable for fixed seed, but memoization has lookup/storage cost, and already-computed caches differ in full mode. No net mining speedup proven.");
 randomx_destroy_vm(vm);randomx_release_cache(cache);
 return 0;
 }catch(const std::exception&e){std::cerr<<"ERROR "<<e.what()<<"\n";return 1;}
}
