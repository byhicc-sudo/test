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
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using Bytes=std::vector<unsigned char>;
using boost::multiprecision::cpp_int;
static Bytes parse(const std::string&s){Bytes b;for(unsigned i=0;i<s.size();i+=2){unsigned x;std::stringstream ss;ss<<std::hex<<s.substr(i,2);ss>>x;b.push_back(x);}return b;}
static std::string hex(const Bytes&v){const char*d="0123456789abcdef";std::string s;for(auto b:v){s+=d[b>>4];s+=d[b&15];}return s;}
static std::vector<std::string> split(const std::string&s){std::stringstream ss(s);std::string t;std::vector<std::string>a;while(std::getline(ss,t,','))a.push_back(t);return a;}
static size_t varlen(const Bytes&v,size_t off){size_t old=off;while(v.at(off++)&128){}return off-old;}
static int ham(const Bytes&a,const Bytes&b){int n=0;for(size_t i=0;i<a.size();i++)n+=__builtin_popcount((unsigned)(a[i]^b[i]));return n;}
static Bytes initial(const Bytes&b){Bytes out(64);unsigned sz=64;if(!EVP_Digest(b.data(),b.size(),out.data(),&sz,EVP_blake2b512(),nullptr)||sz!=64)throw std::runtime_error("blake2b failed");return out;}
static cpp_int readhex(std::string s){if(s.substr(0,2)=="0x")s.erase(0,2);cpp_int v=0;for(char c:s){v=(v<<4)+(std::isdigit((unsigned char)c)?c-'0':std::tolower((unsigned char)c)-'a'+10);}return v;}
static cpp_int little(const Bytes&b){cpp_int v=0;for(int i=(int)b.size()-1;i>=0;i--){v<<=8;v+=b[i];}return v;}
int main(int argc,char**argv){try{
if(argc!=4)throw std::runtime_error("args csv seed out.csv");
Bytes seed=parse(argv[2]);if(seed.size()!=32)throw std::runtime_error("seed size");
auto*c=randomx_alloc_cache(RANDOMX_FLAG_DEFAULT);if(!c)throw std::runtime_error("cache");randomx_init_cache(c,seed.data(),seed.size());
auto*vm=randomx_create_vm(RANDOMX_FLAG_DEFAULT,c,nullptr);if(!vm)throw std::runtime_error("vm");
std::ifstream f(argv[1]);std::ofstream out(argv[3]);out<<"height,winner_nonce,winner_pow,neighbor_pow,neighbor_valid,initial_firstbyte_winner,initial_hamming,output_hamming,xor_difference\n";
std::string line;std::getline(f,line);
unsigned ok=0,neighbor_ok=0,blake_zero=0,xor_predict=0;unsigned long long output_ham=0,init_ham=0;std::set<std::string> xor_masks;Bytes firstMask;
auto start=std::chrono::steady_clock::now();
while(std::getline(f,line)){
if(line.empty())continue;auto z=split(line);if(z.size()<9)throw std::runtime_error("columns");
unsigned height=std::stoul(z[0]);uint32_t nonce=std::stoul(z[1]);Bytes expected=parse(z[3]),blob=parse(z[4]);
size_t off=0;for(int i=0;i<3;i++)off+=varlen(blob,off);off+=32;if(blob.size()<off+4)throw std::runtime_error("nonce offset");
for(int j=0;j<4;j++)if(blob[off+j]!=(nonce>>(8*j)&255))throw std::runtime_error("nonce does not match blob");
Bytes win(32),neigh(32);randomx_calculate_hash(vm,blob.data(),blob.size(),win.data());
if(win!=expected)throw std::runtime_error("WINNER_HASH_MISMATCH "+std::to_string(height));
Bytes pre=initial(blob);blake_zero+=(pre[0]==0);
uint32_t n2=nonce+1;for(int j=0;j<4;j++)blob[off+j]=n2>>(8*j)&255;
randomx_calculate_hash(vm,blob.data(),blob.size(),neigh.data());Bytes pre2=initial(blob);
cpp_int diff=readhex(z[6]);bool pass=little(neigh)*diff<(cpp_int(1)<<256);neighbor_ok+=pass;
int outHam=ham(win,neigh),initialHam=ham(pre,pre2);output_ham+=outHam;init_ham+=initialHam;
Bytes mask(32);for(int i=0;i<32;i++)mask[i]=win[i]^neigh[i];xor_masks.insert(hex(mask));
if(ok==0)firstMask=mask;else if(mask==firstMask)xor_predict++;
out<<height<<","<<nonce<<","<<hex(win)<<","<<hex(neigh)<<","<<pass<<","<<(unsigned)pre[0]<<","<<initialHam<<","<<outHam<<","<<hex(mask)<<"\n";++ok;
}
auto end=std::chrono::steady_clock::now();double sec=std::chrono::duration<double>(end-start).count();
randomx_destroy_vm(vm);randomx_release_cache(c);
std::cout<<"CONTROL_SUMMARY winner_hashes_exact="<<ok<<" neighbor_count="<<ok<<" neighbor_valid="<<neighbor_ok<<" blake_first_byte_zero_winning="<<blake_zero<<" distinct_neighbor_xor_masks="<<xor_masks.size()<<" first_mask_predicts_other="<<xor_predict<<" mean_output_hamming="<<(ok?double(output_ham)/ok:0)<<" mean_initial_blake_hamming="<<(ok?double(init_ham)/ok:0)<<" combined_2x_hashes_hps="<<(sec>0?double(ok*2)/sec:0)<<"\n";
return ok==100?0:7;
}catch(const std::exception&e){std::cerr<<"ERROR "<<e.what()<<"\n";return 9;}}
