#!/usr/bin/env python3
import random, math, numpy as np
import quimb.tensor as qtn

MASK=(1<<32)-1
ORDERS={
"sigma1":[46,7,15,25,41,2,20,55,59,33,45,51,60,32,21,6,11,16,1,42,47,3,37,12,29,38,30,54,36,61,28,50,26,56,24,40,17,8,63,22,19,10,14,58,27,52,34,53,35,0,48,13,9,49,62,43,23,5,39,31,4,57,44,18],
"sigma0":[12,3,33,14,56,23,45,44,43,54,24,42,63,0,53,34,2,25,32,13,55,11,1,21,52,15,22,41,26,4,57,51,10,46,5,36,35,61,47,16,28,58,62,38,31,50,8,37,27,17,18,20,6,9,39,59,48,30,29,49,40,19,7,60]
}
SHIFTS={"sigma1":[6,11,25],"sigma0":[2,13,22]}

def rotr(x,n,w=32):
    m=(1<<w)-1
    n%=w
    return ((x>>n)|(x<<(w-n)))&m
def sigma_ref(x,kind,w=32,shifts=None):
    ss=SHIFTS[kind] if shifts is None else shifts
    y=0
    for s in ss: y ^= rotr(x,s,w)
    return y

def basis_add(b,x):
    b=dict(b)
    while x:
        p=x.bit_length()-1
        if p in b: x ^= b[p]
        else: b[p]=x; break
    return b
def reduce_vec(b,x):
    for p in sorted(b,reverse=True):
        if (x>>p)&1: x ^= b[p]
    return x

def op_cols(kind,w=32,shifts=None):
    ss=SHIFTS[kind] if shifts is None else shifts
    outc=[]; inc=[]
    for v in range(2*w):
        if v<w:
            i=v
            co=1<<i
            ci=1<<i
            for sh in ss:
                j=(i-sh)%w
                ci ^= 1<<(w+j)
        else:
            j=v-w
            co=1<<(w+j)
            ci=1<<(w+j)
        outc.append(co); inc.append(ci)
    return outc,inc

def build_op_trellis(kind,order,w=32,shifts=None):
    outc,inc=op_cols(kind,w,shifts)
    n=2*w
    suffix=[None]*(n+1)
    suffix[n]={}
    for k in range(n-1,-1,-1):
        b=suffix[k+1]
        b=basis_add(b,outc[order[k]])
        b=basis_add(b,inc[order[k]])
        suffix[k]=b
    layers=[(0,)]
    trans=[]
    states={0}
    for k,v in enumerate(order):
        fb=suffix[k+1]
        nxt=set(); edges=[]
        # label p=(out<<1)|in
        for s in sorted(states):
            for outb in (0,1):
                for inb in (0,1):
                    ns=s
                    if outb: ns ^= outc[v]
                    if inb: ns ^= inc[v]
                    if reduce_vec(fb,ns)==0:
                        nxt.add(ns); edges.append((s,ns,outb,inb))
        layers.append(tuple(sorted(nxt)))
        trans.append(tuple(edges))
        states=nxt
    assert states=={0}
    return layers,trans

def path_count(trans):
    c={0:1}
    for edges in trans:
        n={}
        for a,b,o,i in edges:
            if a in c: n[b]=n.get(b,0)+c[a]
        c=n
    return c.get(0,0)

def accepts_basis(e,s,e2,s2,kind,order,layers,trans,w=32):
    state=0
    for k,v in enumerate(order):
        ib=(e>>v)&1 if v<w else (s>>(v-w))&1
        ob=(e2>>v)&1 if v<w else (s2>>(v-w))&1
        found=None
        for a,b,o,i in trans[k]:
            if a==state and o==ob and i==ib:
                found=b; break
        if found is None: return False
        state=found
    return state==0

def dense_mpo_from_trellis(layers,trans):
    maps=[{s:i for i,s in enumerate(x)} for x in layers]
    arr=[]
    n=len(trans)
    for k,edges in enumerate(trans):
        L=len(layers[k]); R=len(layers[k+1])
        if k==0:
            A=np.zeros((R,2,2),dtype=np.complex128)
            for a,b,o,i in edges:A[maps[k+1][b],o,i]=1
        elif k==n-1:
            A=np.zeros((L,2,2),dtype=np.complex128)
            for a,b,o,i in edges:A[maps[k][a],o,i]=1
        else:
            A=np.zeros((L,R,2,2),dtype=np.complex128)
            for a,b,o,i in edges:A[maps[k][a],maps[k+1][b],o,i]=1
        arr.append(A)
    return qtn.MatrixProductOperator(arr,shape='lrud')

