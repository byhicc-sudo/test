#!/usr/bin/env python3
import math, random, time, inspect, numpy as np
import quimb.tensor as qtn
import sys
sys.path.insert(0,'foton-v20')
sys.path.insert(0,'foton-v21')
from sigma_sparse_trellis_v20 import build_trellis, sigma_ref
from sigma_packed_apply_v21 import apply_packed_sigma, product_bits

def multibranch_mps(words, order):
    m=len(words); n=64
    amps=[1/math.sqrt(m)]*m
    arrays=[]
    bits=[product_bits(e,s,order) for e,s in words]
    for i in range(n):
        if i==0:
            A=np.zeros((m,2),float)
            for r in range(m): A[r,int(bits[r][i])]=amps[r]
        elif i==n-1:
            A=np.zeros((m,2),float)
            for r in range(m): A[r,int(bits[r][i])]=1.0
        else:
            A=np.zeros((m,m,2),float)
            for r in range(m): A[r,r,int(bits[r][i])]=1.0
        arrays.append(A)
    return qtn.MatrixProductState(arrays,shape='lrp')

def compress_mps(mps,max_bond=64,cutoff=1e-14):
    x=mps.copy()
    # prefer native MPS compression
    if hasattr(x,'compress'):
        x.compress(max_bond=max_bond, cutoff=cutoff)
        return x,'mps.compress'
    y=qtn.tensor_network_1d_compress(x,max_bond=max_bond,cutoff=cutoff,method='dm')
    return y,'tensor_network_1d_compress'

def run(m):
    kind='sigma1'
    order,_,_,_=build_trellis(kind)
    rng=random.Random(23000+m)
    words=[]
    seen=set()
    while len(words)<m:
        p=(rng.getrandbits(32),rng.getrandbits(32))
        if p not in seen:
            seen.add(p); words.append(p)
    inp=multibranch_mps(words,order)
    print(f'=== BRANCHES {m} ===',flush=True)
    print('input_bond',inp.max_bond(),'input_norm',float(np.real(inp.norm())),flush=True)
    t0=time.time()
    raw,_,apply_sec,peak=apply_packed_sigma(inp,kind)
    print('raw_apply_seconds',apply_sec,flush=True)
    print('raw_bond',raw.max_bond(),'raw_norm',float(np.real(raw.norm())),flush=True)
    print('raw_peak_MiB_f64',peak*8/(1024**2),flush=True)
    t1=time.time()
    comp,method=compress_mps(raw,max_bond=max(64,m*2),cutoff=1e-14)
    csec=time.time()-t1
    print('compress_method',method,flush=True)
    print('compress_seconds',csec,flush=True)
    print('compressed_bond',comp.max_bond(),flush=True)
    n=float(np.real(comp.norm()))
    print('compressed_norm',format(n,'.16g'),flush=True)
    target=1/math.sqrt(m)
    worst=0.0
    for e,s in words:
        want=product_bits(e,s^sigma_ref(e,kind),order)
        a=complex(comp.amplitude(want))
        worst=max(worst,abs(abs(a)-target))
    print('branch_amp_worst_error',worst,flush=True)
    wrong=list(product_bits(words[0][0],words[0][1]^sigma_ref(words[0][0],kind),order))
    for site,v in enumerate(order):
        if v>=32:
            wrong[site]='1' if wrong[site]=='0' else '0'; break
    bad=abs(complex(comp.amplitude(''.join(wrong))))
    print('wrong_amp_abs',bad,flush=True)
    assert abs(n-1)<1e-9
    assert worst<1e-8
    assert bad<1e-10
    print(f'BRANCH_{m}_COMPRESS=PASS',flush=True)

print('=== FOTON V23 SIGMA COMPRESS ===',flush=True)
for m in (2,4,8):
    run(m)
print('V23_SIGMA_COMPRESS=PASS',flush=True)
