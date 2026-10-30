#!/usr/bin/env python3
import time,random,numpy as np
import quimb.tensor as qtn
import sys
sys.path.insert(0,'foton-v20')
from sigma_sparse_trellis_v20 import columns,basis_add,reduce_vec,sigma_ref,SHIFTS

BEST={
"sigma1":[45,41,46,1,20,59,2,25,6,32,15,7,60,11,55,54,33,51,36,28,40,21,29,50,16,14,37,26,12,19,10,58,52,30,56,24,38,63,0,39,5,44,42,49,23,47,18,3,8,13,61,31,57,22,62,53,35,17,43,9,27,34,4,48],
"sigma0":[24,42,54,2,3,23,44,56,0,14,33,25,11,45,32,53,12,34,63,43,1,52,22,13,35,55,26,5,47,16,21,41,36,4,15,10,62,31,50,57,46,61,28,38,17,8,58,19,20,59,40,39,27,51,9,6,7,29,48,60,30,18,49,37]
}

def build(kind):
    order=BEST[kind]; cols=columns(SHIFTS[kind])
    suffix=[None]*65; suffix[64]={}
    for k in range(63,-1,-1):
        suffix[k]=basis_add(suffix[k+1],cols[order[k]])
    layers=[(0,)]; trans=[]; states={0}
    for k,v in enumerate(order):
        fb=suffix[k+1]; col=cols[v]; nxt=set(); edges=[]
        for s in sorted(states):
            for x,ns in ((0,s),(1,s^col)):
                if reduce_vec(fb,ns)==0:
                    nxt.add(ns); edges.append((s,ns,x))
        layers.append(tuple(sorted(nxt))); trans.append(tuple(edges)); states=nxt
    assert states=={0}
    return order,layers,trans

def direct(kind):
    order,layers,trans=build(kind)
    maps=[{s:i for i,s in enumerate(layer)} for layer in layers]
    arrays=[]; entries=0
    for k,edges in enumerate(trans):
        L=len(layers[k]); R=len(layers[k+1])
        if k==0:
            A=np.zeros((R,2),float)
            for a,b,x in edges:A[maps[k+1][b],x]=1.0
            A*=2**-16
        elif k==63:
            A=np.zeros((L,2),float)
            for a,b,x in edges:A[maps[k][a],x]=1.0
        else:
            A=np.zeros((L,R,2),float)
            for a,b,x in edges:A[maps[k][a],maps[k+1][b],x]=1.0
        entries+=A.size; arrays.append(A)
    return qtn.MatrixProductState(arrays,shape='lrp'),order,entries,layers,trans

def bits(e,s,order):
    out=[]
    for v in order:
        out.append(str((e>>v)&1) if v<32 else str((s>>(v-32))&1))
    return ''.join(out)

for kind in ('sigma1','sigma0'):
    print('=== V25',kind.upper(),'OPTIMIZED ORDER ===',flush=True)
    t0=time.time(); psi,order,entries,layers,trans=direct(kind)
    print('build_seconds',time.time()-t0,flush=True)
    print('max_bond',psi.max_bond(),flush=True)
    print('dense_entries',entries,flush=True)
    print('dense_MiB_f64',entries*8/(1024**2),flush=True)
    print('sparse_transitions',sum(len(x) for x in trans),flush=True)
    n=float(np.real(psi.norm()))
    print('norm',format(n,'.16g'),flush=True)
    assert abs(n-1)<1e-10
    rng=random.Random(2500+(kind=='sigma1'))
    for j in range(16):
        e=rng.getrandbits(32); s=sigma_ref(e,kind)
        a=complex(psi.amplitude(bits(e,s,order)))
        bad=complex(psi.amplitude(bits(e,s^(1<<(j&31)),order)))
        assert abs(a-2**-16)<1e-12 and abs(bad)<1e-12
    print('exact_amplitude_checks 16+16 PASS',flush=True)
print('V25_SIGMA_ORDER=PASS',flush=True)
