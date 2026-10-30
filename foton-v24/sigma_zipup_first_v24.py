#!/usr/bin/env python3
import math,time,random,resource,numpy as np
import quimb.tensor as qtn
from sigma_sparse_trellis_v20 import build_trellis,sigma_ref

DT=np.float64

def sigma_mpo(kind):
    order,cols,layers,trans=build_trellis(kind)
    maps=[{s:i for i,s in enumerate(layer)} for layer in layers]
    arrays=[]; entries=0
    for k,(v,edges) in enumerate(zip(order,trans)):
        L=len(layers[k]); R=len(layers[k+1])
        if k==0:
            A=np.zeros((R,2,2),dtype=DT)
            for a,b,x in edges:
                rb=maps[k+1][b]
                if v<32:
                    A[rb,x,x]=1.0
                else:
                    A[rb,0^x,0]=1.0; A[rb,1^x,1]=1.0
        elif k==63:
            A=np.zeros((L,2,2),dtype=DT)
            for a,b,x in edges:
                la=maps[k][a]
                if v<32:
                    A[la,x,x]=1.0
                else:
                    A[la,0^x,0]=1.0; A[la,1^x,1]=1.0
        else:
            A=np.zeros((L,R,2,2),dtype=DT)
            for a,b,x in edges:
                la=maps[k][a]; rb=maps[k+1][b]
                if v<32:
                    A[la,rb,x,x]=1.0
                else:
                    A[la,rb,0^x,0]=1.0; A[la,rb,1^x,1]=1.0
        entries+=A.size; arrays.append(A)
    return qtn.MatrixProductOperator(arrays,shape='lrud'),order,entries

def bits_for(e,s,order):
    return ''.join(str((e>>v)&1) if v<32 else str((s>>(v-32))&1) for v in order)

def two_branch(e0,s0,e1,s1,order):
    b0=bits_for(e0,s0,order); b1=bits_for(e1,s1,order)
    arr=[]
    for i in range(64):
        if i==0:
            A=np.zeros((2,2),float); A[0,int(b0[i])]=1/math.sqrt(2); A[1,int(b1[i])]=1/math.sqrt(2)
        elif i==63:
            A=np.zeros((2,2),float); A[0,int(b0[i])]=1; A[1,int(b1[i])]=1
        else:
            A=np.zeros((2,2,2),float); A[0,0,int(b0[i])]=1; A[1,1,int(b1[i])]=1
        arr.append(A)
    return qtn.MatrixProductState(arr,shape='lrp')

print('=== V24 ZIPUP-FIRST SIGMA ===',flush=True)
kind='sigma1'
t0=time.time(); mpo,order,entries=sigma_mpo(kind); build=time.time()-t0
print('mpo_build_seconds',build,flush=True)
print('mpo_bond',mpo.max_bond(),'mpo_MiB',entries*8/(1024**2),flush=True)
print('rss_after_mpo_MiB',resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,flush=True)
rng=random.Random(24024)
e0,s0,e1,s1=[rng.getrandbits(32) for _ in range(4)]
psi=two_branch(e0,s0,e1,s1,order)
print('input_bond',psi.max_bond(),'norm',float(np.real(psi.norm())),flush=True)

for method,opts in [
    ('zipup-first',dict(max_bond=4,max_bond_oversample=8,cutoff=1e-14,cutoff_oversample=1e-14)),
    ('dm',dict(max_bond=4,cutoff=1e-14)),
]:
    t=time.time()
    out=psi.gate_with_mpo(mpo,method=method,**opts)
    sec=time.time()-t
    n=float(np.real(out.norm()))
    w0=bits_for(e0,s0^sigma_ref(e0,kind),order)
    w1=bits_for(e1,s1^sigma_ref(e1,kind),order)
    a0=complex(out.amplitude(w0)); a1=complex(out.amplitude(w1))
    wrong=list(w0)
    for site,v in enumerate(order):
        if v>=32:
            wrong[site]='1' if wrong[site]=='0' else '0';break
    bad=abs(complex(out.amplitude(''.join(wrong))))
    print('METHOD',method,flush=True)
    print(' seconds',sec,flush=True)
    print(' out_bond',out.max_bond(),flush=True)
    print(' norm',format(n,'.16g'),flush=True)
    print(' amp0',a0,'amp1',a1,'wrong',bad,flush=True)
    print(' rss_peak_MiB',resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,flush=True)
    assert abs(n-1)<1e-9
    assert abs(abs(a0)-1/math.sqrt(2))<1e-8
    assert abs(abs(a1)-1/math.sqrt(2))<1e-8
    assert bad<1e-10
    print(method.upper().replace('-','_')+'_PASS',flush=True)

print('V24_ZIPUP_FIRST=PASS',flush=True)
