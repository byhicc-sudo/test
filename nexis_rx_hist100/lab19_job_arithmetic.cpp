// NEXIS RX LAB19: arithmetic-only hypotheses on 100 real winning Monero jobs
// No mining, no brute force, no synthetic PoW. Inputs are independently
// verified RandomX 256-bit hashes from two real GitHub Actions artifacts.
#include <boost/multiprecision/cpp_int.hpp>
#include <algorithm>
#include <array>
#include <cstdint>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
using boost::multiprecision::cpp_int;
static const cpp_int two256=cpp_int(1)<<256;
struct Row {
 uint32_t nonce=0, time=0, height=0, prev=0, merkle=0, wideDiffLow=0;
 uint32_t win32=0, neighbor32=0;
 cpp_int difficulty, winning, neighbor;
 std::string winningHex;
};
static std::vector<std::string> fields(const std::string&s){
 std::stringstream ss(s);std::string word;std::vector<std::string>v;
 while(std::getline(ss,word,','))v.push_back(word);return v;
}
static unsigned hexdigit(char c){
 if(c>='0'&&c<='9')return unsigned(c-'0');
 if(c>='a'&&c<='f')return unsigned(c-'a'+10);
 if(c>='A'&&c<='F')return unsigned(c-'A'+10);
 throw std::runtime_error("hex invalid");
}
static std::vector<uint8_t> unhex(const std::string&s){
 if(s.size()%2)throw std::runtime_error("odd hex");
 std::vector<uint8_t>r;for(size_t k=0;k<s.size();k+=2)r.push_back(uint8_t((hexdigit(s[k])<<4)|hexdigit(s[k+1])));
 return r;
}
static uint32_t first32(const std::vector<uint8_t>&v,size_t i){
 if(i+4>v.size())throw std::runtime_error("first32 overflow");
 uint32_t o=0;for(unsigned j=0;j<4;j++)o|=uint32_t(v[i+j])<<(8*j);return o;
}
static uint64_t varint(const std::vector<uint8_t>&v,size_t&off){
 uint64_t a=0;for(unsigned k=0;k<10;k++){
 if(off>=v.size())throw std::runtime_error("short varint");
 auto b=v[off++];a|=uint64_t(b&127)<<(7*k);
 if(!(b&128))return a;
 }throw std::runtime_error("invalid varint");
}
static cpp_int decHex(std::string s){
 if(s.size()>1&&s[0]=='0'&&s[1]=='x')s.erase(0,2);
 cpp_int x=0;for(char c:s)x=(x<<4)+hexdigit(c);return x;
}
static cpp_int leInt(const std::vector<uint8_t>&b){
 cpp_int x=0;for(int j=int(b.size())-1;j>=0;--j)x=(x<<8)+b[j];return x;
}
static uint32_t inverseOdd(uint32_t x){
 if(!(x&1))throw std::runtime_error("noninvertible");
 uint32_t a=1;for(int i=0;i<5;i++)a*=uint32_t(2-x*a);return a;
}
using Model=std::pair<std::string,std::function<uint32_t(const Row&)>>;
static std::vector<Model> candidates(){
 return {
 {"timestamp",[&](const Row&r){return r.time;}},
 {"previous32",[&](const Row&r){return r.prev;}},
 {"merkle32",[&](const Row&r){return r.merkle;}},
 {"height",[&](const Row&r){return r.height;}},
 {"difficulty32",[&](const Row&r){return r.wideDiffLow;}},
 {"timestamp+previous32",[](const Row&r){return uint32_t(r.time+r.prev);}},
 {"timestamp+merkle32",[](const Row&r){return uint32_t(r.time+r.merkle);}},
 {"previous32+merkle32",[](const Row&r){return uint32_t(r.prev+r.merkle);}},
 {"timestamp+previous32+merkle32",[](const Row&r){return uint32_t(r.time+r.prev+r.merkle);}},
 {"timestamp-previous32",[](const Row&r){return uint32_t(r.time-r.prev);}},
 {"previous32-merkle32",[](const Row&r){return uint32_t(r.prev-r.merkle);}},
 {"timestamp-merkle32",[](const Row&r){return uint32_t(r.time-r.merkle);}},
 {"previous32*timestamp",[](const Row&r){return uint32_t(r.prev*r.time);}},
 {"merkle32*timestamp",[](const Row&r){return uint32_t(r.merkle*r.time);}},
 {"previous32*merkle32",[](const Row&r){return uint32_t(r.prev*r.merkle);}},
 {"height*timestamp",[](const Row&r){return uint32_t(r.height*r.time);}},
 {"height*previous32",[](const Row&r){return uint32_t(r.height*r.prev);}},
 {"height*merkle32",[](const Row&r){return uint32_t(r.height*r.merkle);}},
 {"previous32*timestamp+merkle32",[](const Row&r){return uint32_t(r.prev*r.time+r.merkle);}},
 {"merkle32*timestamp+previous32",[](const Row&r){return uint32_t(r.merkle*r.time+r.prev);}},
 {"previous32*merkle32+timestamp",[](const Row&r){return uint32_t(r.prev*r.merkle+r.time);}},
 {"timestamp*timestamp+previous32",[](const Row&r){return uint32_t(r.time*r.time+r.prev);}},
 {"height*previous32+merkle32",[](const Row&r){return uint32_t(r.height*r.prev+r.merkle);}},
 {"height+timestamp+previous32",[](const Row&r){return uint32_t(r.height+r.time+r.prev);}}
 };
}
int main(int argc,char**argv){
 try{
 if(argc!=4)throw std::runtime_error("Usage: lab19 compiled100.csv winner_vs_nonceplusone.csv output.tsv");
 std::ifstream f(argc>1?argv[1]:"");if(!f)throw std::runtime_error("cannot open verified winning hashes");
 std::map<unsigned,Row> data;
 std::string line;std::getline(f,line);
 while(std::getline(f,line)){
 if(line.empty())continue;auto z=fields(line);
 if(z.size()<8)throw std::runtime_error("winning CSV columns");
 Row r;r.height=std::stoul(z[0]);r.nonce=std::stoul(z[1]);r.winningHex=z[3];
 auto h=unhex(z[3]);if(h.size()!=32)throw std::runtime_error("bad RandomX 256-bit hash");
 r.winning=leInt(h);r.win32=first32(h,0);
 auto blob=unhex(z[4]);size_t offset=0;
 varint(blob,offset);varint(blob,offset);r.time=uint32_t(varint(blob,offset));
 r.prev=first32(blob,offset);
 r.nonce=std::stoul(z[1]);if(first32(blob,offset+32)!=r.nonce)throw std::runtime_error("nonce not in blob");
 r.merkle=first32(blob,offset+36);
 r.difficulty=decHex(z[6]);r.wideDiffLow=uint32_t(r.difficulty & ((cpp_int(1)<<32)-1));
 if(r.difficulty<=0)throw std::runtime_error("difficulty zero");
 data.emplace(r.height,std::move(r));
 }
 std::ifstream g(argv[2]);if(!g)throw std::runtime_error("missing neighbor hash csv");
 std::getline(g,line);unsigned neighbors=0;
 while(std::getline(g,line)){
 if(line.empty())continue;auto z=fields(line);
 if(z.size()<4)throw std::runtime_error("neighbor CSV columns");
 unsigned h=std::stoul(z[0]);auto it=data.find(h);if(it==data.end())throw std::runtime_error("neighbor height missing");
 auto b=unhex(z[3]);if(b.size()!=32)throw std::runtime_error("bad neighbor hash");
 if(z[2]!=it->second.winningHex)throw std::runtime_error("winner hash discrepancy");
 it->second.neighbor=leInt(b);it->second.neighbor32=first32(b,0);neighbors++;
 }
 std::vector<Row> rows;for(auto& item:data)rows.push_back(item.second);
 if(rows.size()!=100||neighbors!=100)throw std::runtime_error("need exactly 100 winners and neighbors");
 unsigned good=0,badNeighbors=0;const cpp_int top=two256-1;
 for(const auto&r:rows) {
 if(r.winning*r.difficulty<=top)good++;
 if(r.neighbor*r.difficulty>top)badNeighbors++;
 }
 if(good!=100||badNeighbors!=100)throw std::runtime_error("broken PoW target input");
 std::ofstream out(argv[3]);if(!out)throw std::runtime_error("cannot open output");
 out<<"model\tpredicts_nonce_32bit\tmatching_nonce_low8_of100\tpredicts_winner_hash_low32\tpredicts_neighbor_hash_low32\tout_of_sample_nonce_fit_20\tfit_possible\n";
 int modelCount=0,maxExact=0,bestLow8=0,maxHashMatch=0;std::string bestName;
 auto models=candidates();unsigned fittedModels=0,totalFittedCorrect=0;
 for(const auto&m:models){
  int exact=0,low8=0,win=0,neighbor=0;
  for(const auto&r:rows) {
   uint32_t x=m.second(r);
   exact+=(x==r.nonce);
   low8+=((x&255)==(r.nonce&255));
   // Independent output hypothesis: same arithmetic expression predicts 32 low hash bits.
   win+=(x==r.win32);
   neighbor+=(uint32_t(x+1)==r.neighbor32);
  }
  // Fit a*x+b modulo 2^32 using only the first 80 historical blocks.
  // Test strictly on the last 20 blocks (no target or hash from these used in fitting).
  bool fit=false;uint32_t a=0,b=0;int testCorrect=0;
  for(int i=0;i<80&&!fit;++i)
   for(int j=i+1;j<80&&!fit;++j) {
    uint32_t dx=uint32_t(m.second(rows[j])-m.second(rows[i]));
    if(dx&1) {
      uint32_t dy=uint32_t(rows[j].nonce-rows[i].nonce);
      a=uint32_t(dy*inverseOdd(dx));b=uint32_t(rows[i].nonce-a*m.second(rows[i]));
      fit=true;
    }
   }
  if(fit){fittedModels++;for(int k=80;k<100;++k)testCorrect+=(uint32_t(a*m.second(rows[k])+b)==rows[k].nonce);totalFittedCorrect+=testCorrect;}
  maxExact=std::max(maxExact,exact);maxHashMatch=std::max(maxHashMatch,win);
  if(low8>bestLow8){bestLow8=low8;bestName=m.first;}
  out<<m.first<<"\t"<<exact<<"\t"<<low8<<"\t"<<win<<"\t"<<neighbor<<"\t"<<testCorrect<<"\t"<<fit<<"\n";
  modelCount++;
 }
 // Two additional bounded checks directly between historical winner hash
 // and winner nonce. These output arithmetic instead of searching input nonce.
 unsigned eqHashNonce=0,eqHashNoncePlusTime=0,eqHashNonceTimesTime=0,eqHashNoncePlusPrev=0,eqHashNonceTimesPrevPlusMerkle=0;
 unsigned neighborSameDelta=0,neighborPlusNonce=0,neighborTimesNonce=0,neighborPlusTime=0,neighborPlusPrevMerkle=0;
 uint32_t firstDelta=uint32_t(rows[0].neighbor32-rows[0].win32);
 for(const auto&r:rows) {
  eqHashNonce+=(r.win32==r.nonce);
  eqHashNoncePlusTime+=(r.win32==uint32_t(r.nonce+r.time));
  eqHashNonceTimesTime+=(r.win32==uint32_t(r.nonce*r.time));
  eqHashNoncePlusPrev+=(r.win32==uint32_t(r.nonce+r.prev));
  eqHashNonceTimesPrevPlusMerkle+=(r.win32==uint32_t(r.nonce*r.prev+r.merkle));
  neighborSameDelta+=(r.neighbor32==uint32_t(r.win32+firstDelta));
  neighborPlusNonce+=(r.neighbor32==uint32_t(r.win32+r.nonce));
  neighborTimesNonce+=(r.neighbor32==uint32_t(r.win32*r.nonce));
  neighborPlusTime+=(r.neighbor32==uint32_t(r.win32+r.time));
  neighborPlusPrevMerkle+=(r.neighbor32==uint32_t(r.win32+r.prev+r.merkle));
 }
 std::cout<<"INPUT_WINNERS=100 INPUT_REAL_NEIGHBORS=100\n";
 std::cout<<"NETWORK_TARGET_SIMPLE_MULTIPLICATION_CORRECT_WINNERS="<<good<<"/100\n";
 std::cout<<"NETWORK_TARGET_SIMPLE_MULTIPLICATION_REJECTS_NONCE_PLUS_ONE="<<badNeighbors<<"/100\n";
 std::cout<<"TESTED_SIMPLE_JOB_TO_NONCE_MODELS="<<modelCount<<"\n";
 std::cout<<"MAX_EXACT_NONCE_PREDICTIONS="<<maxExact<<"/100\n";
 std::cout<<"BEST_LOW_8_BIT_MATCHES="<<bestLow8<<"/100 model="<<bestName<<" (chance baseline=0.390625/100; multiple comparisons)\n";
 std::cout<<"MAX_EXACT_WINNER_HASH_LOW32_FROM_JOB_FEATURE="<<maxHashMatch<<"/100\n";
 std::cout<<"CALIBRATED_TWO_POINT_AFFINE_MODELS="<<fittedModels<<" TOTAL_HOLDOUT_EXACT_MATCHES="<<totalFittedCorrect<<"/"<<fittedModels*20<<"\n";
 std::cout<<"HASH32_EQ_NONCE="<<eqHashNonce<<"/100 HASH32_EQ_NONCE_PLUS_TIMESTAMP="<<eqHashNoncePlusTime<<"/100\n";
 std::cout<<"HASH32_EQ_NONCE_TIMES_TIMESTAMP="<<eqHashNonceTimesTime<<"/100 HASH32_EQ_NONCE_PLUS_PREV="<<eqHashNoncePlusPrev<<"/100\n";
 std::cout<<"HASH32_EQ_NONCE_TIMES_PREV_PLUS_MERKLE="<<eqHashNonceTimesPrevPlusMerkle<<"/100\n";
 std::cout<<"NEIGHBOR_LOW32_FROM_FIXED_DELTA="<<neighborSameDelta<<"/100 (first winner-neighbor pair used as calibration)\n";
 std::cout<<"NEIGHBOR_LOW32_EQUALS_WIN_PLUS_NONCE="<<neighborPlusNonce<<"/100\n";
 std::cout<<"NEIGHBOR_LOW32_EQUALS_WIN_TIMES_NONCE="<<neighborTimesNonce<<"/100\n";
 std::cout<<"NEIGHBOR_LOW32_EQUALS_WIN_PLUS_TIME="<<neighborPlusTime<<"/100\n";
 std::cout<<"NEIGHBOR_LOW32_EQUALS_WIN_PLUS_PREV_PLUS_MERKLE="<<neighborPlusPrevMerkle<<"/100\n";
 std::cout<<"BLOCK_3300100 nonce="<<rows[0].nonce<<" time="<<rows[0].time
  <<" prev32="<<rows[0].prev<<" merkle32="<<rows[0].merkle
  <<" winner_hash_low32="<<rows[0].win32
  <<" neighbor_hash_low32="<<rows[0].neighbor32
  <<" difficulty_decimal="<<rows[0].difficulty<<"\n";
 return 0;
 }catch(const std::exception&e){std::cerr<<"ERROR "<<e.what()<<"\n";return 1;}
}
