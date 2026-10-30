#!/usr/bin/env python3
import math, random, time
import numpy as np
import quimb
import quimb.tensor as qtn

N = 32
DT = np.complex128

def full_adder_mpo(n=32):
    arrays = []
    for i in range(n):
        first = (i == 0)
        last = (i == n - 1)
        if first and last:
            A = np.zeros((4,4), dtype=DT)
            ci = 0
            for p in range(4):
                x=(p>>1)&1; y=p&1
                s=x^y^ci
                q=(x<<1)|s
                A[q,p]=1
        elif first:
            A = np.zeros((2,4,4), dtype=DT)  # r,u,d
            ci = 0
            for co in range(2):
                for p in range(4):
                    x=(p>>1)&1; y=p&1
                    s=x^y^ci
                    c2=(x&y)|(x&ci)|(y&ci)
                    if co == c2:
                        q=(x<<1)|s
                        A[co,q,p]=1
        elif last:
            A = np.zeros((2,4,4), dtype=DT)  # l,u,d
            for ci in range(2):
                for p in range(4):
                    x=(p>>1)&1; y=p&1
                    s=x^y^ci
                    q=(x<<1)|s
                    A[ci,q,p]=1
        else:
            A = np.zeros((2,2,4,4), dtype=DT)  # l,r,u,d
            for ci in range(2):
                for co in range(2):
                    for p in range(4):
                        x=(p>>1)&1; y=p&1
                        s=x^y^ci
                        c2=(x&y)|(x&ci)|(y&ci)
                        if co == c2:
                            q=(x<<1)|s
                            A[ci,co,q,p]=1
        arrays.append(A)
    return qtn.MatrixProductOperator(arrays, shape='lrud')

def basis_mps(x, y, n=32):
    eye=np.eye(4,dtype=DT)
    vecs=[]
    for i in range(n):
        p=(((x>>i)&1)<<1)|((y>>i)&1)
        vecs.append(eye[:,p])
    return qtn.MPS_product_state(vecs)

def plus_x_y0_mps(n=32):
    # each site: (|x=0,y=0> + |x=1,y=0>)/sqrt(2)
    v=np.zeros(4,dtype=DT)
    v[0]=1/math.sqrt(2)
    v[2]=1/math.sqrt(2)
    return qtn.MPS_product_state([v.copy() for _ in range(n)])

def overlap(a,b):
    return complex(a.H @ b)

def main():
    print("=== FOTON V18 EXACT ADDER MPO ===", flush=True)
    print("quimb", quimb.__version__, flush=True)
    mpo=full_adder_mpo(N)
    print("sites", N, flush=True)
    print("mpo_tensors", mpo.num_tensors, flush=True)
    print("mpo_max_bond", mpo.max_bond(), flush=True)
    print("physical_dim_per_site", 4, flush=True)

    rng=random.Random(180032)
    worst=0.0
    t0=time.time()
    for k in range(64):
        x=rng.getrandbits(32)
        y=rng.getrandbits(32)
        psi=basis_mps(x,y)
        out=psi.gate_with_mpo(mpo, method='zipup', max_bond=16, cutoff=1e-14)
        expected=basis_mps(x,(x+y)&0xffffffff)
        ov=abs(overlap(expected,out))
        err=abs(1.0-ov)
        worst=max(worst,err)
        if err > 1e-11:
            raise SystemExit(f"BASIS_FAIL k={k} x={x:08x} y={y:08x} ov={ov}")
    print("basis_vectors",64,"PASS",flush=True)
    print("basis_worst_overlap_error",worst,flush=True)
    print("basis_seconds",time.time()-t0,flush=True)

    psi=plus_x_y0_mps(N)
    n0=float(psi.norm())
    t1=time.time()
    out=psi.gate_with_mpo(mpo, method='zipup', max_bond=64, cutoff=1e-14)
    n1=float(out.norm())
    print("coherent_forward_seconds",time.time()-t1,flush=True)
    print("coherent_norm_before",format(n0,'.16g'),flush=True)
    print("coherent_norm_after",format(n1,'.16g'),flush=True)
    print("coherent_max_bond_after",out.max_bond(),flush=True)

    t2=time.time()
    back=out.gate_with_mpo(mpo.H, method='zipup', max_bond=64, cutoff=1e-14)
    n2=float(back.norm())
    ov=overlap(psi,back)
    print("coherent_inverse_seconds",time.time()-t2,flush=True)
    print("coherent_norm_restored",format(n2,'.16g'),flush=True)
    print("coherent_restore_overlap_real",format(ov.real,'.16g'),flush=True)
    print("coherent_restore_overlap_imag",format(ov.imag,'.3e'),flush=True)
    print("coherent_max_bond_restored",back.max_bond(),flush=True)

    assert abs(n1-1.0) < 1e-11
    assert abs(n2-1.0) < 1e-11
    assert abs(abs(ov)-1.0) < 1e-10

    dense_entries=sum(int(np.prod(t.shape)) for t in mpo.tensors)
    nnz=sum(int(np.count_nonzero(t.data)) for t in mpo.tensors)
    print("mpo_dense_entries",dense_entries,flush=True)
    print("mpo_nonzero_entries",nnz,flush=True)
    print("nonzero_fraction",nnz/dense_entries,flush=True)
    print("V18_EXACT_BOUNDED_ADDER_MPO=PASS",flush=True)

if __name__=="__main__":
    main()
