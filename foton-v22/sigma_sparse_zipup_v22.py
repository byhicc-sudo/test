#!/usr/bin/env python3
import math,time,random,numpy as np
import quimb.tensor as qtn
from sigma_sparse_trellis_v20 import build_trellis,sigma_ref

DT=np.complex128
CUTOFF=1e-13

def branch_mps(bitstrings):
    m=len(bitstrings); n=len(bitstrings[0])
    arrays=[]
    amp=1/math.sqrt(m)
    for i in range(n):
        if i==0:
            A=np.zeros((m,2),dtype=DT)
            for b,s in enumerate(bitstrings): A[b,int(s[i])] += amp
        elif i==n-1:
            A=np.zeros((m,2),dtype=DT)
            for b,s in enumerate(bitstrings): A[b,int(s[i])] += 1
        else:
            A=np.zeros((m,m,2),dtype=DT)
            for b,s in enumerate(bitstrings): A[b,b,int(s[i])] += 1
        arrays.append(A)
    return qtn.MatrixProductState(arrays,shape='lrp')

def bits_for(e,s,order):
    return ''.join(str((e>>v)&1) if v<32 else str((s>>(v-32))&1) for v in order)

def as_lrp(A,k,n):
    if k==0: return A.reshape(1,A.shape[0],A.shape[1])
    if k==n-1: return A.reshape(A.shape[0],1,A.shape[1])
    return A

def from_lrp(B,k,n):
    if k==0: return B[0,:,:]
    if k==n-1: return B[:,0,:]
    return B

def right_canonical_arrays(inp,cutoff=1e-14):
    n=inp.L
    arr=[as_lrp(inp.arrays[k],k,n).astype(DT,copy=True) for k in range(n)]
    for k in range(n-1,0,-1):
        A=arr[k]
        l,r,p=A.shape
        M=A.reshape(l,r*p)
        U,s,Vh=np.linalg.svd(M,full_matrices=False)
        if s.size:
            keep=max(1,int(np.count_nonzero(s>cutoff*s[0])))
        else:
            keep=1
        U=U[:,:keep]; s=s[:keep]; Vh=Vh[:keep,:]
        arr[k]=Vh.reshape(keep,r,p)
        G=U*s[None,:]
        arr[k-1]=np.einsum('alp,lr->arp',arr[k-1],G,optimize=True)
    return arr

def right_suffix_counts(order,layers,trans):
    n=len(order)
    q=[None]*(n+1)
    q[n]={0:1.0}
    for k in range(n-1,-1,-1):
        mult=1.0 if order[k]<32 else 2.0
        d={}
        for a,b,x in trans[k]:
            d[a]=d.get(a,0.0)+mult*q[k+1][b]
        q[k]=d
    return q

def sparse_zipup_sigma(inp,kind,max_bond=128,cutoff=CUTOFF):
    order,cols,layers,trans=build_trellis(kind)
    maps=[{s:i for i,s in enumerate(layer)} for layer in layers]
    q=right_suffix_counts(order,layers,trans)
    root_scale=math.sqrt(q[0][0])
    n=64
    in_arrays=right_canonical_arrays(inp)
    out_arrays=[]
    # Apply a right-canonical normalized MPO U/root_scale.
    C=np.ones((1,1,1),dtype=DT)
    peak_T=0; peak_C=1; peak_rank=1
    t0=time.time()

    for k,(v,edges) in enumerate(zip(order,trans)):
        A=in_arrays[k]
        aL,aR,_=A.shape
        L=len(layers[k]); R=len(layers[k+1])
        assert C.shape[1:]==(aL,L),(k,C.shape,A.shape,L)
        D=C.shape[0]

        T=np.zeros((D,2,aR,R),dtype=DT)
        for sa,sb,x in edges:
            lw=maps[k][sa]; rw=maps[k+1][sb]
            # exact diagonal gauge that makes the trellis right-isometric
            fac=math.sqrt(q[k+1][sb]/q[k][sa])
            Cw=C[:,:,lw]
            if v<32:
                M=(Cw @ A[:,:,x])*fac
                T[:,x,:,rw] += M
            else:
                for si in (0,1):
                    M=(Cw @ A[:,:,si])*fac
                    T[:,si^x,:,rw] += M

        peak_T=max(peak_T,T.size)
        if k==n-1:
            assert aR==1 and R==1
            B=T[:,:,0,0]
            out_arrays.append(B)
            break

        M=T.reshape(D*2,aR*R)
        U,s,Vh=np.linalg.svd(M,full_matrices=False)
        if s.size:
            keep=int(np.count_nonzero(s>cutoff*s[0]))
        else:
            keep=0
        keep=max(1,min(keep,max_bond))
        U=U[:,:keep]; s=s[:keep]; Vh=Vh[:keep,:]
        B=U.reshape(D,2,keep).transpose(0,2,1)
        out_arrays.append(from_lrp(B,k,n))
        C=(s[:,None]*Vh).reshape(keep,aR,R)
        peak_C=max(peak_C,C.size); peak_rank=max(peak_rank,keep)

    # Undo the harmless global normalization introduced by the canonical gauge.
    out_arrays[0]=out_arrays[0]*root_scale
    out=qtn.MatrixProductState(out_arrays,shape='lrp')
    return out,order,time.time()-t0,peak_T,peak_C,peak_rank

