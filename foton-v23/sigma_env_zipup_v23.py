#!/usr/bin/env python3
import math,time,random,numpy as np
import quimb.tensor as qtn
from sigma_sparse_trellis_v20 import build_trellis,sigma_ref

DT=np.complex128
CUTOFF=1e-12

def branch_mps(bitstrings):
    m=len(bitstrings); n=len(bitstrings[0]); arrays=[]
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

def from_lrp(A,k,n):
    if k==0: return A[0,:,:]
    if k==n-1: return A[:,0,:]
    return A

def right_canonical_arrays(inp,cutoff=1e-14):
    n=inp.L
    arr=[as_lrp(inp.arrays[k],k,n).astype(DT,copy=True) for k in range(n)]
    for k in range(n-1,0,-1):
        A=arr[k]; l,r,p=A.shape
        M=A.reshape(l,r*p)
        U,s,Vh=np.linalg.svd(M,full_matrices=False)
        keep=max(1,int(np.count_nonzero(s>cutoff*(s[0] if s.size else 1.0))))
        U=U[:,:keep]; s=s[:keep]; Vh=Vh[:keep,:]
        arr[k]=Vh.reshape(keep,r,p)
        G=U*s[None,:]
        arr[k-1]=np.einsum('abp,br->arp',arr[k-1],G,optimize=True)
    return arr

def operator_right_envs(order,layers,trans):
    # Hilbert-Schmidt right environments of the reversible Sigma MPO.
    # E site local ops are orthogonal rank-1 projectors (HS norm^2=1).
    # S site local ops are I/X (orthogonal, HS norm^2=2).
    n=len(order)
    H=[None]*(n+1)
    H[n]=np.ones((1,1),dtype=np.float64)
    peak=1
    for k in range(n-1,-1,-1):
        L=len(layers[k]); R=len(layers[k+1])
        hn=H[k+1]
        hp=np.zeros((L,L),dtype=np.float64)
        fac=1.0 if order[k]<32 else 2.0
        # deterministic trellis: for each left state and label x, at most one right state
        maps=[[],[]]
        for a,b,x in trans[k]:
            maps[x].append((a,b))
        for x in (0,1):
            if not maps[x]: continue
            aa=np.array([z[0] for z in maps[x]],dtype=np.int64)
            bb=np.array([z[1] for z in maps[x]],dtype=np.int64)
            # states are already 0.. indexes? edges carry syndrome values, not indexes.
            # caller passes indexed transition table.
            hp[np.ix_(aa,aa)] += fac*hn[np.ix_(bb,bb)]
        H[k]=hp
        peak=max(peak,hp.size)
    return H,peak

def indexed_trellis(kind):
    order,cols,layers,trans=build_trellis(kind)
    maps=[{s:i for i,s in enumerate(layer)} for layer in layers]
    it=[]
    for k,edges in enumerate(trans):
        it.append([(maps[k][a],maps[k+1][b],x) for a,b,x in edges])
    return order,layers,it

