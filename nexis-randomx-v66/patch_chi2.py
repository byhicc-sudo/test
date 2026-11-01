#!/usr/bin/env python3
"""V66 ideal chi2/SFG optical-phase-product substitute for RandomX v1.2.3 light VM.
Each bit uses 0/pi phase. In xor3, E1=EA*EB then E2=E1*EC;
no measurement/phase restoration between those TWO simulated nonlinear stages.
Terminal phase detection to return binary bits is still required, as are
optical modulation, pumps, wavelength matching, and memory/CPU interfaces.
"""
from pathlib import Path
import sys

vm=Path(sys.argv[1] if len(sys.argv)>1 else "upstream-randomx/src/vm_interpreted.cpp")
light=vm.with_name("vm_interpreted_light.cpp")
header=vm.with_name("nexis_v66_chi2_proxy.hpp")
def one(src,old,new,label):
    n=src.count(old)
    if n!=1:raise RuntimeError(f"anchor {label}: {n}")
    return src.replace(old,new,1)

header.write_text(r'''#pragma once
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
namespace randomx {
struct NexisV66Stats {
 uint64_t iterations=0, dual_calls=0, triple_calls=0;
 uint64_t nonlinear_mix_bits=0, terminal_detect_bits=0, errors=0;
 uint64_t scratchpad_calls=0, dataset_calls=0, address_calls=0;
 uint64_t sampled_dataset=0, sampled_address=0;
};
extern NexisV66Stats nexis_v66;
extern unsigned nexis_v66_run, nexis_v66_iter;
inline std::complex<double> nexis_phase(unsigned bit) {
 return bit ? std::complex<double>(-1.0,0.0) : std::complex<double>(1.0,0.0);
}
// Ideal 2-input chi2 mixer. The output is detected ONCE at VM register boundary.
inline uint64_t nexis_chi2_xor2(uint64_t a,uint64_t b,unsigned width) {
 uint64_t out=0;
 for(unsigned i=0;i<width;++i) {
   const auto field=nexis_phase((a>>i)&1u)*nexis_phase((b>>i)&1u);
   out |= uint64_t(field.real()<0.0)<<i;
 }
 ++nexis_v66.dual_calls;
 nexis_v66.nonlinear_mix_bits+=width;
 nexis_v66.terminal_detect_bits+=width;
 const uint64_t mask=width==64 ? ~uint64_t(0):((uint64_t(1)<<width)-1);
 nexis_v66.errors+=((out&mask)!=((a^b)&mask));
 return out;
}
// 3-input network: two coherent nonlinear interactions, no detection between.
inline uint64_t nexis_chi2_xor3(uint64_t a,uint64_t b,uint64_t c,unsigned width) {
 uint64_t out=0;
 for(unsigned i=0;i<width;++i) {
   const auto field1=nexis_phase((a>>i)&1u)*nexis_phase((b>>i)&1u);
   const auto field2=field1*nexis_phase((c>>i)&1u);
   out |= uint64_t(field2.real()<0.0)<<i;
 }
 ++nexis_v66.triple_calls;
 nexis_v66.nonlinear_mix_bits+=2*width;
 nexis_v66.terminal_detect_bits+=width;
 const uint64_t mask=width==64 ? ~uint64_t(0):((uint64_t(1)<<width)-1);
 nexis_v66.errors+=((out&mask)!=((a^b^c)&mask));
 return out;
}
inline void nexis_v66_finish() {
 std::fprintf(stderr,
  "V66_SUMMARY|runs=%u|iterations=%llu|dual_calls=%llu|triple_calls=%llu|nonlinear_mix_bits=%llu|terminal_detect_bits=%llu|errors=%llu|scratchpad_calls=%llu|dataset_calls=%llu|address_calls=%llu|sampled_dataset=%llu|sampled_address=%llu\n",
  nexis_v66_run,(unsigned long long)nexis_v66.iterations,
  (unsigned long long)nexis_v66.dual_calls,(unsigned long long)nexis_v66.triple_calls,
  (unsigned long long)nexis_v66.nonlinear_mix_bits,(unsigned long long)nexis_v66.terminal_detect_bits,
  (unsigned long long)nexis_v66.errors,(unsigned long long)nexis_v66.scratchpad_calls,
  (unsigned long long)nexis_v66.dataset_calls,(unsigned long long)nexis_v66.address_calls,
  (unsigned long long)nexis_v66.sampled_dataset,(unsigned long long)nexis_v66.sampled_address);
 unsigned pass=0;
 for(unsigned a=0;a<2;++a)for(unsigned b=0;b<2;++b)for(unsigned c=0;c<2;++c){
  const auto e1=nexis_phase(a)*nexis_phase(b);
  const auto e2=e1*nexis_phase(c);
  pass+=unsigned(e2.real()<0.0)==(a^b^c);
 }
 std::fprintf(stderr,"V66_COHERENT_CHI2_XOR3|pass=%u|total=8|interstage_detection=0|interstage_regeneration=0\n",pass);
}
}
''',encoding='utf-8')

