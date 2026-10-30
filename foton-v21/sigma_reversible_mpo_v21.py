#!/usr/bin/env python3
import time, math, random, numpy as np
import quimb.tensor as qtn
from sigma_sparse_trellis_v20 import build_trellis, sigma_ref

DT=np.float64

def sigma_mpo(kind):
    order,cols,layers,trans=build_trellis(kind)
    maps=[{s:i for i,s in enumerate(layer)} for layer in layers]
    arrays=[]
    entries=0; nnz=0
    for k,(v,edges) in enumerate(zip(order,trans)):
        L=len(layers[k]); R=len(layers[k+1])
        if k==0:
            A=np.zeros((R,2,2),dtype=DT)
            for a,b,x in edges:
                rb=maps[k+1][b]
                if v<32:
                    A[rb,x,x]=1.0
                else:
                    for si in (0,1):
                        so=si^x
                        A[rb,so,si]=1.0
        elif k==63:
            A=np.zeros((L,2,2),dtype=DT)
            for a,b,x in edges:
                la=maps[k][a]
                if v<32:
                    A[la,x,x]=1.0
                else:
                    for si in (0,1):
                        so=si^x
                        A[la,so,si]=1.0
        else:
            A=np.zeros((L,R,2,2),dtype=DT)
            for a,b,x in edges:
                la=maps[k][a]; rb=maps[k+1][b]
                if v<32:
                    A[la,rb,x,x]=1.0
                else:
                    for si in (0,1):
                        so=si^x
                        A[la,rb,so,si]=1.0
        entries += A.size; nnz += int(np.count_nonzero(A))
        arrays.append(A)
    mpo=qtn.MatrixProductOperator(arrays,shape='lrud')
    return mpo,order,entries,nnz

def bits_for(e,s,order):
    return ''.join(str((e>>v)&1) if v<32 else str((s>>(v-32))&1) for v in order)

def product_plus_e_zero_s(order):
    vecs=[]
    plus=np.array([1.0,1.0])/math.sqrt(2)
    zero=np.array([1.0,0.0])
    for v in order:
        vecs.append(plus.copy() if v<32 else zero.copy())
    return qtn.MPS_product_state(vecs)

def run(kind, coherent=True):
    print('===',kind.upper(),'REVERSIBLE TRELLIS MPO ===',flush=True)
    t0=time.time()
    mpo,order,entries,nnz=sigma_mpo(kind)
    print('build_seconds',time.time()-t0,flush=True)
    print('sites',mpo.L,'max_bond',mpo.max_bond(),flush=True)
    print('dense_entries',entries,flush=True)
    print('dense_MiB_f64',entries*8/(1024**2),flush=True)
    print('nnz',nnz,'sparse_fraction',nnz/entries,flush=True)
    rng=random.Random(2100+(1 if kind=='sigma1' else 0))
    t1=time.time()
    for j in range(2):
        e=rng.getrandbits(32); s=rng.getrandbits(32)
        inp=qtn.MPS_computational_state(bits_for(e,s,order))
        out=inp.gate_with_mpo(mpo,method='zipup',max_bond=16,cutoff=1e-14)
        want=bits_for(e,s^sigma_ref(e,kind),order)
        amp=complex(out.amplitude(want))
        assert abs(abs(amp)-1)<1e-11,(j,amp)
        assert abs(float(np.real(out.norm()))-1)<1e-11
    print('basis_operator_tests 2 PASS seconds',time.time()-t1,flush=True)

    if coherent:
        psi=product_plus_e_zero_s(order)
        t2=time.time()
        out=psi.gate_with_mpo(mpo,method='zipup',max_bond=1024,cutoff=1e-14)
        sec=time.time()-t2
        n=float(np.real(out.norm()))
        print('coherent_forward_seconds',sec,flush=True)
        print('coherent_out_bond',out.max_bond(),flush=True)
        print('coherent_norm',format(n,'.16g'),flush=True)
        assert abs(n-1)<1e-9
        # MPO is self-inverse for S ^= Sigma(E).
        t3=time.time()
        back=out.gate_with_mpo(mpo,method='zipup',max_bond=1024,cutoff=1e-14)
        inv=time.time()-t3
        # Apply H to E sites so exact restored state should be all-zero.
        H=np.array([[1,1],[1,-1]],float)/math.sqrt(2)
        for site,v in enumerate(order):
            if v<32:
                back.gate_(H,site,contract='swap+split',max_bond=1024,cutoff=1e-14)
        p0=abs(complex(back.amplitude('0'*64)))**2
        nb=float(np.real(back.norm()))
        print('coherent_inverse_seconds',inv,flush=True)
        print('restore_prob_zero',format(p0,'.16g'),flush=True)
        print('restore_norm',format(nb,'.16g'),flush=True)
        assert abs(p0-1)<1e-8 and abs(nb-1)<1e-9
        print(kind.upper()+'_COHERENT_OPERATOR=PASS',flush=True)

run('sigma1',True)
# sigma0 basis operator is enough in same run; coherent structure has identical dimensions.
run('sigma0',False)
print('V21_SIGMA_REVERSIBLE_MPO=PASS',flush=True)