def make_branches(kind,m):
    order,_,_,_=build_trellis(kind)
    rng=random.Random(22000+(1 if kind=='sigma1' else 0)+m)
    pairs=[]
    seen=set()
    while len(pairs)<m:
        e=rng.getrandbits(32); s=rng.getrandbits(32)
        if (e,s) not in seen:
            seen.add((e,s)); pairs.append((e,s))
    bits=[bits_for(e,s,order) for e,s in pairs]
    return order,pairs,bits

def run(kind,m):
    order,pairs,bits=make_branches(kind,m)
    inp=branch_mps(bits)
    n0=float(np.real(inp.norm()))
    print(f'=== {kind.upper()} SPARSE ZIPUP BRANCHES={m} ===',flush=True)
    print('input_bond',inp.max_bond(),'input_norm',format(n0,'.16g'),flush=True)

    out,order,sec,peakT,peakC,peakR=sparse_zipup_sigma(inp,kind,max_bond=max(64,2*m))
    n=float(np.real(out.norm()))
    print('forward_seconds',sec,flush=True)
    print('output_bond',out.max_bond(),'zipup_peak_rank',peakR,flush=True)
    print('peak_T_entries',peakT,'peak_T_MiB_c128',peakT*16/(1024**2),flush=True)
    print('peak_C_entries',peakC,'peak_C_MiB_c128',peakC*16/(1024**2),flush=True)
    print('output_norm',format(n,'.16g'),flush=True)
    assert abs(n-1)<2e-10

    target_amp=1/math.sqrt(m)
    for j,(e,s) in enumerate(pairs):
        want=bits_for(e,s^sigma_ref(e,kind),order)
        a=complex(out.amplitude(want))
        assert abs(abs(a)-target_amp)<2e-10,(j,a,target_amp)
    print('branch_amplitudes',m,'PASS',flush=True)

    back,_,sec2,pT2,pC2,pR2=sparse_zipup_sigma(out,kind,max_bond=max(64,2*m))
    ov=abs(complex(inp.H @ back))
    nb=float(np.real(back.norm()))
    print('inverse_seconds',sec2,flush=True)
    print('restore_overlap',format(ov,'.16g'),'restore_norm',format(nb,'.16g'),flush=True)
    print('inverse_peak_T_MiB_c128',pT2*16/(1024**2),'inverse_peak_rank',pR2,flush=True)
    assert abs(ov-1)<5e-10 and abs(nb-1)<5e-10
    print(kind.upper()+f'_ZIPUP_{m}=PASS',flush=True)

print('purpose: exact sparse zip-up application of photonic reversible Sigma MPO; no mining search',flush=True)
for m in (2,4,8):
    run('sigma1',m)
for m in (2,4,8):
    run('sigma0',m)
print('V22_SPARSE_ZIPUP=PASS',flush=True)
