// NEXIS_RX_SAFE_PASSES_V01: preserve branch positions
static void nexisReduceBytecode(InstructionByteCode bc[RANDOMX_PROGRAM_SIZE]) {
  bool branchEntry[RANDOMX_PROGRAM_SIZE] = {false};
  for(unsigned j=0;j<RANDOMX_PROGRAM_SIZE;++j)
    if(bc[j].type==InstructionType::CBRANCH){
      const int entry=static_cast<int>(bc[j].target)+1;
      if(entry>=0 && entry<RANDOMX_PROGRAM_SIZE)branchEntry[entry]=true;
    }
  for(unsigned j=0;j<RANDOMX_PROGRAM_SIZE;++j){
    auto& op=bc[j];
    if((op.type==InstructionType::IROR_R||op.type==InstructionType::IROL_R)
       &&op.isrc==&op.imm&&(op.imm&63U)==0)op.type=InstructionType::NOP;
  }
  for(unsigned j=0;j+1<RANDOMX_PROGRAM_SIZE;++j){
    if(branchEntry[j+1])continue;
    auto&a=bc[j];auto&b=bc[j+1];
    const bool ax=a.type==InstructionType::IXOR_R&&a.isrc==&a.imm;
    const bool bx=b.type==InstructionType::IXOR_R&&b.isrc==&b.imm;
    if(ax&&bx&&a.idst==b.idst){
      b.imm^=a.imm;b.type=b.imm==0?InstructionType::NOP:InstructionType::IXOR_R;
      a.type=InstructionType::NOP;++j;continue;
    }
    const bool ar=(a.type==InstructionType::IROR_R||a.type==InstructionType::IROL_R)&&a.isrc==&a.imm;
    const bool br=(b.type==InstructionType::IROR_R||b.type==InstructionType::IROL_R)&&b.isrc==&b.imm;
    if(ar&&br&&a.idst==b.idst){
      const unsigned ra=a.type==InstructionType::IROR_R?(a.imm&63U):((64U-(a.imm&63U))&63U);
      const unsigned rb=b.type==InstructionType::IROR_R?(b.imm&63U):((64U-(b.imm&63U))&63U);
      b.imm=(ra+rb)&63U;b.type=b.imm==0?InstructionType::NOP:InstructionType::IROR_R;
      a.type=InstructionType::NOP;++j;
    }
  }
}
