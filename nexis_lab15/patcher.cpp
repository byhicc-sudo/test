#include <fstream>
#include <string>
#include <stdexcept>
#include <iostream>
std::string read(const std::string&p){std::ifstream f(p,std::ios::binary);if(!f)throw std::runtime_error("can't read "+p);return {std::istreambuf_iterator<char>(f),{}};}
void write(const std::string&p,const std::string&s){std::ofstream f(p,std::ios::binary|std::ios::trunc);if(!f)throw std::runtime_error("can't write "+p);f<<s;}
void replace_once(std::string &s,const std::string &a,const std::string&b){
 auto i=s.find(a);if(i==std::string::npos||s.find(a,i+a.size())!=std::string::npos)throw std::runtime_error("anchor missing/not unique");
 s.replace(i,a.size(),b);
}
int main(int argc,char**argv){
 try{
 if(argc!=3)throw std::runtime_error("usage: patcher source-root legacy|alternative");
 std::string root=argv[1],which=argv[2];
 if(which!="legacy"&&which!="alternative")throw std::runtime_error("bad motor");
 std::string path=root+"/src/bytecode_machine.hpp",s=read(path);
 std::string needle="\t\t\t\tcompileInstruction(instr, i, ibc);\n\t\t\t}\n\t\t}\n\n\t\tstatic void executeBytecode";
 std::string repl="\t\t\t\tcompileInstruction(instr, i, ibc);\n\t\t\t}\n\t\t\tnexisReduceBytecode(bytecode);\n\t\t}\n"+read("nexis_lab15/reducer.inc")+"\n\t\tstatic void executeBytecode";
 replace_once(s,needle,repl);write(path,s);
 if(which=="alternative"){
  path=root+"/src/vm_interpreted.cpp";s=read(path);
  replace_once(s,"namespace randomx {\n","#include <cstdlib>\nnamespace randomx {\n"+read("nexis_lab15/fp.inc")+"\n");
  replace_once(s,"\t\tcompileProgram(program, bytecode, nreg);","\t\tcompileProgram(program, bytecode, nreg);\n\t\tif(std::getenv(\"NEXIS_FP_ON\")) nexisAnswerKeyFP(bytecode, nreg);");
  write(path,s);
 }
 std::cout<<"PATCH_OK "<<which<<"\n";
 }catch(const std::exception&e){std::cerr<<"PATCH_FAIL "<<e.what()<<"\n";return 1;}
}
