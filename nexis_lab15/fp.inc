// NEXIS LAB16: O(256*8) exact bitwise involution pairing.
// Each program has 8 FP destination register objects: f[0..3], e[0..3].
// The operations FSWAP (lane permutation) and FSCAL (equal XOR mask
// on both lanes) commute bitwise. Two of the same type are identity.
// Barrier at every branch, landing point or FP write into that register.
static void nexisAnswerKeyFP(randomx::InstructionByteCode* ops, randomx::NativeRegisterFile& regs) {
 bool entry[RANDOMX_PROGRAM_SIZE]={};
 for(int k=0;k<RANDOMX_PROGRAM_SIZE;++k){
   if(ops[k].type==InstructionType::CBRANCH){
     const int landing=static_cast<int>(ops[k].target)+1;
     if(landing>=0&&landing<RANDOMX_PROGRAM_SIZE)entry[landing]=true;
   }
 }
 rx_vec_f128* destinations[8]={
   &regs.f[0],&regs.f[1],&regs.f[2],&regs.f[3],
   &regs.e[0],&regs.e[1],&regs.e[2],&regs.e[3]
 };
 int pending[8][2];
 for(int k=0;k<8;k++)for(int t=0;t<2;t++)pending[k][t]=-1;
 auto clearAll=[&](){
   for(int k=0;k<8;k++)for(int t=0;t<2;t++)pending[k][t]=-1;
 };
 for(int i=0;i<RANDOMX_PROGRAM_SIZE;++i) {
   if(entry[i])clearAll();
   auto&op=ops[i];
   if(op.type==InstructionType::CBRANCH){clearAll();continue;}
   bool pairType=op.type==InstructionType::FSCAL_R||op.type==InstructionType::FSWAP_R;
   bool writesFP=pairType ||
       op.type==InstructionType::FADD_R||op.type==InstructionType::FADD_M||
       op.type==InstructionType::FSUB_R||op.type==InstructionType::FSUB_M||
       op.type==InstructionType::FMUL_R||op.type==InstructionType::FDIV_M||
       op.type==InstructionType::FSQRT_R;
   if(!writesFP)continue;
   int k=-1;
   for(int p=0;p<8;++p)if(op.fdst==destinations[p]){k=p;break;}
   if(k<0)continue;
   if(!pairType){
     pending[k][0]=-1;pending[k][1]=-1;continue;
   }
   int t=op.type==InstructionType::FSWAP_R?0:1;
   if(pending[k][t]>=0){
     ops[pending[k][t]].type=InstructionType::NOP;
     op.type=InstructionType::NOP;
     pending[k][t]=-1;
   }else pending[k][t]=i;
 }
}