def exhaustive_small():
    w=8; shifts=[1,3,5]
    # simple interleaving order
    order=[]
    for i in range(w): order += [i,w+i]
    layers,trans=build_op_trellis('sigma1',order,w,shifts)
    mpo=dense_mpo_from_trellis(layers,trans)
    print('SMALL_W',w,'max_bond',mpo.max_bond(),'paths',path_count(trans),flush=True)
    assert path_count(trans)==2**(2*w)
    # exhaustive basis permutation
    for e in range(1<<w):
      se=sigma_ref(e,'sigma1',w,shifts)
      for s in range(1<<w):
        inp=e | (s<<w)
        out=e | ((s^se)<<w)
        bits=''.join(str((inp>>v)&1) for v in order)
        obits=''.join(str((out>>v)&1) for v in order)
        psi=qtn.MPS_computational_state(bits)
        got=psi.gate_with_mpo(mpo,method='zipup',max_bond=128,cutoff=1e-14)
        ov=abs(complex(qtn.MPS_computational_state(obits).H @ got))
        if abs(ov-1)>1e-10: raise AssertionError((e,s,ov))
    print('SMALL_EXHAUSTIVE_BASIS PASS',flush=True)
    # entangled/coherent product+phase state; U twice must restore
    rng=random.Random(2121)
    vecs=[]
    for _ in range(2*w):
        th=rng.random()*1.7
        ph=rng.random()*2*math.pi
        v=np.array([math.cos(th/2), np.exp(1j*ph)*math.sin(th/2)],complex)
        vecs.append(v)
    psi=qtn.MPS_product_state(vecs)
    # entangle neighboring sites
    CZ=np.diag([1,1,1,-1]).reshape(2,2,2,2).astype(complex)
    for i in range(0,2*w-1,2):
        psi.gate_(CZ,(i,i+1),contract='swap+split',max_bond=64,cutoff=1e-14)
    init=psi.copy()
    out=psi.gate_with_mpo(mpo,method='zipup',max_bond=256,cutoff=1e-14)
    back=out.gate_with_mpo(mpo,method='zipup',max_bond=256,cutoff=1e-14)
    ov=abs(complex(init.H @ back))
    print('SMALL_ENTANGLED_FWD_BOND',out.max_bond(),flush=True)
    print('SMALL_ENTANGLED_RESTORE',format(ov,'.16g'),flush=True)
    assert abs(ov-1)<1e-9
    print('SMALL_ENTANGLED_OPERATOR PASS',flush=True)

def full_audit(kind):
    order=ORDERS[kind]
    layers,trans=build_op_trellis(kind,order)
    widths=[len(x) for x in layers]
    print('===',kind.upper(),'FULL32 OPERATOR TRELLIS ===',flush=True)
    print('max_bond',max(widths),flush=True)
    print('transitions',sum(map(len,trans)),flush=True)
    print('operator_paths',path_count(trans),flush=True)
    assert path_count(trans)==2**64
    rng=random.Random(2100+(kind=='sigma1'))
    for j in range(512):
        e=rng.getrandbits(32); s=rng.getrandbits(32)
        e2=e; s2=s^sigma_ref(e,kind)
        assert accepts_basis(e,s,e2,s2,kind,order,layers,trans)
        assert not accepts_basis(e,s,e2,s2^(1<<(j&31)),kind,order,layers,trans)
    print('random_basis_operator_checks 512 PASS',flush=True)
    dense_entries=0
    for k in range(64):
        L=len(layers[k]);R=len(layers[k+1])
        dense_entries += (R*4 if k==0 else L*4 if k==63 else L*R*4)
    print('dense_entries_if_MPO',dense_entries,flush=True)
    print('dense_MiB_float64',dense_entries*8/(1024**2),flush=True)
    print(kind.upper()+'_FULL_OPERATOR_TRELLIS PASS',flush=True)

print('purpose: exact photonic reversible Sigma operator audit; no mining search',flush=True)
full_audit('sigma1')
full_audit('sigma0')
exhaustive_small()
print('V21_SIGMA_OPERATOR=PASS',flush=True)
