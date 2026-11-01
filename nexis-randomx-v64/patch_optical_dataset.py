#!/usr/bin/env python3
"""Observational ideal optical XOR on real RandomX v1.2.3 light VM dataset reads."""
from pathlib import Path
import sys
vm = Path(sys.argv[1] if len(sys.argv)>1 else "upstream-randomx/src/vm_interpreted.cpp")
light = vm.with_name("vm_interpreted_light.cpp")
def replace_once(s, old, new, label):
    n=s.count(old)
    if n!=1: raise RuntimeError(f"{label}: expected 1 anchor, got {n}")
    return s.replace(old,new,1)
s=vm.read_text(encoding="utf-8")
s=replace_once(s,"namespace randomx {\n",
"""namespace randomx {
unsigned nexis_opt_run = 0;
unsigned nexis_opt_iter = 0;
""","vm globals")
s=replace_once(s,"VmBase<Allocator, softAes>::generateProgram(seed);",
"++nexis_opt_run;\n\t\tVmBase<Allocator, softAes>::generateProgram(seed);","vm run")
s=replace_once(s,"datasetRead(datasetOffset + mem.ma, nreg.r);",
"nexis_opt_iter = ic;\n\t\t\tdatasetRead(datasetOffset + mem.ma, nreg.r);","vm iteration")
vm.write_text(s,encoding="utf-8")
s=light.read_text(encoding="utf-8")
s=replace_once(s,'#include "dataset.hpp"','#include "dataset.hpp"\n#include <cstdio>\n#include <cstdlib>','light includes')
optical=r'''
extern unsigned nexis_opt_run;
extern unsigned nexis_opt_iter;
static unsigned long long nexis_opt_words = 0;
static unsigned long long nexis_opt_bits = 0;
static unsigned long long nexis_opt_errors = 0;
static unsigned nexis_opt_samples = 0;
static void nexis_opt_finish() {
    std::fprintf(stderr,
        "V64_OPTICAL_MZI_SUMMARY|runs=%u|words=%llu|bits=%llu|errors=%llu|samples=%u\n",
        nexis_opt_run, nexis_opt_words, nexis_opt_bits, nexis_opt_errors, nexis_opt_samples);
}
static inline uint64_t nexis_ideal_mzi_xor(uint64_t x, uint64_t y) {
    uint64_t out = 0;
    for (unsigned bit = 0; bit < 64; ++bit) {
        const double amp_a = ((x >> bit) & 1ULL) ? -1.0 : 1.0;
        const double amp_b = ((y >> bit) & 1ULL) ? -1.0 : 1.0;
        const double dark_amplitude = 0.5 * (amp_a - amp_b);
        const double dark_power = dark_amplitude * dark_amplitude;
        out |= uint64_t(dark_power > 0.5) << bit;
    }
    return out;
}
'''
s=replace_once(s,"namespace randomx {\n","namespace randomx {\n"+optical,"light optical model")
s=replace_once(s,"initDatasetItem(cachePtr, (uint8_t*)rl, itemNumber);",
"""initDatasetItem(cachePtr, (uint8_t*)rl, itemNumber);
        static bool nexis_opt_registered = false;
        if (!nexis_opt_registered) {
            std::atexit(nexis_opt_finish);
            nexis_opt_registered = true;
        }
        const uint64_t before0 = r[0], data0 = rl[0];
        uint64_t optical0 = 0;
        for (unsigned q=0;q<8;++q) {
            const uint64_t simulated = nexis_ideal_mzi_xor(r[q], rl[q]);
            if (q == 0) optical0 = simulated;
            ++nexis_opt_words;
            nexis_opt_bits += 64;
            if (simulated != (r[q] ^ rl[q])) ++nexis_opt_errors;
        }""","light probe")
s=replace_once(s,"for (unsigned q = 0; q < 8; ++q)\n\t\t\tr[q] ^= rl[q];",
"""for (unsigned q = 0; q < 8; ++q)
            r[q] ^= rl[q];
        if (nexis_opt_iter==0 || nexis_opt_iter==1 || nexis_opt_iter==2 ||
            nexis_opt_iter==1023 || nexis_opt_iter==2047) {
            ++nexis_opt_samples;
            std::fprintf(stderr,
                "RXOPT|run=%u|iter=%u|item=%u|pre0=%016llx|data0=%016llx|mzi0=%016llx|real0=%016llx\\n",
                nexis_opt_run, nexis_opt_iter, itemNumber,
                (unsigned long long)before0, (unsigned long long)data0,
                (unsigned long long)optical0, (unsigned long long)r[0]);
        }""","light native XOR")
light.write_text(s,encoding="utf-8")
print("V64_PATCH_PASS light-VM dataset observations")
