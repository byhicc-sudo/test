#!/usr/bin/env python3
"""Switch the already-instrumented public v1.2.3 LightVM XOR to ideal MZI output."""
from pathlib import Path
import sys
path=Path(sys.argv[1] if len(sys.argv)>1 else "upstream-randomx/src/vm_interpreted_light.cpp")
s=path.read_text(encoding="utf-8")
needle="""for (unsigned q = 0; q < 8; ++q)
            r[q] ^= rl[q];"""
replace="""for (unsigned q = 0; q < 8; ++q)
            r[q] = nexis_ideal_mzi_xor(r[q], rl[q]);"""
if s.count(needle)!=1: raise RuntimeError("light VM native XOR anchor absent/ambiguous")
s=s.replace(needle,replace,1)
assert s.count(replace)==1 and needle not in s
path.write_text(s,encoding="utf-8")
print("V64_MZI_SUBSTITUTION_PATCH_PASS: native dataset XOR replaced by simulated optical port decision")
