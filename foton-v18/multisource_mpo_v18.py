#!/usr/bin/env python3
import math, random, time
import numpy as np
import quimb
import quimb.tensor as qtn

N=32
DT=np.complex128

def add_sources_mpo(nsrc, n=32):
    D=1 << (nsrc+1)
    chi=nsrc+1
    arrays=[]
    for i in range(n):
        first=(i==0); last=(i==n-1)
        if first and last:
            A=np.zeros((D,D),dtype=DT)
            ci=0
            for p in range(D):
                y=p&1
                xs=[(p>>(j+1))&1 for j in range(nsrc)]
                tot=y+sum(xs)+ci
                yp=tot&1
                q=(p&~1)|yp
                A[q,p]=1
        elif first:
            A=np.zeros((chi,D,D),dtype=DT)
            ci=0
            for p in range(D):
                y=p&1
                xs=[(p>>(j+1))&1 for j in range(nsrc)]
                tot=y+sum(xs)+ci
                yp=tot&1; co=tot>>1
                q=(p&~1)|yp
                A[co,q,p]=1
        elif last:
            A=np.zeros((chi,D,D),dtype=DT)
            for ci in range(chi):
                for p in range(D):
                    y=p&1
                    xs=[(p>>(j+1))&1 for j in range(nsrc)]
                    tot=y+sum(xs)+ci
                    yp=tot&1
                    q=(p&~1)|yp
                    A[ci,q,p]=1
        else:
            A=np.zeros((chi,chi,D,D),dtype=DT)
            for ci in range(chi):
                for p in range(D):
                    y=p&1
                    xs=[(p>>(j+1))&1 for j in range(nsrc)]
                    tot=y+sum(xs)+ci
                    yp=tot&1; co=tot>>1
                    if co < chi:
                        q=(p&~1)|yp
                        A[ci,co,q,p]=1
        arrays.append(A)
    return qtn.MatrixProductOperator(arrays,shape='lrud')

def sub_sources_mpo(nsrc,n=32):
    D=1 << (nsrc+1)
    chi=nsrc+1
    arrays=[]
    for i in range(n):
        first=(i==0); last=(i==n-1)
        if first and last:
            A=np.zeros((D,D),dtype=DT)
            bi=0
            for p in range(D):
                y=p&1
                xs=[(p>>(j+1))&1 for j in range(nsrc)]
                z=y-sum(xs)-bi
                yp=z&1
                q=(p&~1)|yp
                A[q,p]=1
        elif first:
            A=np.zeros((chi,D,D),dtype=DT)
            bi=0
            for p in range(D):
                y=p&1
                xs=[(p>>(j+1))&1 for j in range(nsrc)]
                z=y-sum(xs)-bi
                yp=z&1
                bo=(yp-z)//2
                q=(p&~1)|yp
                A[bo,q,p]=1
        elif last:
            A=np.zeros((chi,D,D),dtype=DT)
            for bi in range(chi):
                for p in range(D):
                    y=p&1
                    xs=[(p>>(j+1))&1 for j in range(nsrc)]
                    z=y-sum(xs)-bi
                    yp=z&1
                    q=(p&~1)|yp
                    A[bi,q,p]=1
        else:
            A=np.zeros((chi,chi,D,D),dtype=DT)
            for bi in range(chi):
                for p in range(D):
                    y=p&1
                    xs=[(p>>(j+1))&1 for j in range(nsrc)]
                    z=y-sum(xs)-bi
                    yp=z&1
                    bo=(yp-z)//2
                    if 0 <= bo < chi:
                        q=(p&~1)|yp
                        A[bi,bo,q,p]=1
        arrays.append(A)
    return qtn.MatrixProductOperator(arrays,shape='lrud')

def basis_mps(srcs,y,n=32):
    nsrc=len(srcs); D=1<<(nsrc+1)
    eye=np.eye(D,dtype=DT)
    vecs=[]
    for i in range(n):
        p=(y>>i)&1
        for j,x in enumerate(srcs):
            p |= ((x>>i)&1) << (j+1)
        vecs.append(eye[:,p])
    return qtn.MPS_product_state(vecs)

def coherent_sources_y0(nsrc,n=32):
    D=1<<(nsrc+1)
    v=np.zeros(D,dtype=DT)
    # target y=0, all source bits locally in equal superposition
    amp=1/math.sqrt(1<<nsrc)
    for mask in range(1<<nsrc):
        p=mask<<1
        v[p]=amp
    return qtn.MPS_product_state([v.copy() for _ in range(n)])

def overlap(a,b):
    return complex(a.H @ b)

def main():
    print("=== FOTON V18 MULTI-SOURCE EXACT MPO ===",flush=True)
    print("quimb",quimb.__version__,flush=True)
    rng=random.Random(1804)
    for nsrc in (1,2,3,4):
        add=add_sources_mpo(nsrc,N)
        sub=sub_sources_mpo(nsrc,N)
        D=1<<(nsrc+1)
        chi=nsrc+1
        print(f"CASE nsrc={nsrc} phys_dim={D} expected_chi={chi} add_chi={add.max_bond()} sub_chi={sub.max_bond()}",flush=True)
        assert add.max_bond()==chi and sub.max_bond()==chi

        worst=0.0
        t0=time.time()
        trials=24 if nsrc<4 else 12
        for k in range(trials):
            srcs=[rng.getrandbits(32) for _ in range(nsrc)]
            y=rng.getrandbits(32)
            expected=(y+sum(srcs))&0xffffffff
            psi=basis_mps(srcs,y)
            out=psi.gate_with_mpo(add,method='zipup',max_bond=64,cutoff=1e-14)
            exp=basis_mps(srcs,expected)
            ov=abs(overlap(exp,out))
            worst=max(worst,abs(1-ov))
            if abs(1-ov)>2e-11:
                raise SystemExit(f"BASIS_FAIL nsrc={nsrc} k={k} ov={ov}")
        print(f"basis nsrc={nsrc} trials={trials} worst={worst:.3e} seconds={time.time()-t0:.3f}",flush=True)

        psi=coherent_sources_y0(nsrc,N)
        t1=time.time()
        out=psi.gate_with_mpo(add,method='zipup',max_bond=128,cutoff=1e-14)
        fwd=time.time()-t1
        t2=time.time()
        back=out.gate_with_mpo(sub,method='zipup',max_bond=128,cutoff=1e-14)
        inv=time.time()-t2
        ov=overlap(psi,back)
        print(f"coherent nsrc={nsrc} fwd={fwd:.6f}s inv={inv:.6f}s out_bond={out.max_bond()} back_bond={back.max_bond()} norm={float(np.real(out.norm())):.16g} restore={abs(ov):.16g}",flush=True)
        assert abs(float(np.real(out.norm()))-1)<2e-11
        assert abs(abs(ov)-1)<2e-10

        dense=sum(int(np.prod(t.shape)) for t in add.tensors)
        nnz=sum(int(np.count_nonzero(t.data)) for t in add.tensors)
        print(f"storage nsrc={nsrc} dense={dense} nnz={nnz} sparse_fraction={nnz/dense:.8f}",flush=True)

    print("V18_MULTI_SOURCE_BOUNDED_MPO=PASS",flush=True)

if __name__=="__main__":
    main()
