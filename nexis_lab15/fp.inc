// NEXIS LAB15: FSWAP_R/FSCAL_R bitwise involution pairing
static void nexisAnswerKeyFP(randomx::InstructionByteCode* ops) {
 bool entry[RANDOMX_PROGRAM_SIZE]={};
 for(int k=0;k<RANDOMX_PROGRAM_SIZE;++k){
   if(ops[k].type==InstructionType::CBRANCH){
     int landing=static_cast<int>(ops[k].target)+1;
     if(landing>=0&&landing<RANDOMX_PROGRAM_SIZE)entry[landing]=true;
   }
 }
 for(int i=0;i<RANDOMX_PROGRAM_SIZE;++i){
   auto typ=ops[i].type;
   if(typ!=InstructionType::FSWAP_R&&typ!=InstructionType::FSCAL_R)continue;
   auto*const reg=ops[i].fdst;
   for(int j=i+1;j<RANDOMX_PROGRAM_SIZE;++j){
     if(entry[j]||ops[j].type==InstructionType::CBRANCH)break;
     auto u=ops[j].type;
     if(u==InstructionType::FSWAP_R||u==InstructionType::FSCAL_R){
       if(ops[j].fdst!=reg)continue;
       if(u==typ){ops[i].type=InstructionType::NOP;ops[j].type=InstructionType::NOP;break;}
       continue;
     }
     if(u==InstructionType::FADD_R||u==InstructionType::FADD_M||
        u==InstructionType::FSUB_R||u==InstructionType::FSUB_M||
        u==InstructionType::FMUL_R||u==InstructionType::FDIV_M||
        u==InstructionType::FSQRT_R) {
         if(ops[j].fdst==reg)break;
     }
   }
 }
}
