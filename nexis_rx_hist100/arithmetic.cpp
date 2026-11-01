#include "randomx.h"
#include <boost/multiprecision/cpp_int.hpp>
#include <array>
#include <cctype>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using boost::multiprecision::cpp_int;
using Bytes=std::vector<unsigned char>;
static cpp_int M=(cpp_int(1)<<256);
static cpp_int mod256(cpp_int x){x%=M;if(x<0)x+=M;return x;}
static Bytes unhex(const std::string&s){
 if(s.size()%2)throw std::runtime_error("invalid hex");
 Bytes b;for(size_t i=0;i<s.size();i+=2){auto hexdig=[](char c){
 if(c>='0'&&c<='9') return c-'0';
 if(c>='a'&&c<='f') return c-'a'+10;
 if(c>='A'&&c<='F') return c-'A'+10;
 throw std::runtime_error("bad hex");
 };b.push_back((hexdig(s[i])<<4)|hexdig(s[i+1]));}return b;
}
static cpp_int toint(const Bytes&v){
 cpp_int x=0;for(int i=int(v.size())-1;i>=0;--i){x<<=8;x+=v[i];}return x;
}
static std::vector<std::string> columns(const std::string&line){
 std::vector<std::string>v;std::stringstream s(line);std::string t;while(std::getline(s,t,','))v.push_back(t);return v;
}
static uint64_t read_varint(const Bytes&b,size_t&off){
 uint64_t x=0;unsigned shift=0;while(true){
  if(off>=b.size()||shift>=64)throw std::runtime_error("invalid varint");
  uint8_t c=b[off++];x|=uint64_t(c&127)<<shift;if(!(c&128))return x;shift+=7;
 }
}
static int hamming(const Bytes&a,const Bytes&b){
 int v=0;for(size_t i=0;i<a.size();++i)v+=__builtin_popcount(unsigned(a[i]^b[i]));return v;
}
struct Stat{unsigned matched=0,attempts=0;void test(bool ok){matched+=ok;++attempts;}};
int main(int argc,char**argv){try{
 if(argc!=4)throw std::runtime_error("usage: arithmetic computed100.csv seedhex output.csv");
 Bytes seed=unhex(argv[2]);if(seed.size()!=32)throw std::runtime_error("seed length");
 std::ifstream fin(argv[1]);if(!fin)throw std::runtime_error("input missing");
 std::ofstream fout(argv[3]);if(!fout)throw std::runtime_error("output failed");
 fout<<"height,nonce,timestamp,prev_low64,merkle_low64,H0_low64,H1_low64,H2_low64,D0_low64,D1_low64,affine_n2,quadratic_n3,cubic_n4,geometric_n2,add_nonce_adjacent,add_timestamp_adjacent,mul_nonce_adjacent,diff_times2_n2,adjacent_hamming_mean\n";
 if(mod256(cpp_int(11)-cpp_int(15))!=M-4 || mod256(cpp_int(17)*cpp_int(9))!=153)throw std::runtime_error("mod256 arithmetic self-test failed");
 auto*cache=randomx_alloc_cache(RANDOMX_FLAG_DEFAULT);if(!cache)throw std::runtime_error("cache alloc");
 randomx_init_cache(cache,seed.data(),seed.size());
 auto*vm=randomx_create_vm(RANDOMX_FLAG_DEFAULT,cache,nullptr);if(!vm)throw std::runtime_error("vm alloc");
 Stat affine,quadratic,cubic,geometric,plusNonce,minusNonce,plusTime,plusPrev,plusMerkle,mulNonce,mulTime,mulPrev,delta2,deltaNonce,deltaTime,sharedDelta;
 unsigned long long totalHamming=0;unsigned blocks=0,validated=0;
 cpp_int baselineDelta=0;bool hasBaseline=false;
 std::string line;std::getline(fin,line);
 while(std::getline(fin,line)){
  if(line.empty())continue;
  auto v=columns(line);if(v.size()<9)throw std::runtime_error("bad input row");
  uint64_t height=std::stoull(v[0]);uint32_t nonce=std::stoul(v[1]);Bytes expected=unhex(v[3]);
  Bytes blob=unhex(v[4]);size_t off=0;
  read_varint(blob,off);read_varint(blob,off);
  uint64_t t=read_varint(blob,off);if(off+32+4+32>blob.size())throw std::runtime_error("blob length");
  cpp_int prev=0,merkle=0;for(int k=0;k<8;k++){prev+=cpp_int(blob[off+k])<<(8*k);merkle+=cpp_int(blob[off+32+4+k])<<(8*k);}
  size_t npos=off+32;for(int k=0;k<4;k++){if(blob[npos+k]!=uint8_t(nonce>>(8*k)))throw std::runtime_error("nonce mismatch");}
  std::array<Bytes,5> hs;std::array<cpp_int,5> y;
  for(uint32_t j=0;j<5;j++){
   uint32_t n=nonce+j;for(int k=0;k<4;k++)blob[npos+k]=uint8_t(n>>(8*k));
   hs[j].resize(32);randomx_calculate_hash(vm,blob.data(),blob.size(),hs[j].data());
   y[j]=toint(hs[j]);
  }
  if(hs[0]!=expected)throw std::runtime_error("historical 256-bit hash mismatch "+std::to_string(height));
  validated++;
  cpp_int d0=mod256(y[1]-y[0]),d1=mod256(y[2]-y[1]);
  bool a=mod256(y[1]+d0)==y[2];affine.test(a);
  bool q=mod256(3*y[2]-3*y[1]+y[0])==y[3];quadratic.test(q);
  bool c=mod256(4*y[3]-6*y[2]+4*y[1]-y[0])==y[4];cubic.test(c);
  bool g=mod256(y[0]*y[2])==mod256(y[1]*y[1]);geometric.test(g);
  bool dd=mod256(d0*2)==d1;delta2.test(dd);
  deltaNonce.test(mod256(d0*cpp_int(uint64_t(nonce)))==d1);
  deltaTime.test(mod256(d0*cpp_int(t))==d1);
  if(!hasBaseline){baselineDelta=d0;hasBaseline=true;}
  else sharedDelta.test(d0==baselineDelta);
  int hamSum=0;int plusN=0,plusT=0,mulN=0;
  for(unsigned j=0;j<4;++j){
    auto n=cpp_int(uint64_t(nonce)+j);
    const bool addN=(mod256(y[j]+n)==y[j+1]);plusNonce.test(addN);plusN+=addN;
    minusNonce.test(mod256(y[j]-n)==y[j+1]);
    const bool addT=(mod256(y[j]+t)==y[j+1]);plusTime.test(addT);plusT+=addT;
    plusPrev.test(mod256(y[j]+prev)==y[j+1]);
    plusMerkle.test(mod256(y[j]+merkle)==y[j+1]);
    const bool timesN=(mod256(y[j]*n)==y[j+1]);mulNonce.test(timesN);mulN+=timesN;
    mulTime.test(mod256(y[j]*t)==y[j+1]);
    mulPrev.test(mod256(y[j]*prev)==y[j+1]);
    hamSum+=hamming(hs[j],hs[j+1]);totalHamming+=hamming(hs[j],hs[j+1]);
  }
  cpp_int mask64=(cpp_int(1)<<64)-1;
  auto low=[&](cpp_int x){return (x&mask64).convert_to<uint64_t>();};
  fout<<height<<","<<nonce<<","<<t<<","<<low(prev)<<","<<low(merkle)<<","<<low(y[0])<<","<<low(y[1])<<","<<low(y[2])<<","<<low(d0)<<","<<low(d1)<<","<<a<<","<<q<<","<<c<<","<<g<<","<<plusN<<","<<plusT<<","<<mulN<<","<<dd<<","<<double(hamSum)/4<<"\n";
  if(height==3300100){
    std::cout<<"EXAMPLE height="<<height<<" nonce="<<nonce<<" timestamp="<<t
      <<" prev_low64="<<low(prev)<<" merkle_low64="<<low(merkle)
      <<" h0_low64="<<low(y[0])<<" h1_low64="<<low(y[1])<<" h2_low64="<<low(y[2])
      <<" difference01_low64="<<low(d0)<<" difference12_low64="<<low(d1)<<"\n";
  }
  blocks++;
 }
 randomx_destroy_vm(vm);randomx_release_cache(cache);
 auto print=[](const char*name,Stat s){std::cout<<name<<"="<<s.matched<<"/"<<s.attempts<<"\n";};
 std::cout<<"TESTED_BLOCKS="<<blocks<<" VERIFIED_HISTORICAL_HASHES="<<validated
 <<" EVALUATED_FULL_RANDOMX_HASHES="<<blocks*5<<"\n";
 print("AFFINE_PREDICT_N2",affine);
 print("QUADRATIC_PREDICT_N3",quadratic);
 print("CUBIC_PREDICT_N4",cubic);
 print("GEOMETRIC_MULTIPLICATION_N2",geometric);
 print("DELTA_TIMES_2",delta2);print("DELTA_TIMES_NONCE",deltaNonce);
 print("DELTA_TIMES_TIMESTAMP",deltaTime);
 print("GLOBAL_ADD_DELTA_FROM_FIRST_BLOCK",sharedDelta);
 print("Y_NEXT_EQUALS_Y_PLUS_NONCE",plusNonce);
 print("Y_NEXT_EQUALS_Y_MINUS_NONCE",minusNonce);
 print("Y_NEXT_EQUALS_Y_PLUS_TIMESTAMP",plusTime);
 print("Y_NEXT_EQUALS_Y_PLUS_PREV_LOW64",plusPrev);
 print("Y_NEXT_EQUALS_Y_PLUS_MERKLE_LOW64",plusMerkle);
 print("Y_NEXT_EQUALS_Y_TIMES_NONCE",mulNonce);
 print("Y_NEXT_EQUALS_Y_TIMES_TIMESTAMP",mulTime);
 print("Y_NEXT_EQUALS_Y_TIMES_PREV_LOW64",mulPrev);
 std::cout<<"MEAN_HAMMING_OF_400_ADJACENT_HASH_PAIRS="<<double(totalHamming)/(blocks*4)<<"\n";
 return blocks==100&&validated==100?0:9;
 }catch(const std::exception&e){std::cerr<<"ERROR "<<e.what()<<"\n";return 10;}
}
