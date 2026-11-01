#!/usr/bin/env python3
"""V65: substitute selected RandomX v1.2.3 chained XORs with ideal photonic MZI simulation.
Not an optical computer. Detector threshold and new phase encoding are assumed at each gate.
"""
from pathlib import Path
import sys
vm = Path(sys.argv[1] if len(sys.argv)>1 else 'upstream-randomx/src/vm_interpreted.cpp')
light = vm.with_name('vm_interpreted_light.cpp')
header = vm.with_name('nexis_v65_ideal_optics.hpp')
def one(s,old,new,label):
    n=s.count(old)
    if n!=1: raise RuntimeError('%s anchor count=%d'%(label,n))
    return s.replace(old,new,1)
header.write_text(r'''#pragma once
#include <cstdint>
#include <cstdio>
#include <cstdlib>
namespace randomx {
struct NexisV65Stats {
    uint64_t iterations = 0, calls = 0, bits = 0, errors = 0;
    uint64_t address_calls = 0, scratchpad_calls = 0, dataset_calls = 0, memory_mix_calls = 0;
    uint64_t regeneration_bits = 0;
    uint64_t dataset_samples = 0, address_samples = 0;
};
extern NexisV65Stats nexis_v65;
extern unsigned nexis_run;
extern unsigned nexis_iter;
inline uint64_t nexis_mzi_xor(uint64_t a, uint64_t b, unsigned bits) {
    uint64_t output=0;
    for(unsigned bit=0; bit<bits; ++bit) {
        const double pa=((a>>bit)&1u)?-1.0:1.0;
        const double pb=((b>>bit)&1u)?-1.0:1.0;
        const double dark=0.5*(pa-pb);
        const double power=dark*dark;
        output|=uint64_t(power>0.5)<<bit;
    }
    const uint64_t mask=(bits==64)?~uint64_t(0):((uint64_t(1)<<bits)-1);
    nexis_v65.calls++;
    nexis_v65.bits+=bits;
    nexis_v65.errors+=((output&mask)!=((a^b)&mask));
    return output;
}
inline void nexis_finish() {
    std::fprintf(stderr,
        "V65_SUMMARY|runs=%u|iterations=%llu|calls=%llu|bits=%llu|errors=%llu"
        "|address_calls=%llu|scratchpad_calls=%llu|dataset_calls=%llu|memory_mix_calls=%llu"
        "|regeneration_bits=%llu|dataset_samples=%llu|address_samples=%llu\n",
        nexis_run, (unsigned long long)nexis_v65.iterations,
        (unsigned long long)nexis_v65.calls, (unsigned long long)nexis_v65.bits,
        (unsigned long long)nexis_v65.errors, (unsigned long long)nexis_v65.address_calls,
        (unsigned long long)nexis_v65.scratchpad_calls, (unsigned long long)nexis_v65.dataset_calls,
        (unsigned long long)nexis_v65.memory_mix_calls, (unsigned long long)nexis_v65.regeneration_bits,
        (unsigned long long)nexis_v65.dataset_samples,(unsigned long long)nexis_v65.address_samples);
    unsigned direct=0, regenerated=0;
    for(unsigned a=0;a<2;a++)for(unsigned b=0;b<2;b++)for(unsigned c=0;c<2;c++){
        const double pa=a?-1.:1., pb=b?-1.:1., pc=c?-1.:1.;
        const double raw=(pa-pb)/2.;
        const unsigned d=unsigned((((raw-pc)/2.)*((raw-pc)/2.))>0.5);
        const unsigned first=unsigned(raw*raw>0.5);
        const double restored=first?-1.:1.;
        const unsigned e=unsigned((((restored-pc)/2.)*((restored-pc)/2.))>0.5);
        direct+=(d==(a^b^c)); regenerated+=(e==(a^b^c));
    }
    std::fprintf(stderr,"V65_COHERENCE|raw_cascade=%u/8|regenerated_cascade=%u/8\n",direct,regenerated);
}
}
''',encoding='utf-8')

