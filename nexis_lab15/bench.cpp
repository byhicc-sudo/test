#include "randomx.h"
#include <array>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
static void write_nonce(unsigned char* p,uint32_t x){for(int i=0;i<4;i++)p[i]=(x>>(8*i))&255;}
static std::vector<unsigned char> hex(const std::string& s){
 std::vector<unsigned char> v;
 if(s.size()%2)std::exit(2);
 for(size_t i=0;i<s.size();i+=2){char t[3]={s[i],s[i+1],0};v.push_back((unsigned char)std::strtoul(t,nullptr,16));}
 return v;
}
static std::string tohex(const unsigned char* h, int n=32){
 char b[3];std::string s;for(int i=0;i<n;i++){std::snprintf(b,3,"%02x",h[i]);s+=b;}return s;
}
static std::string hash_once(const std::vector<unsigned char>&key,const std::vector<unsigned char>&inp){
 auto*c=randomx_alloc_cache(RANDOMX_FLAG_DEFAULT);if(!c)std::exit(10);
 randomx_init_cache(c,key.data(),key.size());
 auto*v=randomx_create_vm(RANDOMX_FLAG_DEFAULT,c,nullptr);if(!v)std::exit(11);
 std::array<unsigned char,32> h{};randomx_calculate_hash(v,inp.data(),inp.size(),h.data());
 randomx_destroy_vm(v);randomx_release_cache(c);return tohex(h.data());
}
int main(int argc,char**argv) {
 if(argc<2)return 2;
 if(std::strcmp(argv[1],"vectors")==0) {
 struct Test { const char*key;const char*input;const char*expected;bool inputhex;};
 const Test tests[]={
 {"test key 000","This is a test","639183aae1bf4c9a35884cb46b09cad9175f04efd7684e7262a0ac1c2f0b4e3f",false},
 {"test key 000","Lorem ipsum dolor sit amet","300a0adb47603dedb42228ccb2b211104f4da45af709cd7547cd049e9489c969",false},
 {"test key 000","sed do eiusmod tempor incididunt ut labore et dolore magna aliqua","c36d4ed4191e617309867ed66a443be4075014e2b061bcdaf9ce7b721d2b77a8",false},
 {"test key 001","sed do eiusmod tempor incididunt ut labore et dolore magna aliqua","e9ff4503201c0c2cca26d285c93ae883f9b1d30c9eb240b820756f2d5a7905fc",false},
 {"test key 001","0b0b98bea7e805e0010a2126d287a2a0cc833d312cb786385a7c2f9de69d25537f584a9bc9977b00000000666fd8753bf61a8631f12984e3fd44f4014eca629276817b56f32e9b68bd82f416","c56414121acda1713c2f2a819d8ae38aed7c80c35c2a769298d34f03833cd5f1",true}};
 int ok=0;for(const auto&t:tests){auto k=std::vector<unsigned char>(t.key,t.key+strlen(t.key));auto in=t.inputhex?hex(t.input):std::vector<unsigned char>(t.input,t.input+strlen(t.input));auto actual=hash_once(k,in);if(actual!=t.expected){std::cerr<<"FAIL EXPECTED="<<t.expected<<" ACTUAL="<<actual<<"\n";return 15;}++ok;}std::cout<<"OFFICIAL_VECTORS_OK="<<ok<<"\n";return 0;
 }
 if(std::strcmp(argv[1],"bench")!=0)return 2;
 const unsigned n=argc>=3?(unsigned)std::atoi(argv[2]):64;
 if(n==0||n>10000)return 3;
 const std::string seed="NEXIS-RX-REFERENCE-SEED-V01";
 auto* c=randomx_alloc_cache(RANDOMX_FLAG_DEFAULT);if(!c)return 10;
 randomx_init_cache(c,seed.data(),seed.size());
 auto* v=randomx_create_vm(RANDOMX_FLAG_DEFAULT,c,nullptr);if(!v)return 11;
 std::array<unsigned char,76> blob{};for(size_t i=0;i<blob.size();i++)blob[i]=(i*19+31)&255;
 for(unsigned i=0;i<3;i++){write_nonce(blob.data()+39,0x9e3779b9u*(i+1)+0x12345678u);unsigned char h[32];randomx_calculate_hash(v,blob.data(),blob.size(),h);}
 std::vector<std::array<unsigned char,32>> hashes(n);
 auto a=std::chrono::steady_clock::now();
 for(unsigned i=0;i<n;i++){write_nonce(blob.data()+39,0x9e3779b9u*(i+1)+0x12345678u);randomx_calculate_hash(v,blob.data(),blob.size(),hashes[i].data());}
 auto b=std::chrono::steady_clock::now();
 double sec=std::chrono::duration<double>(b-a).count();
 for(unsigned i=0;i<n;i++)std::printf("H|%u|%s\n",i,tohex(hashes[i].data()).c_str());
 std::printf("METRIC|%u|%.9f|%.6f\n",n,sec,n/sec);
 randomx_destroy_vm(v);randomx_release_cache(c);return 0;
}