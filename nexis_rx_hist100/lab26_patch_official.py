# LAB26: instrument the pinned upstream RandomX interpreted VM, no algorithm changes.
# C++ hook definitions are linked from lab26_dead_store.cpp.
from pathlib import Path
import sys
base=Path(sys.argv[1])
def replace_one(s, old, new):
    assert s.count(old)==1,(old,s.count(old))
    return s.replace(old,new)
bc=base/"src/bytecode_machine.hpp"
s=bc.read_text()
s=replace_one(s,"namespace randomx {",'''extern "C" const void* nexis26_read_ptr(const uint8_t*, const void*, unsigned);
extern "C" bool nexis26_before_write(const uint8_t*, const void*, unsigned);
namespace randomx {''')
s=replace_one(s,"return scratchpad + addr;",
              "return const_cast<void*>(nexis26_read_ptr(scratchpad,scratchpad+addr,8));")
store="store64(scratchpad + ((*ibc.idst + ibc.imm) & ibc.memMask), *ibc.isrc);"
s=replace_one(s,store,"if(nexis26_before_write(scratchpad,scratchpad + ((*ibc.idst + ibc.imm) & ibc.memMask),8))\n            "+store)
bc.write_text(s)
vm=base/"src/vm_interpreted.cpp"
s=vm.read_text()
a="load64(scratchpad + spAddr0 + 8 * i)"
s=replace_one(s,a,"load64(nexis26_read_ptr(scratchpad,scratchpad + spAddr0 + 8 * i,8))")
for a in ("scratchpad + spAddr1 + 8 * i",
          "scratchpad + spAddr1 + 8 * (RegisterCountFlt + i)"):
    full="rx_cvt_packed_int_vec_f128("+a+")"
    s=replace_one(s,full,"rx_cvt_packed_int_vec_f128(nexis26_read_ptr(scratchpad,"+a+",8))")
a="store64(scratchpad + spAddr1 + 8 * i, nreg.r[i]);"
s=replace_one(s,a,"if(nexis26_before_write(scratchpad,scratchpad + spAddr1 + 8 * i,8))\n             "+a)
a="rx_store_vec_f128((double*)(scratchpad + spAddr0 + 16 * i), nreg.f[i]);"
s=replace_one(s,a,"if(nexis26_before_write(scratchpad,scratchpad + spAddr0 + 16 * i,16))\n             "+a)
vm.write_text(s)
print("LAB26_READ_WRITE_INSTRUMENTATION=OK")
