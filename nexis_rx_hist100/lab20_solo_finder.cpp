// NEXIS-RX LAB20
// Real winning nonce finder with a strictly full RandomX 256-bit validity check.
// Historical winning nonce is used only AFTER candidate discovery for audit.
// Cheap Blake2b prehash is analyzed but NEVER used to reject a candidate.
#include "randomx.h"
#include <openssl/evp.h>
#include <boost/multiprecision/cpp_int.hpp>
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using Bytes=std::vector<uint8_t>;
using boost::multiprecision::cpp_int;
static Bytes unhex(const std::string&s){
 if(s.size()%2)throw std::runtime_error("bad hex length");
 auto hex=[](char c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;throw std::runtime_error("bad hex");};
 Bytes b;for(size_t i=0;i<s.size();i+=2)b.push_back(uint8_t((hex(s[i])<<4)|hex(s[i+1])));return b;
}
static std::string tohex(const Bytes&b){const char*d="0123456789abcdef";std::string s;for(uint8_t c:b){s+=d[c>>4];s+=d[c&15];}return s;}
static std::vector<std::string> split(const std::string&s){std::istringstream f(s);std::string x;std::vector<std::string>v;while(std::getline(f,x,','))v.push_back(x);return v;}
static size_t noncepos(const Bytes&b){
 size_t p=0;for(int j=0;j<3;j++){while(true){if(p>=b.size())throw std::runtime_error("varint");uint8_t x=b[p++];if(!(x&128))break;}}
 p+=32;if(p+4>b.size())throw std::runtime_error("nonce not present");return p;
}
static uint32_t getnonce(const Bytes&b,size_t p){
 uint32_t n=0;for(int i=0;i<4;i++)n|=uint32_t(b[p+i])<<(i*8);return n;
}
static void setnonce(Bytes&b,size_t p,uint32_t n){for(int i=0;i<4;i++)b[p+i]=uint8_t(n>>(8*i));}
static cpp_int leint(const Bytes&b){cpp_int x=0;for(int i=int(b.size())-1;i>=0;--i)x=(x<<8)+b[i];return x;}
static cpp_int parsehex(std::string s){
 if(s.substr(0,2)=="0x")s.erase(0,2);
 cpp_int x=0;for(char c:s){
  unsigned z=(c>='0'&&c<='9')?c-'0':((c>='a'&&c<='f')?c-'a'+10:99);
  if(z>15)throw std::runtime_error("difficulty hex");
  x=(x<<4)+z;
 }return x;
}
static uint64_t fnv(const Bytes&data,uint64_t start=14695981039346656037ULL){
 uint64_t h=start;for(unsigned char x:data){h^=uint64_t(x);h*=1099511628211ULL;}return h;
}
static Bytes initialBlake(const Bytes&blob){
 Bytes result(64);unsigned len=0;
 if(!EVP_Digest(blob.data(),blob.size(),result.data(),&len,EVP_blake2b512(),nullptr)||len!=64)
  throw std::runtime_error("BLAKE2b");
 return result;
}
static bool meets(const Bytes&hash,const cpp_int&diff){
 const cpp_int limit=(cpp_int(1)<<256)-1;return leint(hash)*diff<=limit;
}
int main(int argc,char**argv){try{
 if(argc!=5)throw std::runtime_error("usage: nexis_lab20 computed100.csv seedhex attempts out.csv");
 const unsigned maxAttempts=std::stoul(argv[3]);if(maxAttempts<256||maxAttempts>4096)throw std::runtime_error("attempts must be 256..4096");
 std::ifstream in(argv[1]);if(!in)throw std::runtime_error("missing authentic inputs");
 std::string line;std::getline(in,line);if(!std::getline(in,line))throw std::runtime_error("empty input");
 auto cols=split(line);if(cols.size()<9)throw std::runtime_error("csv columns");
 const uint32_t height=std::stoul(cols[0]), knownNonce=std::stoul(cols[1]);const auto expected=unhex(cols[3]);
 auto blob=unhex(cols[4]);auto seed=unhex(argv[2]);if(expected.size()!=32||seed.size()!=32||blob.size()!=76)throw std::runtime_error("input size");
 cpp_int actualDiff=parsehex(cols[6]);if(actualDiff<=0)throw std::runtime_error("invalid network difficulty");
 size_t p=noncepos(blob);if(getnonce(blob,p)!=knownNonce)throw std::runtime_error("nonce offset incorrect");
 auto*cache=randomx_alloc_cache(RANDOMX_FLAG_DEFAULT);if(!cache)throw std::runtime_error("cache init");
 randomx_init_cache(cache,seed.data(),seed.size());
 auto*vm=randomx_create_vm(RANDOMX_FLAG_DEFAULT,cache,nullptr);if(!vm)throw std::runtime_error("vm init");
 auto calculate=[&](Bytes&b){
  Bytes hash(32);randomx_calculate_hash(vm,b.data(),b.size(),hash.data());return hash;
 };
 auto original=calculate(blob);
 if(original!=expected||!meets(original,actualDiff))throw std::runtime_error("historical baseline not verified");
 // Hide the historically winning nonce BEFORE generating the candidate sequence.
 setnonce(blob,p,0u);
 uint64_t state=fnv(blob);state=fnv(seed,state);
 // Every odd stride permutes all 2^32 nonces without duplicate.
 uint32_t start=uint32_t(state>>32)^uint32_t(state);
 uint32_t stride=(uint32_t((state>>13)^state)*0x9e3779b9u)|1u;
 if(stride%2==0)throw std::runtime_error("stride must be odd");
 std::ofstream out(argv[4]);if(!out)throw std::runtime_error("output open");
 out<<"candidate_index,nonce,initial_blake_first_byte,randomx_hash,hash_value_low64,meets_diff_32,meets_diff_128,meets_diff_256,meets_historic_network_diff\n";
 const std::array<unsigned,3> targets={32u,128u,256u};
 std::array<unsigned,3> found={0,0,0},firstAt={0,0,0};std::array<uint32_t,3>firstNonce={0,0,0};
 std::array<Bytes,3>firstHash;
 unsigned liveBlocks=0,preRejected=0,preRejectMiss=0;std::array<unsigned,4>scoreBucket={0,0,0,0},success32Bucket={0,0,0,0};
 auto t0=std::chrono::steady_clock::now();
 for(unsigned i=0;i<maxAttempts;i++){
  uint32_t candidate=uint32_t(start+uint32_t(i)*stride);
  setnonce(blob,p,candidate);
  const auto cheap=initialBlake(blob),exact=calculate(blob);
  unsigned bucket=unsigned(cheap[0])>>6;scoreBucket[bucket]++;
  bool pass32=meets(exact,cpp_int(32)),pass128=meets(exact,cpp_int(128)),pass256=meets(exact,cpp_int(256));
  if(pass32)success32Bucket[bucket]++;
  if(bucket>=1){preRejected++;if(pass32)preRejectMiss++;}
  std::array<bool,3>pass={pass32,pass128,pass256};
  for(int k=0;k<3;k++)if(pass[k]){found[k]++;if(firstAt[k]==0){firstAt[k]=i+1;firstNonce[k]=candidate;firstHash[k]=exact;}}
  bool block=meets(exact,actualDiff);liveBlocks+=block;
  uint64_t low=0;for(int j=0;j<8;j++)low|=uint64_t(exact[j])<<(8*j);
  out<<i<<","<<candidate<<","<<(unsigned)cheap[0]<<","<<tohex(exact)<<","<<low
    <<","<<pass32<<","<<pass128<<","<<pass256<<","<<block<<"\n";
 }
 auto t1=std::chrono::steady_clock::now();double sec=std::chrono::duration<double>(t1-t0).count();
 randomx_destroy_vm(vm);randomx_release_cache(cache);
 std::cout<<"HISTORICAL_BLOB_VERIFY=PASS height="<<height<<" hash="<<tohex(original)
  <<" known_nonce="<<knownNonce<<" historic_network_diff="<<actualDiff<<"\n";
 std::cout<<"CANDIDATE_STRATEGY=FULL_CYCLE_MOD_2^32 start="<<start<<" odd_stride="<<stride
  <<" distinct="<<maxAttempts<<"/"<<maxAttempts<<"\n";
 std::cout<<"RANDOMX_FULL_HASHES="<<maxAttempts<<" runtime_seconds="<<sec<<" real_light_mode_hps="<<maxAttempts/sec<<"\n";
 for(int k=0;k<3;k++){
  std::cout<<"FINDER_TARGET_DIFFICULTY="<<targets[k]<<" valid="<<found[k]<<"/"<<maxAttempts;
  if(firstAt[k])std::cout<<" FIRST_NEW_NONCE="<<firstNonce[k]<<" FIRST_AT_CANDIDATE="<<firstAt[k]
    <<" FIRST_FULL_RANDOMX_HASH="<<tohex(firstHash[k]);
  std::cout<<"\n";
 }
 std::cout<<"ACTUAL_HISTORICAL_NETWORK_DIFFICULTY_NEW_BLOCKS="<<liveBlocks<<"/"<<maxAttempts<<"\n";
 std::cout<<"INITIAL_BLAKE2B_GATE_first_byte_less_than64: allowed="<<maxAttempts-preRejected
  <<" rejected="<<preRejected<<" rejected_valid_diff32_shares="<<preRejectMiss<<"\n";
 for(unsigned b=0;b<4;b++)std::cout<<"INITIAL_BLAKE2B_BUCKET="<<b<<" tested="<<scoreBucket[b]
  <<" valid_diff32="<<success32Bucket[b]<<"\n";
 return (found[0]>0)?0:11;
 }catch(const std::exception&e){std::cerr<<"ERROR "<<e.what()<<"\n";return 12;}
}
