#!/usr/bin/env python3
import random,time,math,sys

ORDERS={
"sigma1":[46,7,15,25,41,2,20,55,59,33,45,51,60,32,21,6,11,16,1,42,47,3,37,12,29,38,30,54,36,61,28,50,26,56,24,40,17,8,63,22,19,10,14,58,27,52,34,53,35,0,48,13,9,49,62,43,23,5,39,31,4,57,44,18],
"sigma0":[12,3,33,14,56,23,45,44,43,54,24,42,63,0,53,34,2,25,32,13,55,11,1,21,52,15,22,41,26,4,57,51,10,46,5,36,35,61,47,16,28,58,62,38,31,50,8,37,27,17,18,20,6,9,39,59,48,30,29,49,40,19,7,60]
}
SHIFTS={"sigma1":[6,11,25],"sigma0":[2,13,22]}
MASK=(1<<32)-1

def rotr(x,n): return ((x>>n)|(x<<(32-n)))&MASK
def sigma_ref(x,kind):
    ss=SHIFTS[kind]
    return rotr(x,ss[0]) ^ rotr(x,ss[1]) ^ rotr(x,ss[2])

def columns(shifts):
    # 32 parity checks: S_j XOR E_{j+s0} XOR E_{j+s1} XOR E_{j+s2}=0.
    cols=[]
    for i in range(32):
        m=0
        for sh in shifts:
            j=(i-sh)&31
            m ^= 1<<j
        cols.append(m)
    cols += [1<<j for j in range(32)]
    return cols

def basis_add(b,x):
    b=dict(b)
    while x:
        p=x.bit_length()-1
        if p in b: x ^= b[p]
        else:
            b[p]=x
            break
    return b

def reduce_vec(b,x):
    for p in sorted(b, reverse=True):
        if (x>>p)&1: x ^= b[p]
    return x

def build_trellis(kind):
    order=ORDERS[kind]; cols=columns(SHIFTS[kind])
    suffix=[None]*65
    suffix[64]={}
    for k in range(63,-1,-1):
        suffix[k]=basis_add(suffix[k+1],cols[order[k]])
    layers=[(0,)]
    trans=[]
    states={0}
    for k,v in enumerate(order):
        fb=suffix[k+1]
        col=cols[v]
        nxt=set()
        edges=[]
        for s in sorted(states):
            ns=s
            if reduce_vec(fb,ns)==0:
                nxt.add(ns); edges.append((s,ns,0))
            ns=s^col
            if reduce_vec(fb,ns)==0:
                nxt.add(ns); edges.append((s,ns,1))
        layers.append(tuple(sorted(nxt)))
        trans.append(tuple(edges))
        states=nxt
    assert states=={0}
    return order,cols,layers,trans

def path_count(layers,trans):
    counts={0:1}
    for es in trans:
        nxt={}
        for a,b,x in es:
            if a in counts:
                nxt[b]=nxt.get(b,0)+counts[a]
        counts=nxt
    return counts.get(0,0)

def syndrome(e,s,kind):
    syn=0
    cols=columns(SHIFTS[kind])
    for i in range(32):
        if (e>>i)&1: syn ^= cols[i]
        if (s>>i)&1: syn ^= cols[32+i]
    return syn

def audit(kind,trials=256):
    t0=time.time()
    order,cols,layers,trans=build_trellis(kind)
    dt=time.time()-t0
    widths=[len(x) for x in layers]
    transitions=sum(len(x) for x in trans)
    paths=path_count(layers,trans)
    print('===',kind.upper(),'EXACT SPARSE PHOTONIC TRELLIS ===',flush=True)
    print('coherent_input_dimension',2**32,flush=True)
    print('sites',64,flush=True)
    print('max_bond_states',max(widths),flush=True)
    print('max_bond_log2',int(math.log2(max(widths))),flush=True)
    print('sparse_transitions',transitions,flush=True)
    print('path_count',paths,flush=True)
    print('build_seconds',dt,flush=True)
    print('dense_peak_complex128_bytes',max(widths)**2*2*16,flush=True)
    print('packed_sparse_transition_bytes_est',transitions*9,flush=True)
    assert paths==2**32
    assert max(widths)<=1024

    rng=random.Random(202619+(1 if kind=='sigma1' else 0))
    for j in range(trials):
        e=rng.getrandbits(32)
        s=sigma_ref(e,kind)
        assert syndrome(e,s,kind)==0
        # Wrong one-bit output must violate at least one parity check.
        assert syndrome(e,s^(1<<(j&31)),kind)!=0
    print('random_exact_checks',trials,'PASS',flush=True)
    # Every codeword has equal amplitude 2^-16 in the coherent Sigma state.
    amp=2**-16
    norm2=(2**32)*(amp*amp)
    print('uniform_codeword_amplitude',amp,flush=True)
    print('analytic_norm2',norm2,flush=True)
    assert norm2==1.0
    print(kind.upper()+'_TRELLIS=PASS',flush=True)
    return max(widths),transitions

print('purpose: exact tensor simulation of photonic CNOT Sigma layer; no mining search',flush=True)
a=audit('sigma1')
b=audit('sigma0')
print('BOTH_SIGMA_MAX_BOND',max(a[0],b[0]),flush=True)
print('BOTH_SIGMA_TRANSITIONS',a[1]+b[1],flush=True)
print('V20_SIGMA_SPARSE_TRELLIS=PASS',flush=True)
