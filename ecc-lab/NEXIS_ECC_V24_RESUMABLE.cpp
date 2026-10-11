// NEXIS ECC V24: Resumable Pollard kangaroo on secp256k1 with synthetic/public targets.
// Compile: g++ -O3 -std=c++17 NEXIS_ECC_V24_RESUMABLE.cpp -lcrypto -o nexis_v24
// Usage: ./nexis_v24 --bits 64 --pub 02558650b3abe53dc236f53cc096a3f43ccbbe0c4a23480957608ebb6d1024198b --seconds 10 --checkpoint v24.chk
// Only uses public key. Exact-bit interval assumed [2^(bits-1),2^bits-1].
#include <openssl/ec.h>
#include <openssl/bn.h>
#include <openssl/obj_mac.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>
#include <chrono>
using u128=unsigned __int128;
using clk=std::chrono::steady_clock;
std::string dec(u128 n){if(!n)return "0";std::string s;while(n){s.push_back(char('0'+n%10));n/=10;}std::reverse(s.begin(),s.end());return s;}
u128 parsedec(const std::string &s){u128 v=0;for(char c:s){if(c<'0'||c>'9')throw std::runtime_error("bad u128");v=v*10+(c-'0');}return v;}
std::string hexb(const std::string &b){static const char *h="0123456789abcdef";std::string o;for(unsigned char c:b){o+=h[c>>4];o+=h[c&15];}return o;}
std::string unhex(const std::string &s){if(s.size()%2)throw std::runtime_error("bad hex");std::string o;for(size_t i=0;i<s.size();i+=2){int hi=std::stoi(s.substr(i,1),nullptr,16),lo=std::stoi(s.substr(i+1,1),nullptr,16);o+=char((hi<<4)|lo);}return o;}
uint64_t mix(uint64_t x){x+=0x9e3779b97f4a7c15ULL;x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);}
uint64_t hpoint(const std::string &p,uint64_t salt){uint64_t v=1469598103934665603ULL^salt;for(unsigned char c:p){v^=c;v*=1099511628211ULL;}return mix(v);}
struct EC{
 EC_GROUP* group=EC_GROUP_new_by_curve_name(NID_secp256k1);BN_CTX* ctx=BN_CTX_new();
 EC(){if(!group||!ctx)throw std::runtime_error("bad openssl");}
 ~EC(){EC_GROUP_free(group);BN_CTX_free(ctx);}
 EC_POINT* pt(){auto p=EC_POINT_new(group);if(!p)throw std::runtime_error("bad pt");return p;}
 void mul(EC_POINT *o,uint64_t k){unsigned char bytes[8];for(int i=0;i<8;i++)bytes[7-i]=static_cast<unsigned char>(k>>(8*i));BIGNUM *b=BN_bin2bn(bytes,8,nullptr);int ok=EC_POINT_mul(group,o,b,nullptr,nullptr,ctx);BN_free(b);if(!ok)throw std::runtime_error("multiply failed");}
 void add(EC_POINT *o,const EC_POINT *p){if(!EC_POINT_add(group,o,o,p,ctx))throw std::runtime_error("add failed");}
 std::string enc(EC_POINT *p){unsigned char b[33];size_t k=EC_POINT_point2oct(group,p,POINT_CONVERSION_COMPRESSED,b,33,ctx);if(k!=33)throw std::runtime_error("encode failed");return std::string(reinterpret_cast<char*>(b),33);}
 void decpt(EC_POINT *p,const std::string &s){if(s.size()!=33||!EC_POINT_oct2point(group,p,(const unsigned char*)s.data(),s.size(),ctx))throw std::runtime_error("bad public point");}
 bool eq(EC_POINT *a,EC_POINT *b){return EC_POINT_cmp(group,a,b,ctx)==0;}
};
struct State {
 int bits=0, dpbits=0,r=0;uint64_t salt=0,tame_target=0,tame_steps=0,wild_steps=0;char phase='T';
 u128 tdist=0,wdist=0;std::string pub,tpoint,wpoint;
 std::unordered_map<std::string,u128> table;
};
void save(const std::string &path,const State &s){
 std::string tmp=path+".tmp";std::ofstream f(tmp,std::ios::binary|std::ios::trunc);
 if(!f)throw std::runtime_error("cannot save checkpoint");
 f<<"NEXIS_KANGAROO_V24\n"<<s.bits<<' '<<s.dpbits<<' '<<s.r<<' '<<s.salt<<' '<<s.tame_target<<' '<<s.tame_steps<<' '<<s.wild_steps<<' '<<s.phase<<'\n';
 f<<dec(s.tdist)<<' '<<dec(s.wdist)<<'\n'<<hexb(s.pub)<<'\n'<<hexb(s.tpoint)<<'\n'<<hexb(s.wpoint)<<'\n'<<s.table.size()<<'\n';
 for(const auto &[p,d]:s.table)f<<hexb(p)<<' '<<dec(d)<<'\n';f.close();if(!f)throw std::runtime_error("checkpoint write failed");
 if(std::rename(tmp.c_str(),path.c_str()))throw std::runtime_error("checkpoint rename failed");
}
void load(const std::string &path,State &s){
 std::ifstream f(path,std::ios::binary);std::string line;std::getline(f,line);if(line!="NEXIS_KANGAROO_V24")throw std::runtime_error("incompatible checkpoint");
 f>>s.bits>>s.dpbits>>s.r>>s.salt>>s.tame_target>>s.tame_steps>>s.wild_steps>>s.phase;
 std::string a,b,c;f>>a>>b;s.tdist=parsedec(a);s.wdist=parsedec(b);
 f>>a>>b>>c;s.pub=unhex(a);s.tpoint=unhex(b);s.wpoint=unhex(c);size_t n=0;f>>n;
 for(size_t i=0;i<n;i++){f>>a>>b;s.table.emplace(unhex(a),parsedec(b));}if(!f)throw std::runtime_error("truncated checkpoint");
}
int main(int argc,char **argv){try{
 int bits=32, dpbits=-1;uint64_t seed=1, requested_tame=0,limit=0;double seconds=10.0;
 std::string pub_hex,checkpoint="NEXIS_ECC_V24.chk";
 for(int i=1;i<argc;i++){
  if(i+1==argc)throw std::runtime_error("missing option argument");std::string key=argv[i],v=argv[++i];
  if(key=="--bits")bits=std::stoi(v);else if(key=="--pub")pub_hex=v;else if(key=="--checkpoint")checkpoint=v;
  else if(key=="--seconds")seconds=std::stod(v);else if(key=="--seed")seed=std::stoull(v);
  else if(key=="--dp-bits")dpbits=std::stoi(v);else if(key=="--tame-steps")requested_tame=std::stoull(v);
  else if(key=="--max-steps")limit=std::stoull(v);else throw std::runtime_error("unknown option "+key);
 }
 if(bits<8||bits>64||seconds<=0||pub_hex.size()!=66)throw std::runtime_error("bits 8..64; require compressed --pub 66 hexadecimal characters");
 EC ec;auto *P=ec.pt(),*T=ec.pt(),*W=ec.pt();ec.decpt(P,unhex(pub_hex));
 pub_hex=hexb(ec.enc(P));uint64_t low=1ULL<<(bits-1),high=(bits==64?UINT64_MAX:((1ULL<<bits)-1));
 long double root=sqrtl((long double)(high-low));int r=std::max(3,std::min(62,(int)llround(log2l(root*log2l(root+2)/2))));
 if(dpbits<0)dpbits=(bits<=20?5:(bits<=28?7:(bits<=36?9:12)));
 if(dpbits>24||dpbits<0)throw std::runtime_error("bad dp bits");
 uint64_t tame_target=requested_tame?requested_tame:(uint64_t)ceill(2.5L*root);
 State s;bool resumed=bool(std::ifstream(checkpoint));
 if(resumed){load(checkpoint,s);if(s.bits!=bits||s.pub!=ec.enc(P)||s.dpbits!=dpbits||s.tame_target!=tame_target||s.r!=r||s.salt!=mix(seed))throw std::runtime_error("checkpoint parameters/public key mismatch");
 ec.decpt(T,s.tpoint);ec.decpt(W,s.wpoint);
 }else{
 s.bits=bits;s.pub=ec.enc(P);s.dpbits=dpbits;s.tame_target=tame_target;s.salt=mix(seed);s.r=r;
 ec.mul(T,high);EC_POINT_copy(W,P);s.tpoint=ec.enc(T);s.wpoint=ec.enc(W);
 }
 std::vector<EC_POINT*> jumps;std::vector<uint64_t> sizes;
 for(int j=0;j<s.r;j++){auto *q=ec.pt();uint64_t sz=1ULL<<j;ec.mul(q,sz);jumps.push_back(q);sizes.push_back(sz);}
 uint64_t mask=(1ULL<<s.dpbits)-1,iteration=0;auto start=clk::now();
 std::cout<<"NEXIS_ECC_V24_RESUMABLE\npublic_key="<<pub_hex<<"\nbits="<<bits<<"\nresumed="<<resumed
 <<"\nphase="<<s.phase<<"\ntame_steps_previous="<<s.tame_steps<<"\nwild_steps_previous="<<s.wild_steps
 <<"\ntame_target="<<s.tame_target<<"\nrecords_previous="<<s.table.size()<<"\n"<<std::flush;
 bool solved=false;uint64_t solution=0;
 while(true){
  if(limit&&iteration>=limit)break;
  if((iteration&4095)==0&&std::chrono::duration<double>(clk::now()-start).count()>=seconds)break;
  if(s.phase=='T'){
   std::string enc=ec.enc(T);uint64_t h=hpoint(enc,s.salt);
   if((h&mask)==0)s.table.try_emplace(enc,s.tdist);
   int j=h%s.r;ec.add(T,jumps[j]);s.tdist+=sizes[j];s.tame_steps++;
   if(s.tame_steps>=s.tame_target){s.phase='W';std::cout<<"phase_changed_to_wild after="<<s.tame_steps<<" steps\n"<<std::flush;}
  }else if(s.phase=='W'){
   std::string enc=ec.enc(W);uint64_t h=hpoint(enc,s.salt);
   if((h&mask)==0){auto it=s.table.find(enc);if(it!=s.table.end()){
      u128 left=(u128)high+it->second;
      if(left>=s.wdist){u128 value=left-s.wdist;if(value>=low&&value<=high){auto *Q=ec.pt();ec.mul(Q,(uint64_t)value);if(ec.eq(Q,P)){solved=true;solution=(uint64_t)value;}
        EC_POINT_free(Q);
      }}
   }}
   if(solved){s.phase='S';break;}
   int j=h%s.r;ec.add(W,jumps[j]);s.wdist+=sizes[j];s.wild_steps++;
  }else break;
  iteration++;
 }
 s.tpoint=ec.enc(T);s.wpoint=ec.enc(W);save(checkpoint,s);
 double elapsed=std::chrono::duration<double>(clk::now()-start).count();
 std::cout<<"status="<<(solved?"SOLVED":"PAUSED")<<"\nphase="<<s.phase<<"\nnew_steps="<<iteration
 <<"\ntotal_steps="<<s.tame_steps+s.wild_steps<<"\ntame_steps="<<s.tame_steps<<"\nwild_steps="<<s.wild_steps
 <<"\nrecords="<<s.table.size()<<"\nelapsed_seconds="<<elapsed<<"\ncheckpoint="<<checkpoint<<"\n";
 if(solved)std::cout<<"found_scalar=0x"<<std::hex<<std::uppercase<<solution<<std::dec<<"\nverification=PUBLIC_KEY_MATCH\n";
 for(auto *j:jumps)EC_POINT_free(j);EC_POINT_free(P);EC_POINT_free(T);EC_POINT_free(W);return 0;
 }catch(const std::exception &e){std::cerr<<"ERROR: "<<e.what()<<"\n";return 2;}}