#!/usr/bin/env python3
"""Instrument a pinned, public RandomX v1 reference without changing its computation."""
from pathlib import Path
import sys

source = Path(sys.argv[1] if len(sys.argv)>1 else 'upstream-randomx/src/vm_interpreted.cpp')
s = source.read_text()
probe = r'''
// NEXIS V63: public test vector reference trace, observational only.
static unsigned nexis_rx_run_index = 0;
static unsigned nexis_rx_trace_run = 0;
static void nexis_rx_probe(const char* stage, unsigned iteration,
    const NativeRegisterFile& state, uint32_t sp0, uint32_t sp1) {
    if (nexis_rx_trace_run == 0 ||
        !(iteration < 3 || iteration == 1023 || iteration == 2047)) return;
    std::fprintf(stderr, "RXTRACE|run=%u|iter=%u|stage=%s|sp0=%08x|sp1=%08x|r=",
        nexis_rx_trace_run, iteration, stage, (unsigned)sp0, (unsigned)sp1);
    for (unsigned j=0; j<8; ++j)
        std::fprintf(stderr, "%016llx", (unsigned long long)state.r[j]);
    alignas(16) unsigned char words[16];
    const char* labels[3] = {"f", "e", "a"};
    for (unsigned k=0;k<3;++k) {
        std::fprintf(stderr, "|%s=", labels[k]);
        for (unsigned i=0;i<4;++i) {
            auto v = k==0 ? state.f[i] : (k==1 ? state.e[i] : state.a[i]);
            rx_store_vec_i128(reinterpret_cast<rx_vec_i128*>(words), rx_cast_vec_f2i(v));
            for (unsigned b=0;b<16;++b) std::fprintf(stderr, "%02x", (unsigned)words[b]);
        }
    }
    std::fprintf(stderr, "\n");
}
'''
def inject(needle,replacement,label):
    global s
    count=s.count(needle)
    if count!=1:
        raise RuntimeError(f'{label}: expected one anchor, got {count}')
    s=s.replace(needle,replacement,1)

inject('#include <iostream>','#include <iostream>\n#include <cstdio>', 'include')
inject('namespace randomx {\n','namespace randomx {\n'+probe, 'namespace')
inject('VmBase<Allocator, softAes>::generateProgram(seed);',
    'nexis_rx_trace_run = (++nexis_rx_run_index <= 8) ? nexis_rx_run_index : 0;\n'
    '\t\tVmBase<Allocator, softAes>::generateProgram(seed);', 'run-index')
inject('executeBytecode(bytecode, scratchpad, config);',
    'nexis_rx_probe("before_bytecode", ic, nreg, spAddr0, spAddr1);\n'
    '\t\t\texecuteBytecode(bytecode, scratchpad, config);\n'
    '\t\t\tnexis_rx_probe("after_bytecode", ic, nreg, spAddr0, spAddr1);', 'bytecode')
inject('\t\t\tspAddr0 = 0;\n\t\t\tspAddr1 = 0;',
    '\t\t\tnexis_rx_probe("after_iteration", ic, nreg, spAddr0, spAddr1);\n'
    '\t\t\tspAddr0 = 0;\n\t\t\tspAddr1 = 0;', 'iteration-end')
source.write_text(s)
print('NEXIS_REFERENCE_PATCH_PASS source=' + str(source))
