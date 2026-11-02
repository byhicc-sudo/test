# Instrument only the RandomX interpreted bytecode compilation boundary.
# The independent reference call uses nexis28_active=false (no change).
from pathlib import Path
import sys
p=Path(sys.argv[1])/"src/vm_interpreted.cpp"
s=p.read_text()
anchor='#include "vm_interpreted.hpp"'
assert s.count(anchor)==1
s=s.replace(anchor,anchor+'\nextern "C" void nexis28_optimize(randomx::InstructionByteCode*, unsigned);')
anchor='compileProgram(program, bytecode, nreg);'
assert s.count(anchor)==1
s=s.replace(anchor,anchor+'\n\t\tnexis28_optimize(bytecode, RANDOMX_PROGRAM_SIZE);')
p.write_text(s)
print("LAB28_PINNED_SOURCE_PATCH=PASS")