s=vm.read_text(encoding='utf-8')
s=one(s,'#include <iostream>','#include <iostream>\n#include "nexis_v65_ideal_optics.hpp"','VM include')
s=one(s,'namespace randomx {\n',
'''namespace randomx {
NexisV65Stats nexis_v65;
unsigned nexis_run=0, nexis_iter=0;
''','VM globals')
s=one(s,'VmBase<Allocator, softAes>::generateProgram(seed);',
'''if (++nexis_run == 1) std::atexit(nexis_finish);
        VmBase<Allocator, softAes>::generateProgram(seed);''','VM run')
s=one(s,'uint64_t spMix = nreg.r[config.readReg0] ^ nreg.r[config.readReg1];',
'''++nexis_v65.iterations;
            nexis_iter=ic;
            const uint64_t spMix=nexis_mzi_xor(nreg.r[config.readReg0],nreg.r[config.readReg1],64);
            ++nexis_v65.address_calls;
            nexis_v65.regeneration_bits += 64; // detector and phase re-encoding before address XOR''','VM address step1')
s=one(s,'spAddr0 ^= spMix;',
'''spAddr0=(uint32_t)nexis_mzi_xor(spAddr0,spMix,32);
            ++nexis_v65.address_calls;''','VM address step2')
s=one(s,'spAddr1 ^= spMix >> 32;',
'''spAddr1=(uint32_t)nexis_mzi_xor(spAddr1,spMix>>32,32);
            ++nexis_v65.address_calls;
            if (ic==0 || ic==1 || ic==2 || ic==1023 || ic==2047) {
                ++nexis_v65.address_samples;
                std::fprintf(stderr,"V65_ADDRESS|run=%u|iter=%u|spmix=%016llx|addr0=%08x|addr1=%08x\\n",
                    nexis_run,ic,(unsigned long long)spMix,spAddr0,spAddr1);
            }''','VM address step3')
s=one(s,'nreg.r[i] ^= load64(scratchpad + spAddr0 + 8 * i);',
'''{ nreg.r[i]=nexis_mzi_xor(nreg.r[i],load64(scratchpad+spAddr0+8*i),64);
                  ++nexis_v65.scratchpad_calls; }''','VM scratchpad XOR')
s=one(s,'mem.mx ^= nreg.r[config.readReg2] ^ nreg.r[config.readReg3];',
'''const uint64_t addrMix=nexis_mzi_xor(nreg.r[config.readReg2],nreg.r[config.readReg3],64);
            ++nexis_v65.memory_mix_calls;
            nexis_v65.regeneration_bits+=64;
            mem.mx=(uint32_t)nexis_mzi_xor(mem.mx,addrMix,32);
            ++nexis_v65.memory_mix_calls;''','VM memory-address XOR')
vm.write_text(s,encoding='utf-8')
s=light.read_text(encoding='utf-8')
s=one(s,'#include "dataset.hpp"','#include "dataset.hpp"\n#include "nexis_v65_ideal_optics.hpp"','light include')
s=one(s,'for (unsigned q = 0; q < 8; ++q)\n\t\t\tr[q] ^= rl[q];',
'''uint64_t firstBefore=r[0], firstData=rl[0];
        for(unsigned q=0;q<8;++q){
            r[q]=nexis_mzi_xor(r[q],rl[q],64);
            ++nexis_v65.dataset_calls;
        }
        if(nexis_iter==0 || nexis_iter==1 || nexis_iter==2 ||
           nexis_iter==1023 || nexis_iter==2047){
            ++nexis_v65.dataset_samples;
            std::fprintf(stderr,
                "V65_DATASET|run=%u|iter=%u|item=%u|before=%016llx|data=%016llx|after=%016llx\\n",
                nexis_run,nexis_iter,itemNumber,
                (unsigned long long)firstBefore,(unsigned long long)firstData,
                (unsigned long long)r[0]);
        }''','light XOR')
light.write_text(s,encoding='utf-8')
print('V65_PATCH_PASS: chained address XOR + scratchpad XOR + dataset XOR')