s=vm.read_text(encoding='utf-8')
s=one(s,'#include <iostream>','#include <iostream>\n#include "nexis_v66_chi2_proxy.hpp"','vm include')
s=one(s,'namespace randomx {\n',"""namespace randomx {
NexisV66Stats nexis_v66;
unsigned nexis_v66_run=0, nexis_v66_iter=0;
""",'vm globals')
s=one(s,'VmBase<Allocator, softAes>::generateProgram(seed);',"""if (++nexis_v66_run == 1) std::atexit(nexis_v66_finish);
        VmBase<Allocator, softAes>::generateProgram(seed);""",'vm run')
s=one(s,'uint64_t spMix = nreg.r[config.readReg0] ^ nreg.r[config.readReg1];',"""++nexis_v66.iterations;
            nexis_v66_iter=ic;
            const uint64_t optAddr0=nexis_chi2_xor3(spAddr0,nreg.r[config.readReg0],nreg.r[config.readReg1],32);
            const uint64_t optAddr1=nexis_chi2_xor3(spAddr1,
                nreg.r[config.readReg0]>>32,nreg.r[config.readReg1]>>32,32);
            nexis_v66.address_calls+=2;""",'vm address operation')
s=one(s,'spAddr0 ^= spMix;','spAddr0=(uint32_t)optAddr0;','vm spAddr0')
s=one(s,'spAddr1 ^= spMix >> 32;',"""spAddr1=(uint32_t)optAddr1;
            if(ic==0 || ic==1 || ic==2 || ic==1023 || ic==2047) {
                ++nexis_v66.sampled_address;
                std::fprintf(stderr,"V66_ADDRESS|run=%u|iter=%u|addr0=%08x|addr1=%08x\\n",
                    nexis_v66_run,ic,spAddr0,spAddr1);
            }""",'vm spAddr1')
s=one(s,'nreg.r[i] ^= load64(scratchpad + spAddr0 + 8 * i);',"""{
                 nreg.r[i]=nexis_chi2_xor2(nreg.r[i],load64(scratchpad+spAddr0+8*i),64);
                 ++nexis_v66.scratchpad_calls;
              }""",'vm scratchpad')
s=one(s,'mem.mx ^= nreg.r[config.readReg2] ^ nreg.r[config.readReg3];',"""mem.mx=(uint32_t)nexis_chi2_xor3(mem.mx,nreg.r[config.readReg2],nreg.r[config.readReg3],32);
            ++nexis_v66.address_calls;""",'vm mem.mx')
vm.write_text(s,encoding='utf-8')

s=light.read_text(encoding='utf-8')
s=one(s,'#include "dataset.hpp"','#include "dataset.hpp"\n#include "nexis_v66_chi2_proxy.hpp"','light include')
s=one(s,'for (unsigned q = 0; q < 8; ++q)\n\t\t\tr[q] ^= rl[q];',"""const uint64_t input0=r[0], data0=rl[0];
        for(unsigned q=0;q<8;++q) {
            r[q]=nexis_chi2_xor2(r[q],rl[q],64);
            ++nexis_v66.dataset_calls;
        }
        if(nexis_v66_iter==0 || nexis_v66_iter==1 || nexis_v66_iter==2 ||
           nexis_v66_iter==1023 || nexis_v66_iter==2047) {
            ++nexis_v66.sampled_dataset;
            std::fprintf(stderr,
                "V66_DATASET|run=%u|iter=%u|item=%u|before=%016llx|data=%016llx|after=%016llx\\n",
                nexis_v66_run,nexis_v66_iter,itemNumber,
                (unsigned long long)input0,(unsigned long long)data0,(unsigned long long)r[0]);
        }""",'light dataset xor')
light.write_text(s,encoding='utf-8')
print('V66_PATCH_PASS: 3-input two-stage coherent ideal chi2 proxy + scratchpad and dataset XOR')
