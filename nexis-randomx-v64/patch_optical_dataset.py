#!/usr/bin/env python3
"""Add passive ideal two-rail MZI XOR measurements to pinned RandomX v1.2.3."""
from pathlib import Path
import sys

path = Path(sys.argv[1] if len(sys.argv) > 1 else "upstream-randomx/src/vm_interpreted.cpp")
s = path.read_text(encoding="utf-8")

def put(needle, replacement, label):
    global s
    count = s.count(needle)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, got {count}")
    s = s.replace(needle, replacement, 1)

put("#include <iostream>", "#include <iostream>\n#include <cstdio>\n#include <cstdlib>", "includes")

probe = r'''
// NEXIS V64. Ideal 0/pi phase encoding + 50:50 balanced MZI output.
// Observation only. The official RandomX XOR below remains untouched.
// This is an optical circuit *simulation*, not a physical light measurement.
static unsigned nexis_opt_run_count = 0;
static unsigned nexis_opt_iter = 0;
static unsigned long long nexis_opt_words = 0;
static unsigned long long nexis_opt_bits = 0;
static unsigned long long nexis_opt_errors = 0;
static unsigned nexis_opt_samples = 0;
static void nexis_opt_finish() {
    std::fprintf(stderr,
        "V64_OPTICAL_MZI_SUMMARY|runs=%u|words=%llu|bits=%llu|errors=%llu|samples=%u\n",
        nexis_opt_run_count, nexis_opt_words, nexis_opt_bits,
        nexis_opt_errors, nexis_opt_samples);
}
static inline uint64_t nexis_ideal_mzi_xor(uint64_t x, uint64_t y) {
    uint64_t out = 0;
    for (unsigned bit = 0; bit < 64; ++bit) {
        // optical complex phase values exp(i*pi*b) are +1 or -1
        const double amp_a = ((x >> bit) & 1ULL) ? -1.0 : 1.0;
        const double amp_b = ((y >> bit) & 1ULL) ? -1.0 : 1.0;
        // intensity at antisymmetric output of ideal interferometer
        const double diff = 0.5 * (amp_a - amp_b);
        const double optical_power = diff * diff;
        const bool detector_one = optical_power > 0.5;
        out |= (uint64_t)detector_one << bit;
    }
    return out;
}
'''
put("namespace randomx {\n", "namespace randomx {\n" + probe, "namespace")

put("VmBase<Allocator, softAes>::generateProgram(seed);",
    "if (++nexis_opt_run_count == 1) std::atexit(nexis_opt_finish);\n"
    "\t\tVmBase<Allocator, softAes>::generateProgram(seed);", "run-counter")

put("datasetRead(datasetOffset + mem.ma, nreg.r);",
    "nexis_opt_iter = ic;\n\t\t\tdatasetRead(datasetOffset + mem.ma, nreg.r);",
    "dataset-read-caller")

old = '''\t\tuint64_t* datasetLine = (uint64_t*)(mem.memory + address);
\t\tfor (int i = 0; i < RegistersCount; ++i)
\t\t\tr[i] ^= datasetLine[i];'''
new = r'''\t\tuint64_t* datasetLine = (uint64_t*)(mem.memory + address);
        uint64_t original_r0 = r[0], dataset_r0 = datasetLine[0];
        uint64_t optical_r0 = 0;
        for (int i = 0; i < RegistersCount; ++i) {
            const uint64_t before = r[i];
            const uint64_t word = datasetLine[i];
            const uint64_t light = nexis_ideal_mzi_xor(before, word);
            ++nexis_opt_words;
            nexis_opt_bits += 64;
            if (light != (before ^ word)) ++nexis_opt_errors;
            if (i == 0) optical_r0 = light;
            // The following is the original RandomX operation. Unchanged.
            r[i] ^= datasetLine[i];
        }
        if (nexis_opt_iter == 0 || nexis_opt_iter == 1 ||
            nexis_opt_iter == 2 || nexis_opt_iter == 1023 ||
            nexis_opt_iter == 2047) {
            ++nexis_opt_samples;
            std::fprintf(stderr,
                "RXOPT|run=%u|iter=%u|address=%llu|pre0=%016llx|data0=%016llx|mzi0=%016llx|real0=%016llx\n",
                nexis_opt_run_count, nexis_opt_iter,
                (unsigned long long)address, (unsigned long long)original_r0,
                (unsigned long long)dataset_r0, (unsigned long long)optical_r0,
                (unsigned long long)r[0]);
        }'''
new = new.replace(r'\t\t', '\t\t')
put(old, new, "datasetRead-loop")

path.write_text(s, encoding="utf-8")
print("V64_PATCH_PASS", path)
