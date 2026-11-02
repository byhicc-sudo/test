// NEXIS-RX LAB24 — GF(2) exact nonce-bit sensitivity on a real Monero job
// 1 baseline, 32 single-bit changes, all 496 two-bit changes, 32 selected triples.
// All candidate outputs computed by official pinned RandomX. No predicted hashes.
#include "randomx.h"
#include "blake2/blake2.h"
#include <boost/multiprecision/cpp_int.hpp>
#include <array>
#include <bitset>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using Bytes=std::vector<uint8_t>;
using boost::multiprecision::cpp_int;
struct Sample{std::array<uint8_t,64>blake{};std::array<uint8_t,32>pow{};};
static Bytes unhex(const std::string&s){
 if(s.size()%2)throw std::runtime_error("hex size");
 auto nib=[](char c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;throw std::runtime_error("nonhex");};
 Bytes v;for(size_t i=0;i<s.size();i+=2)v.push_back(uint8_t((nib(s[i])<<4)|nib(s[i+1])));return v;
}
static std::vector<std::string> split(const std::string&s){std::stringstream f(s);std::string w;std::vector<std::string>v;while(std::getline(f,w,','))v.push_back(w);return v;}
static size_t npos(const Bytes&b){
 size_t p=0;for(int j=0;j<3;j++)for(;;){if(p>=b.size())throw std::runtime_error("blob varint");if(!(b[p++]&128))break;}
 p+=32;if(p+4>b.size())throw std::runtime_error("nonce offset");return p;
}
static uint32_t getnonce(const Bytes&b,size_t p){uint32_t n=0;for(unsigned i=0;i<4;i++)n|=uint32_t(b[p+i])<<(8*i);return n;}
static void putnonce(Bytes&b,size_t p,uint32_t n){for(unsigned i=0;i<4;i++)b[p+i]=uint8_t(n>>(8*i));}
static cpp_int numberhex(const std::string&raw){std::string s=raw;if(s.substr(0,2)=="0x")s.erase(0,2);cpp_int x=0;for(char c:s){int z=c>='0'&&c<='9'?c-'0':(c>='a'&&c<='f'?c-'a'+10:-1);if(z<0||z>15)throw std::runtime_error("bad difficulty");x=(x<<4)+z;}return x;}
static cpp_int leint(const std::array<uint8_t,32>&b){cpp_int x=0;for(int i=31;i>=0;i--)x=(x<<8)+b[size_t(i)];return x;}
static uint64_t high38(const std::array<uint8_t,32>&h){
 uint64_t w=0;for(unsigned k=0;k<8;k++)w|=uint64_t(h[24+k])<<(8*k);
 return w>>26;
}
template<size_t N>static std::bitset<N> asbits(const uint8_t*p){
 std::bitset<N>b;for(size_t i=0;i<N;i++)if((p[i/8]>>(i%8))&1)b.set(i);return b;
}
template<size_t N>static size_t gf2rank(const std::vector<std::bitset<N>>&vectors){
 std::array<std::bitset<N>,N>basis{};std::array<bool,N>used{};size_t rank=0;
 for(auto v:vectors)for(int bit=int(N)-1;bit>=0;bit--){
  if(!v.test(size_t(bit)))continue;
  if(used[size_t(bit)]){v^=basis[size_t(bit)];continue;}
  used[size_t(bit)]=true;basis[size_t(bit)]=v;rank++;break;
 }
 return rank;
}
static Sample combine(const Sample&a,const Sample&b){
 Sample x;for(size_t i=0;i<64;i++)x.blake[i]=a.blake[i]^b.blake[i];
 for(size_t i=0;i<32;i++)x.pow[i]=a.pow[i]^b.pow[i];
 return x;
}
static bool zeros(const Sample&s){for(auto b:s.pow)if(b)return false;return true;}
static int lz(const std::array<uint8_t,32>&b){
 int count=0;for(int i=31;i>=0;i--){if(b[size_t(i)]==0){count+=8;continue;}count+=__builtin_clz(unsigned(b[size_t(i)]))-24;break;}
 return count;
}
int main(int argc,char**argv){try{
 if(argc!=5)throw std::runtime_error("usage: lab24 computed100.csv seedhex summary.txt candidates.csv");
 std::ifstream in(argv[1]);if(!in)throw std::runtime_error("no 100-block exact data");
 std::string line;std::getline(in,line);if(!std::getline(in,line))throw std::runtime_error("missing row");
 auto row=split(line);if(row.size()<9||row[0]!="3300100")throw std::runtime_error("unexpected dataset");
 auto blob=unhex(row[4]),expected=unhex(row[3]),seed=unhex(argv[2]);
 if(blob.size()!=76||expected.size()!=32||seed.size()!=32)throw std::runtime_error("input size");
 const size_t pos=npos(blob);uint32_t winner=uint32_t(std::stoul(row[1]));
 if(winner!=getnonce(blob,pos))throw std::runtime_error("reference nonce field mismatch");
 const cpp_int difficulty=numberhex(row[6]);
 if(difficulty!=cpp_int("367410898587"))throw std::runtime_error("unexpected real difficulty");
 auto*cache=randomx_alloc_cache(RANDOMX_FLAG_DEFAULT);if(!cache)throw std::runtime_error("cache allocation");
 randomx_init_cache(cache,seed.data(),seed.size());
 auto*vm=randomx_create_vm(RANDOMX_FLAG_DEFAULT,cache,nullptr);if(!vm)throw std::runtime_error("VM");
 Sample reference;for(size_t i=0;i<32;i++)reference.pow[i]=expected[i];
 randomx_calculate_hash(vm,blob.data(),blob.size(),reference.pow.data());
 for(size_t i=0;i<32;i++)if(reference.pow[i]!=expected[i])throw std::runtime_error("authentic network winner mismatch");
 if(leint(reference.pow)*difficulty>((cpp_int(1)<<256)-1))throw std::runtime_error("winner network target mismatch");
 const uint32_t height=uint32_t(std::stoul(row[0]));
 // Baseline depends only on public block height, not historical winning nonce.
 const uint32_t baseNonce=(height*0x9e3779b9U)^0x85ebca6bU;
 if(baseNonce==winner)throw std::runtime_error("biased baseline");
 std::ofstream csv(argv[4]),summary(argv[3]);if(!csv||!summary)throw std::runtime_error("output open");
 csv<<"mask,nonce,toggled_bits,hash_leading_zeros,high38_unsigned,network_valid\n";
 std::map<uint32_t,Sample>cacheSamples;
 unsigned networkValid=0;
 auto calculate=[&](uint32_t mask)->Sample{
  auto it=cacheSamples.find(mask);if(it!=cacheSamples.end())return it->second;
  if(cacheSamples.size()>600)throw std::runtime_error("too many samples");
  putnonce(blob,pos,baseNonce^mask);
  Sample result;
  if(blake2b(result.blake.data(),result.blake.size(),blob.data(),blob.size(),nullptr,0))throw std::runtime_error("init blake");
  randomx_calculate_hash(vm,blob.data(),blob.size(),result.pow.data());
  bool accepted=leint(result.pow)*difficulty<=(cpp_int(1)<<256)-1;
  networkValid+=accepted;
  csv<<mask<<","<<(baseNonce^mask)<<","<<__builtin_popcount(mask)<<","<<lz(result.pow)
    <<","<<high38(result.pow)<<","<<accepted<<"\n";
  cacheSamples.emplace(mask,result);
  return result;
 };
 auto t0=std::chrono::steady_clock::now();
 const auto zero=calculate(0);
 std::array<Sample,32>first{};
 std::vector<std::bitset<512>>initVectors;
 std::vector<std::bitset<256>>finalVectors;
 std::vector<std::bitset<38>>targetVectors;
 for(unsigned i=0;i<32;i++){
  first[i]=calculate(uint32_t(1)<<i);
  Sample d=combine(first[i],zero);
  initVectors.push_back(asbits<512>(d.blake.data()));
  finalVectors.push_back(asbits<256>(d.pow.data()));
  targetVectors.push_back(std::bitset<38>(high38(d.pow)));
 }
 const unsigned rankBlake=unsigned(gf2rank(initVectors));
 const unsigned rankAll=unsigned(gf2rank(finalVectors));
 const unsigned rank38=unsigned(gf2rank(targetVectors));
 unsigned secondNonzero256=0,secondNonzero38=0,secondNonzeroInit=0,secondAny=0;
 std::map<uint32_t,Sample>secondDerivatives;
 for(unsigned a=0;a<32;a++)for(unsigned b=a+1;b<32;b++){
  const uint32_t mask=(uint32_t(1)<<a)|(uint32_t(1)<<b);
  Sample d=combine(combine(calculate(mask),first[a]),combine(first[b],zero));
  bool nz256=!zeros(d);
  bool nz38=high38(d.pow)!=0;
  bool nz512=false;for(auto x:d.blake)nz512|=(x!=0);
  secondNonzero256+=nz256;secondNonzero38+=nz38;secondNonzeroInit+=nz512;secondAny++;
  secondDerivatives.emplace(mask,d);
 }
 unsigned thirdNonzero256=0,thirdNonzero38=0,thirdNonzeroInit=0,thirdTotal=0;
 for(unsigned a=0;a<32;a++){
  unsigned b=(a+1)%32,c=(a+2)%32;
  const uint32_t mask=(uint32_t(1)<<a)|(uint32_t(1)<<b)|(uint32_t(1)<<c);
  // Third finite difference over {a,b,c}:
  // F(abc)^F(ab)^F(ac)^F(bc)^F(a)^F(b)^F(c)^F(0).
  auto third=calculate(mask);
  third=combine(third,first[a]);third=combine(third,first[b]);third=combine(third,first[c]);
  auto ab=secondDerivatives.at((uint32_t(1)<<a)|(uint32_t(1)<<b));
  auto ac=secondDerivatives.at((uint32_t(1)<<a)|(uint32_t(1)<<c));
  auto bc=secondDerivatives.at((uint32_t(1)<<b)|(uint32_t(1)<<c));
  // (second derivative)=F(pair)^F(a)^F(b)^F(0); substituting three derivatives
  // cancels singles and baseline as needed, giving exact third difference.
  // D3=F(abc)^F(ab)^F(ac)^F(bc)^F(a)^F(b)^F(c)^F(0)
  // =F(abc)^Dab^Dac^Dbc^F(a)^F(b)^F(c)
  third=combine(third,ab);third=combine(third,ac);third=combine(third,bc);
  thirdNonzero256+=!zeros(third);
  thirdNonzero38+=(high38(third.pow)!=0);
  bool nz512=false;for(auto x:third.blake)nz512|=(x!=0);
  thirdNonzeroInit+=nz512;thirdTotal++;
 }
 auto t1=std::chrono::steady_clock::now();
 auto emit=[&](const std::string&s){std::cout<<s<<"\n";summary<<s<<"\n";};
 emit("AUTHENTIC_MONERO_BLOCK=3300100 WINNER_NONCE_VERIFIED="+std::to_string(winner));
 emit("DIFFICULTY_NETWORK=367410898587 NECESSARY_TARGET_HIGH_ZEROS=38");
 emit("NONCE_BASE_FROM_HEIGHT_INDEPENDENT_OF_WINNER="+std::to_string(baseNonce));
 emit("ACTUAL_FULL_RANDOMX_HASHES="+std::to_string(cacheSamples.size())+" UNIQUE_NONCES="+std::to_string(cacheSamples.size()));
 emit("NONCE_BIT_TO_INITIAL_BLAKE512_GF2_RANK="+std::to_string(rankBlake)+"/32");
 emit("NONCE_BIT_TO_FINAL_RANDOMX256_GF2_RANK="+std::to_string(rankAll)+"/32");
 emit("NONCE_BIT_TO_TARGET_HIGH38_GF2_RANK="+std::to_string(rank38)+"/32");
 emit("SECOND_DIFFERENCE_496_PAIRS_NONZERO_INITIAL_BLAKE512="+std::to_string(secondNonzeroInit)+"/"+std::to_string(secondAny));
 emit("SECOND_DIFFERENCE_496_PAIRS_NONZERO_FINAL_RANDOMX256="+std::to_string(secondNonzero256)+"/"+std::to_string(secondAny));
 emit("SECOND_DIFFERENCE_496_PAIRS_NONZERO_TARGET_HIGH38="+std::to_string(secondNonzero38)+"/"+std::to_string(secondAny));
 emit("THIRD_DIFFERENCE_32_TRIPLES_NONZERO_INITIAL_BLAKE512="+std::to_string(thirdNonzeroInit)+"/"+std::to_string(thirdTotal));
 emit("THIRD_DIFFERENCE_32_TRIPLES_NONZERO_FINAL_RANDOMX256="+std::to_string(thirdNonzero256)+"/"+std::to_string(thirdTotal));
 emit("THIRD_DIFFERENCE_32_TRIPLES_NONZERO_TARGET_HIGH38="+std::to_string(thirdNonzero38)+"/"+std::to_string(thirdTotal));
 emit("NEW_ACTUAL_NETWORK_WINNING_NONCES="+std::to_string(networkValid));
 const double sec=std::chrono::duration<double>(t1-t0).count();
 emit("ELAPSED_SECONDS="+std::to_string(sec)+" LIGHT_MODE_HPS="+std::to_string(cacheSamples.size()/sec));
 emit("CAVEAT=Finite differences and rank are exact on the sampled real job and baseline. A nonzero third difference rules out degree<=2 over GF2 for the affected target function, not every possible non-arithmetic shortcut. No predictive nonce filter established.");
 randomx_destroy_vm(vm);randomx_release_cache(cache);return 0;
 }catch(const std::exception&e){std::cerr<<"ERROR "<<e.what()<<"\n";return 1;}
}