def weighted_zipup_sigma(inp,kind,max_bond=256,cutoff=CUTOFF):
    order,layers,trans=indexed_trellis(kind)
    H,env_peak=operator_right_envs(order,layers,trans)
    n=64; arr=right_canonical_arrays(inp)
    out_arrays=[]; C=np.ones((1,1,1),dtype=DT)
    peakT=peakC=1; peakrank=1; t0=time.time()

    for k,(v,edges) in enumerate(zip(order,trans)):
        A=arr[k]; aL,aR,_=A.shape
        L=len(layers[k]); R=len(layers[k+1])
        assert C.shape[1:]==(aL,L),(k,C.shape,A.shape,L)
        D=C.shape[0]
        T=np.zeros((D,2,aR,R),dtype=DT)
        for lw,rw,x in edges:
            Cw=C[:,:,lw]
            if v<32:
                T[:,x,:,rw] += Cw @ A[:,:,x]
            else:
                for si in (0,1):
                    T[:,si^x,:,rw] += Cw @ A[:,:,si]
        peakT=max(peakT,T.size)

        if k==n-1:
            B=T[:,:,0,0]
            out_arrays.append(B)
            break

        rows=D*2
        M=T.reshape(rows,aR,R)
        hr=H[k+1]
        # exact future-weighted left Gram:
        # G[r,s] = sum_{a, w,w'} M[r,a,w] H[w,w'] M*[s,a,w']
        G=np.einsum('raw,wx,sax->rs',M,hr,M.conj(),optimize=True)
        G=(G+G.conj().T)*0.5
        ev,U=np.linalg.eigh(G)
        idx=np.argsort(ev)[::-1]
        ev=ev[idx]; U=U[:,idx]
        top=max(float(ev[0].real),0.0) if ev.size else 0.0
        keep=int(np.count_nonzero(ev>cutoff*top)) if top>0 else 1
        keep=max(1,min(keep,max_bond))
        U=U[:,:keep]
        # Rows outside span(U) have zero future norm; exact for retained nonzero environment rank.
        B=U.reshape(D,2,keep).transpose(0,2,1)
        out_arrays.append(from_lrp(B,k,n))
        # algebraic carry in original right basis
        C=np.einsum('rk,raw->kaw',U.conj(),M,optimize=True)
        peakC=max(peakC,C.size); peakrank=max(peakrank,keep)

    out=qtn.MatrixProductState(out_arrays,shape='lrp')
    return out,order,time.time()-t0,peakT,peakC,peakrank,env_peak

def make_case(kind,m):
    order,_,_=indexed_trellis(kind)
    rng=random.Random(23000+(kind=='sigma1')*101+m)
    pairs=[]; seen=set()
    while len(pairs)<m:
        p=(rng.getrandbits(32),rng.getrandbits(32))
        if p not in seen: seen.add(p); pairs.append(p)
    return order,pairs,[bits_for(e,s,order) for e,s in pairs]

def run(kind,m):
    order,pairs,bits=make_case(kind,m)
    inp=branch_mps(bits)
    print(f'=== {kind.upper()} ENV ZIPUP B={m} ===',flush=True)
    print('input_bond',inp.max_bond(),'input_norm',float(np.real(inp.norm())),flush=True)
    out,order,sec,pT,pC,pR,pE=weighted_zipup_sigma(inp,kind,max_bond=max(64,4*m))
    n=float(np.real(out.norm()))
    print('forward_seconds',sec,flush=True)
    print('output_bond',out.max_bond(),'peak_rank',pR,flush=True)
    print('peak_T_MiB_c128',pT*16/(1024**2),flush=True)
    print('peak_C_MiB_c128',pC*16/(1024**2),flush=True)
    print('env_peak_MiB_f64',pE*8/(1024**2),flush=True)
    print('norm',format(n,'.16g'),flush=True)
    assert abs(n-1)<5e-9,(kind,m,n)
    wantamp=1/math.sqrt(m)
    for e,s in pairs:
        a=complex(out.amplitude(bits_for(e,s^sigma_ref(e,kind),order)))
        assert abs(abs(a)-wantamp)<5e-9,(kind,m,a)
    print('amplitudes PASS',flush=True)
    back,_,sec2,pT2,pC2,pR2,pE2=weighted_zipup_sigma(out,kind,max_bond=max(64,4*m))
    ov=abs(complex(inp.H @ back)); nb=float(np.real(back.norm()))
    print('inverse_seconds',sec2,'restore',format(ov,'.16g'),'back_norm',format(nb,'.16g'),flush=True)
    print('inverse_peak_rank',pR2,'inverse_peak_T_MiB',pT2*16/(1024**2),flush=True)
    assert abs(ov-1)<1e-8 and abs(nb-1)<1e-8,(kind,m,ov,nb)
    print(kind.upper()+f'_ENV_ZIPUP_{m}=PASS',flush=True)

print('purpose: environment-aware exact compression of sparse photonic Sigma operator; no mining search',flush=True)
for m in (2,4,8): run('sigma1',m)
for m in (2,4,8): run('sigma0',m)
print('V23_ENVIRONMENT_ZIPUP=PASS',flush=True)
