#!/usr/bin/env python3
import time, math, random, numpy as np
import quimb.tensor as qtn
from sigma_sparse_trellis_v20 import build_trellis, sigma_ref

def direct_mps(kind):
    order,cols,layers,trans=build_trellis(kind)
    maps=[{s:i for i,s in enumerate(layer)} for layer in layers]
    arrays=[]
    total_entries=0
    for k,edges in enumerate(trans):
        L=len(layers[k]); R=len(layers[k+1])
        if k==0:
            A=np.zeros((R,2),dtype=np.float64)
            for a,b,x in edges: A[maps[k+1][b],x]=1.0
            A *= 2**-16
        elif k==63:
            A=np.zeros((L,2),dtype=np.float64)
            for a,b,x in edges: A[maps[k][a],x]=1.0
        else:
            A=np.zeros((L,R,2),dtype=np.float64)
            for a,b,x in edges: A[maps[k][a],maps[k+1][b],x]=1.0
        total_entries += A.size
        arrays.append(A)
    psi=qtn.MatrixProductState(arrays,shape='lrp')
    return psi,order,total_entries

def decode(bits,order):
    e=s=0
    for site,v in enumerate(order):
        b=int(bits[site])
        if v<32: e |= b<<v
        else: s |= b<<(v-32)
    return e,s

def run(kind):
    print('===',kind.upper(),'DIRECT TRELLIS MPS ===',flush=True)
    t0=time.time()
    psi,order,entries=direct_mps(kind)
    build=time.time()-t0
    print('sites',psi.L,flush=True)
    print('max_bond',psi.max_bond(),flush=True)
    print('dense_entries',entries,flush=True)
    print('dense_MiB_float64',entries*8/(1024**2),flush=True)
    print('build_seconds',build,flush=True)
    t1=time.time(); n=float(np.real(psi.norm())); nt=time.time()-t1
    print('norm',format(n,'.16g'),'norm_seconds',nt,flush=True)
    assert abs(n-1)<1e-10
    rng=random.Random(202620)
    # Exact amplitude check for random valid and invalid computational configurations.
    for j in range(16):
        e=rng.getrandbits(32); s=sigma_ref(e,kind)
        bits=['0']*64
        for site,v in enumerate(order):
            bits[site]=str((e>>v)&1) if v<32 else str((s>>(v-32))&1)
        amp=complex(psi.amplitude(''.join(bits)))
        assert abs(amp-(2**-16))<1e-12,(j,amp)
        # flip one S bit => amplitude zero
        sf=s^(1<<(j&31))
        for site,v in enumerate(order):
            bits[site]=str((e>>v)&1) if v<32 else str((sf>>(v-32))&1)
        bad=complex(psi.amplitude(''.join(bits)))
        assert abs(bad)<1e-12,(j,bad)
    print('amplitude_checks 16 valid+16 invalid PASS',flush=True)
    print(kind.upper()+'_DIRECT_MPS=PASS',flush=True)

run('sigma1')
run('sigma0')
print('V20_DIRECT_SIGMA_MPS=PASS',flush=True)
