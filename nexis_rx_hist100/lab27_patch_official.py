# Live write-back patch only. Official RandomX remains the hash oracle.
from pathlib import Path
import sys
base=Path(sys.argv[1])
def once(s,a,b):
    if s.count(a)!=1:raise RuntimeError((a,s.count(a)))
    return s.replace(a,b)
bc=base/"src/bytecode_machine.hpp"
s=bc.read_text()
s=once(s,"namespace randomx {",'''extern "C" const void* nexis27_read_ptr(uint8_t*,const void*);
extern "C" void nexis27_istore(uint8_t*,uint8_t*,uint64_t);
extern "C" void nexis27_flush(uint8_t*);
namespace randomx {''')
s=once(s,"return scratchpad + addr;", "return const_cast<void*>(nexis27_read_ptr(scratchpad,scratchpad+addr));")
s=once(s,"store64(scratchpad + ((*ibc.idst + ibc.imm) & ibc.memMask), *ibc.isrc);",
        "nexis27_istore(scratchpad,scratchpad + ((*ibc.idst + ibc.imm) & ibc.memMask), *ibc.isrc);")
bc.write_text(s)
vm=base/"src/vm_interpreted.cpp"
s=vm.read_text()
s=once(s,"executeBytecode(bytecode, scratchpad, config);",
       "executeBytecode(bytecode, scratchpad, config);\n            nexis27_flush(scratchpad);")
vm.write_text(s)
print("NEXIS27_ONLINE_WRITEBACK_OFFICIAL_VM_PATCH=PASS")
