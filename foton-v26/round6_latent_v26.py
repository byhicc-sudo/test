#!/usr/bin/env python3
import math, random, time, struct, hashlib
import numpy as np
import quimb.tensor as qtn

MASK=(1<<32)-1
IV=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]
K=[
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]

def rotr(x,n): return ((x>>n)|(x<<(32-n)))&MASK
def S0(x): return rotr(x,2)^rotr(x,13)^rotr(x,22)
def S1(x): return rotr(x,6)^rotr(x,11)^rotr(x,25)
def ch(x,y,z): return (x&y)^((~x)&z)&MASK
def maj(x,y,z): return (x&y)^(x&z)^(y&z)
def round_ref(st,w,k):
    a,b,c,d,e,f,g,h=st
    t1=(h+S1(e)+ch(e,f,g)+w+k)&MASK
    t2=(S0(a)+maj(a,b,c))&MASK
    return [(t1+t2)&MASK,a,b,c,(d+t1)&MASK,e,f,g],t1,t2

prefix=hashlib.sha256(b'FOTON-JOB96-CB-PREFIX').digest()[:24]
suffix=hashlib.sha256(b'FOTON-JOB96-CB-SUFFIX').digest()[:24]
pwords=list(struct.unpack('>6I',prefix))
swords=list(struct.unpack('>6I',suffix))
Wfixed=pwords+[None,None]+swords+[0x80000000,0]

st=list(IV)
for t in range(6):
    st,_,_=round_ref(st,Wfixed[t],K[t])
pre6=st[:]
_,t1base,t2base=round_ref(pre6,0,K[6])
# At round6, W6=x enters only additively in t1.
# a6 = x + (t1base+t2base), e6 = x + (pre6[d]+t1base)
CA=(t1base+t2base)&MASK
CE=(pre6[3]+t1base)&MASK

def relation_mps(ca,ce):
    # Each site packs [x, a6, e6] as bit0/bit1/bit2.
    # Bond state = (carry_a, carry_e), 4 states.
    arrays=[]
    amp=2**-16
    for i in range(32):
        ka=(ca>>i)&1; ke=(ce>>i)&1
        first=(i==0); last=(i==31)
        if first:
            A=np.zeros((4,8),float)
            cin_a=cin_e=0
            for x in (0,1):
                sa=x+ka+cin_a; ae=sa&1; coa=sa>>1
                se=x+ke+cin_e; ee=se&1; coe=se>>1
                q=x|(ae<<1)|(ee<<2)
                A[(coa<<1)|coe,q]+=amp
        elif last:
            A=np.zeros((4,8),float)
            for cin in range(4):
                cia=(cin>>1)&1; cie=cin&1
                for x in (0,1):
                    sa=x+ka+cia; ae=sa&1
                    se=x+ke+cie; ee=se&1
                    q=x|(ae<<1)|(ee<<2)
                    A[cin,q]+=1.0
        else:
            A=np.zeros((4,4,8),float)
            for cin in range(4):
                cia=(cin>>1)&1; cie=cin&1
                for x in (0,1):
                    sa=x+ka+cia; ae=sa&1; coa=sa>>1
                    se=x+ke+cie; ee=se&1; coe=se>>1
                    q=x|(ae<<1)|(ee<<2)
                    A[cin,(coa<<1)|coe,q]+=1.0
        arrays.append(A)
    return qtn.MatrixProductState(arrays,shape='lrp')

def bits(x,a,e):
    return ''.join(str(((x>>i)&1)|(((a>>i)&1)<<1)|(((e>>i)&1)<<2)) for i in range(32))

print('=== FOTON V26 REAL JOB ROUND6 LATENT MPS ===',flush=True)
print('free_input_word','W6 / EXTRANONCE2 high32',flush=True)
print('coherent_dimension',2**32,flush=True)
print('pre6_state',[f'{x:08x}' for x in pre6],flush=True)
print('CA',f'{CA:08x}','CE',f'{CE:08x}',flush=True)
t0=time.time(); psi=relation_mps(CA,CE); build=time.time()-t0
print('sites',psi.L,flush=True)
print('physical_dim',8,flush=True)
print('max_bond',psi.max_bond(),flush=True)
entries=sum(int(np.prod(A.shape)) for A in psi.arrays)
print('dense_entries',entries,flush=True)
print('dense_KiB_f64',entries*8/1024,flush=True)
print('build_seconds',build,flush=True)
n=float(np.real(psi.norm()))
print('norm',format(n,'.16g'),flush=True)
assert abs(n-1)<1e-12
rng=random.Random(2606)
for j in range(64):
    x=rng.getrandbits(32)
    a=(x+CA)&MASK; e=(x+CE)&MASK
    amp=complex(psi.amplitude(bits(x,a,e)))
    assert abs(amp-2**-16)<1e-12,(j,amp)
    bad=complex(psi.amplitude(bits(x,a^(1<<(j&31)),e)))
    assert abs(bad)<1e-12,(j,bad)
    rr,_,_=round_ref(pre6,x,K[6])
    assert rr[0]==a and rr[4]==e
print('random_exact_checks','64 valid + 64 invalid PASS',flush=True)
print('hash_round6_reference','PASS',flush=True)
print('V26_ROUND6_LATENT=PASS',flush=True)
