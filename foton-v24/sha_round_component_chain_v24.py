#!/usr/bin/env python3
import math, random, time, numpy as np, sys
import quimb.tensor as qtn
sys.path.insert(0,'foton-v18')
from multisource_mpo_v18 import add_sources_mpo, sub_sources_mpo

MASK=(1<<32)-1
K0=0x428a2f98

def rotr(x,n): return ((x>>n)|(x<<(32-n)))&MASK
def S0(x): return rotr(x,2)^rotr(x,13)^rotr(x,22)
def S1(x): return rotr(x,6)^rotr(x,11)^rotr(x,25)
def ch(x,y,z): return (x&y)^((~x)&z)&MASK
def maj(x,y,z): return (x&y)^(x&z)^(y&z)

def branch_mps_words(branches, nbits_per_site):
    # branches: list of [word0, word1, ...], each local physical bits packed LSB-first.
    m=len(branches); D=1<<nbits_per_site; arrays=[]
    amp=1/math.sqrt(m)
    for i in range(32):
        vals=[]
        for words in branches:
            p=0
            for j,w in enumerate(words):
                p |= ((w>>i)&1)<<j
            vals.append(p)
        if i==0:
            A=np.zeros((m,D),complex)
            for r,p in enumerate(vals): A[r,p]=amp
        elif i==31:
            A=np.zeros((m,D),complex)
            for r,p in enumerate(vals): A[r,p]=1
        else:
            A=np.zeros((m,m,D),complex)
            for r,p in enumerate(vals): A[r,r,p]=1
        arrays.append(A)
    return qtn.MatrixProductState(arrays,shape='lrp')

def overlap(a,b): return complex(a.H @ b)

def local_bool_gate(fn):
    # physical packing [scratch, x, y, z]
    U=np.zeros((16,16),complex)
    for p in range(16):
        s=p&1; x=(p>>1)&1; y=(p>>2)&1; z=(p>>3)&1
        sp=s^fn(x,y,z)
        q=(p&~1)|sp
        U[q,p]=1
    return U

CH=local_bool_gate(lambda e,f,g:(e&f)^((1-e)&g))
MAJ=local_bool_gate(lambda a,b,c:(a&b)^(a&c)^(b&c))

def coherent_local_logic(m, which):
    rng=random.Random(24000+m+(0 if which=='ch' else 100))
    inp=[]; exp=[]
    seen=set()
    while len(inp)<m:
        x,y,z=[rng.getrandbits(32) for _ in range(3)]
        key=(x,y,z)
        if key in seen: continue
        seen.add(key)
        inp.append([0,x,y,z])
        out=ch(x,y,z) if which=='ch' else maj(x,y,z)
        exp.append([out,x,y,z])
    psi=branch_mps_words(inp,4)
    want=branch_mps_words(exp,4)
    U=CH if which=='ch' else MAJ
    t0=time.time()
    for i in range(32):
        psi.gate_(U,i,contract=True)
    sec=time.time()-t0
    ov=abs(overlap(want,psi)); n=float(np.real(psi.norm()))
    print(f'{which.upper()} branches={m} seconds={sec:.6f} bond={psi.max_bond()} norm={n:.16g} overlap={ov:.16g}',flush=True)
    assert abs(n-1)<1e-11 and abs(ov-1)<1e-11
    # self inverse
    for i in range(31,-1,-1):
        psi.gate_(U,i,contract=True)
    back=branch_mps_words(inp,4)
    rv=abs(overlap(back,psi))
    assert abs(rv-1)<1e-11
    print(f'{which.upper()}_{m}_REVERSIBLE=PASS',flush=True)

def coherent_t1(m):
    rng=random.Random(24100+m)
    inp=[]; exp=[]
    seen=set()
    while len(inp)<m:
        e,f,g,h,w=[rng.getrandbits(32) for _ in range(5)]
        key=(e,f,g,h,w)
        if key in seen: continue
        seen.add(key)
        sg=S1(e); cv=ch(e,f,g)
        y=K0
        out=(y+h+sg+cv+w)&MASK
        # packing required by add_sources_mpo: y, src1..src4
        inp.append([y,h,sg,cv,w])
        exp.append([out,h,sg,cv,w])
    psi=branch_mps_words(inp,5)
    want=branch_mps_words(exp,5)
    add=add_sources_mpo(4,32); sub=sub_sources_mpo(4,32)
    t0=time.time()
    out=psi.gate_with_mpo(add,method='zipup',max_bond=256,cutoff=1e-14)
    sec=time.time()-t0
    n=float(np.real(out.norm())); ov=abs(overlap(want,out))
    print(f'T1 branches={m} fwd={sec:.6f}s bond={out.max_bond()} norm={n:.16g} overlap={ov:.16g}',flush=True)
    assert abs(n-1)<2e-10 and abs(ov-1)<2e-10
    t1=time.time()
    back=out.gate_with_mpo(sub,method='zipup',max_bond=256,cutoff=1e-14)
    inv=time.time()-t1
    rv=abs(overlap(psi,back))
    print(f'T1 branches={m} inv={inv:.6f}s restore={rv:.16g} back_bond={back.max_bond()}',flush=True)
    assert abs(rv-1)<3e-10
    print(f'T1_{m}_COHERENT=PASS',flush=True)

def coherent_t2(m):
    rng=random.Random(24200+m)
    inp=[]; exp=[]; seen=set()
    while len(inp)<m:
        a,b,c=[rng.getrandbits(32) for _ in range(3)]
        key=(a,b,c)
        if key in seen: continue
        seen.add(key)
        sg=S0(a); mv=maj(a,b,c)
        out=(sg+mv)&MASK
        inp.append([0,sg,mv])
        exp.append([out,sg,mv])
    psi=branch_mps_words(inp,3)
    want=branch_mps_words(exp,3)
    add=add_sources_mpo(2,32); sub=sub_sources_mpo(2,32)
    t0=time.time()
    out=psi.gate_with_mpo(add,method='zipup',max_bond=256,cutoff=1e-14)
    sec=time.time()-t0
    n=float(np.real(out.norm())); ov=abs(overlap(want,out))
    print(f'T2 branches={m} fwd={sec:.6f}s bond={out.max_bond()} norm={n:.16g} overlap={ov:.16g}',flush=True)
    assert abs(n-1)<2e-10 and abs(ov-1)<2e-10
    back=out.gate_with_mpo(sub,method='zipup',max_bond=256,cutoff=1e-14)
    rv=abs(overlap(psi,back))
    assert abs(rv-1)<3e-10
    print(f'T2_{m}_COHERENT=PASS restore={rv:.16g}',flush=True)

print('=== FOTON V24 SHA ROUND COMPONENT CHAIN ===',flush=True)
print('purpose: photonic tensor-circuit simulation; no brute-force/SAT/SMT/search',flush=True)
for m in (2,4,8):
    coherent_local_logic(m,'ch')
    coherent_local_logic(m,'maj')
    coherent_t1(m)
    coherent_t2(m)
print('V24_SHA_COMPONENT_CHAIN=PASS',flush=True)
