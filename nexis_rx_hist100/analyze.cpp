#include <cryptopp/keccak.h>
#include <boost/multiprecision/cpp_int.hpp>
#include "randomx.h"
#include <array>
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using Bytes=std::vector<unsigned char>;
using boost::multiprecision::cpp_int;
static Bytes dec(const std::string&s){if(s.size()%2)throw std::runtime_error("invalid hex");Bytes b;for(size_t i=0;i<s.size();i+=2){auto d=[](char x){if(x>='0'&&x<='9')return x-'0';if(x>='a'&&x<='f')return x-'a'+10;if(x>='A'&&x<='F')return x-'A'+10;throw std::runtime_error("bad char");};b.push_back((d(s[i])<<4)|d(s[i+1]));}return b;}
static std::string enc(const Bytes&b){const char*h="0123456789abcdef";std::string s;for(auto x:b){s+=h[x>>4];s+=h[x&15];}return s;}
static void varint(Bytes&b,uint64_t x){while(x>=128){b.push_back(uint8_t(x)|128);x>>=7;}b.push_back(uint8_t(x));}
static Bytes khash(const Bytes&b){Bytes out(32);CryptoPP::Keccak_256 k;k.CalculateDigest(out.data(),b.data(),b.size());return out;}
static Bytes pairhash(const Bytes&a,const Bytes&b){if(a.size()!=32||b.size()!=32)throw std::runtime_error("bad leaf");Bytes v=a;v.insert(v.end(),b.begin(),b.end());return khash(v);}
static Bytes treehash(const std::vector<Bytes>&leaves){auto n=leaves.size();if(n==0)throw std::runtime_error("no leaves");if(n==1)return leaves[0];if(n==2)return pairhash(leaves[0],leaves[1]);size_t cnt=1;while(cnt*2<n)cnt*=2;size_t direct=2*cnt-n;std::vector<Bytes>level;for(size_t i=0;i<direct;i++)level.push_back(leaves[i]);for(size_t i=direct;i<n;i+=2)level.push_back(pairhash(leaves[i],leaves[i+1]));while(level.size()>1){std::vector<Bytes>next;for(size_t i=0;i<level.size();i+=2)next.push_back(pairhash(level[i],level[i+1]));level.swap(next);}return level[0];}
static std::vector<std::string> split(const std::string&s,char delim){std::vector<std::string>parts;std::stringstream ss(s);std::string t;while(std::getline(ss,t,delim))parts.push_back(t);return parts;}
static cpp_int readHexInt(std::string s){if(s.rfind("0x",0)==0)s.erase(0,2);cpp_int x=0;for(char c:s){int d=std::isdigit((unsigned char)c)?c-'0':std::tolower((unsigned char)c)-'a'+10;x=(x<<4)+d;}return x;}
static cpp_int leInt(const Bytes&h){cpp_int x=0;for(int i=int(h.size())-1;i>=0;i--){x<<=8;x+=h[i];}return x;}
static int hamming(const Bytes&a,const Bytes&b){int n=0;for(size_t i=0;i<a.size();i++)n+=__builtin_popcount(unsigned(a[i]^b[i]));return n;}
int main(int argc,char**argv){try{
 if(argc!=4)throw std::runtime_error("usage analyze record.tsv seed_hex output.csv");
 std::string seedHex=argv[2];Bytes seed=dec(seedHex);if(seed.size()!=32)throw std::runtime_error("seed not 32 bytes");
 std::ifstream f(argv[1]);if(!f)throw std::runtime_error("missing tsv");std::ofstream out(argv[3]);if(!out)throw std::runtime_error("no output");
 out<<"height,nonce,block_id,pow_hash,hashing_blob,hashing_blob_bytes,difficulty,leading_zero_bits,hamming_from_prior\n";
 auto*cache=randomx_alloc_cache(RANDOMX_FLAG_DEFAULT);if(!cache)throw std::runtime_error("alloc cache");randomx_init_cache(cache,seed.data(),seed.size());auto*vm=randomx_create_vm(RANDOMX_FLAG_DEFAULT,cache,nullptr);if(!vm)throw std::runtime_error("create vm");
 unsigned count=0,blockIdsOK=0,powPass=0;int minLz=256,maxLz=0;unsigned long long sumHamming=0;Bytes prior;
 std::string line;while(std::getline(f,line)){if(line.empty())continue;auto v=split(line,'\t');if(v.size()!=11)throw std::runtime_error("wrong columns "+std::to_string(v.size()));
 uint64_t height=std::stoull(v[0]);std::string blockid=v[1];Bytes prev=dec(v[2]);uint32_t nonce=std::stoul(v[3]);uint64_t timestamp=std::stoull(v[4]);uint64_t major=std::stoull(v[5]);uint64_t minor=std::stoull(v[6]);std::vector<Bytes>leaves{dec(v[7])};if(!v[8].empty())for(const auto&h:split(v[8],','))leaves.push_back(dec(h));
 cpp_int diff=readHexInt(v[9]);if(diff==0)throw std::runtime_error("zero diff");
 Bytes blob;varint(blob,major);varint(blob,minor);varint(blob,timestamp);blob.insert(blob.end(),prev.begin(),prev.end());for(int k=0;k<4;k++)blob.push_back(uint8_t(nonce>>(8*k)));Bytes root=treehash(leaves);blob.insert(blob.end(),root.begin(),root.end());varint(blob,leaves.size());
 auto calculatedId=enc(khash(blob));if(calculatedId!=blockid){std::cerr<<"BAD_BLOCK_ID height="<<height<<" calc="<<calculatedId<<" want="<<blockid<<" leaves="<<leaves.size()<<" blob="<<enc(blob)<<"\n";return 4;}
 blockIdsOK++;
 Bytes pow(32);randomx_calculate_hash(vm,blob.data(),blob.size(),pow.data());cpp_int h=leInt(pow);bool pass=(h*diff < (cpp_int(1)<<256));powPass+=pass;
 int lz=0;for(int q=31;q>=0;q--){if(pow[q]==0){lz+=8;continue;}lz+=__builtin_clz(unsigned(pow[q]))-24;break;}
 minLz=std::min(minLz,lz);maxLz=std::max(maxLz,lz);int ham=prior.empty()?-1:hamming(pow,prior);if(ham>=0)sumHamming+=ham;prior=pow;
 out<<height<<","<<nonce<<","<<blockid<<","<<enc(pow)<<","<<enc(blob)<<","<<blob.size()<<","<<v[9]<<","<<lz<<","<<ham<<"\n";
 count++;if(!pass){std::cerr<<"INVALID_POW height="<<height<<" pow="<<enc(pow)<<" diff="<<v[9]<<"\n";return 5;}
 }
 randomx_destroy_vm(vm);randomx_release_cache(cache);
 std::cout<<"EXACT_100_SUMMARY blocks="<<count<<" block_id_matches="<<blockIdsOK<<" valid_difficulty="<<powPass<<" min_leading_zero="<<minLz<<" max_leading_zero="<<maxLz<<" mean_hamming_adjacent="<<(count>1?double(sumHamming)/(count-1):0)<<" seed="<<seedHex<<"\n";
 return (count==100&&blockIdsOK==100&&powPass==100)?0:6;
 }catch(const std::exception&e){std::cerr<<"ERROR "<<e.what()<<"\n";return 9;}}
