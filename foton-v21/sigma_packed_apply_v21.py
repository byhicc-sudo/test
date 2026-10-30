#!/usr/bin/env python3
import math,time,random,numpy as np
import quimb.tensor as qtn
from sigma_sparse_trellis_v20 import build_trellis,sigma_ref

def two_branch_mps(bits0,bits1):
    n=len(bits0); arrays=[]
    for i in range(n):
        b0=int(bits0[i]); b1=int(bits1[i])
        if i==0:
            A=np.zeros((2,2),dtype=np.float64)  # right, phys
            A[0,b0]=1/math.sqrt(2)
            A[1,b1]=1/math.sqrt(2)
        elif i==n-1:
            A=np.zeros((2,2),dtype=np.float64)  # left, phys
            A[0,b0]=1
            A[1,b1]=1
        else:
            A=np.zeros((2,2,2),dtype=np.float64) # left,right,phys
            A[0,0,b0]=1
            A[1,1,b1]=1
        arrays.append(A)
    return qtn.MatrixProductState(arrays,shape='lrp')

def product_bits(e,s,order):
    return ''.join(str((e>>v)&1) if v<32 else str((s>>(v-32))&1) for v in order)

def as_lrp(A,k,n):
    if k==0:
        return A.reshape(1,A.shape[0],A.shape[1])
    if k==n-1:
        return A.reshape(A.shape[0],1,A.shape[1])
    return A

def from_lrp(B,k,n):
    if k==0: return B[0,:,:]
    if k==n-1: return B[:,0,:]
    return B

def apply_packed_sigma(inp,kind):
    order,cols,layers,trans=build_trellis(kind)
    maps=[{s:i for i,s in enumerate(layer)} for layer in layers]
    n=64
    out_arrays=[]
    peak_entries=0
    t0=time.time()
    for k,(v,edges) in enumerate(zip(order,trans)):
        A=as_lrp(inp.arrays[k],k,n)
        dL,dR,_=A.shape
        L=len(layers[k]); R=len(layers[k+1])
        B=np.zeros((dL*L,dR*R,2),dtype=np.float64)
        # input tensors in this test are highly sparse; enumerate only nonzero entries.
        nz=np.argwhere(A!=0)
        by_phys={0:[],1:[]}
        for l,r,si in nz:
            by_phys[int(si)].append((int(l),int(r),float(A[l,r,si])))
        for a,b,x in edges:
            la=maps[k][a]; rb=maps[k+1][b]
            if v<32:
                # E passes through unchanged and drives syndrome label x.
                for l,r,val in by_phys[x]:
                    B[l*L+la,r*R+rb,x] += val
            else:
                # S_out = S_in XOR Sigma-bit contribution x.
                for si in (0,1):
                    so=si^x
                    for l,r,val in by_phys[si]:
                        B[l*L+la,r*R+rb,so] += val
        peak_entries=max(peak_entries,B.size)
        out_arrays.append(from_lrp(B,k,n))
    out=qtn.MatrixProductState(out_arrays,shape='lrp')
    return out,order,time.time()-t0,peak_entries

def run(kind):
    order,_,_,_=build_trellis(kind)
    rng=random.Random(21100+(1 if kind=='sigma1' else 0))
    e0=rng.getrandbits(32); s0=rng.getrandbits(32)
    e1=rng.getrandbits(32); s1=rng.getrandbits(32)
    while e1==e0 and s1==s0:
        e1=rng.getrandbits(32); s1=rng.getrandbits(32)
    b0=product_bits(e0,s0,order); b1=product_bits(e1,s1,order)
    inp=two_branch_mps(b0,b1)
    n0=float(np.real(inp.norm()))
    print('===',kind.upper(),'PACKED SPARSE REVERSIBLE APPLY ===',flush=True)
    print('input_bond',inp.max_bond(),'input_norm',n0,flush=True)
    out,order,sec,peak=apply_packed_sigma(inp,kind)
    print('apply_seconds',sec,flush=True)
    print('raw_output_bond',out.max_bond(),flush=True)
    print('peak_dense_tensor_entries',peak,flush=True)
    print('peak_tensor_MiB_f64',peak*8/(1024**2),flush=True)
    n=float(np.real(out.norm()))
    print('output_norm',format(n,'.16g'),flush=True)
    w0=product_bits(e0,s0^sigma_ref(e0,kind),order)
    w1=product_bits(e1,s1^sigma_ref(e1,kind),order)
    a0=complex(out.amplitude(w0)); a1=complex(out.amplitude(w1))
    print('branch0_amp',a0,flush=True)
    print('branch1_amp',a1,flush=True)
    assert abs(n-1)<1e-10
    assert abs(abs(a0)-1/math.sqrt(2))<1e-10
    assert abs(abs(a1)-1/math.sqrt(2))<1e-10
    # A wrong output must have zero amplitude.
    wrong=list(w0)
    # flip first S-variable site in optimized order
    for site,v in enumerate(order):
        if v>=32:
            wrong[site]='1' if wrong[site]=='0' else '0'
            break
    bad=complex(out.amplitude(''.join(wrong)))
    print('wrong_amp',bad,flush=True)
    assert abs(bad)<1e-12
    print(kind.upper()+'_PACKED_APPLY=PASS',flush=True)

run('sigma1')
run('sigma0')
print('V21_PACKED_SPARSE_OPERATOR=PASS',flush=True)
