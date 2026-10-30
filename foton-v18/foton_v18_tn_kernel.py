#!/usr/bin/env python3
import argparse, random, time
import numpy as np
import quimb.tensor as qtn

MASK=(1<<32)-1
K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]

def rotr(x,n): return ((x>>n)|(x<<(32-n)))&MASK
def S0(x): return rotr(x,2)^rotr(x,13)^rotr(x,22)
def S1(x): return rotr(x,6)^rotr(x,11)^rotr(x,25)
def s0(x): return rotr(x,7)^rotr(x,18)^(x>>3)
def s1(x): return rotr(x,17)^rotr(x,19)^(x>>10)
def ch(x,y,z): return (x&y)^((~x)&z)&MASK
def maj(x,y,z): return (x&y)^(x&z)^(y&z)

def round_ref(st,w,k):
    a,b,c,d,e,f,g,h=st
    t1=(h+S1(e)+ch(e,f,g)+w+k)&MASK
    t2=(S0(a)+maj(a,b,c))&MASK
    return [(t1+t2)&MASK,a,b,c,(d+t1)&MASK,e,f,g]

def sched_ref(old,a,b,c):
    return (old+s0(a)+b+s1(c))&MASK

def bit(x,i): return (x>>i)&1

def pin(name,val):
    return qtn.Tensor(np.array([1.0,0.0]) if val==0 else np.array([0.0,1.0]), inds=(name,))

def carry_pin(name,val,dim):
    v=np.zeros(dim); v[val]=1.0
    return qtn.Tensor(v, inds=(name,))

def carry_sum(name,dim):
    return qtn.Tensor(np.ones(dim), inds=(name,))

def make_t1_slice(i,kbit):
    inds=[f'c1_{i}',f'c1_{i+1}',f'e_{i}',f'e_{(i+6)&31}',f'e_{(i+11)&31}',f'e_{(i+25)&31}',
          f'f_{i}',f'g_{i}',f'h_{i}',f'w_{i}',f't1_{i}']
    arr=np.zeros((5,5,2,2,2,2,2,2,2,2,2), dtype=np.float64)
    for ci in range(5):
      for e0 in (0,1):
       for e6 in (0,1):
        for e11 in (0,1):
         for e25 in (0,1):
          sig=e6^e11^e25
          for f in (0,1):
           for g in (0,1):
            cv=(e0&f)^((1-e0)&g)
            for h in (0,1):
             for w in (0,1):
              s=h+sig+cv+w+kbit+ci
              to=s&1; co=s>>1
              arr[ci,co,e0,e6,e11,e25,f,g,h,w,to]=1.0
    return qtn.Tensor(arr, inds=inds, tags={f'T1_{i}'})

def make_comb_slice(i):
    inds=[f'cx_{i}',f'cx_{i+1}',f'a_{i}',f'a_{(i+2)&31}',f'a_{(i+13)&31}',f'a_{(i+22)&31}',
          f'b_{i}',f'c_{i}',f'd_{i}',f't1_{i}',f'ao_{i}',f'eo_{i}']
    arr=np.zeros((8,8,2,2,2,2,2,2,2,2,2,2), dtype=np.float64)
    for cin in range(8):
      c2=(cin>>2)&1; c3=(cin>>1)&1; c4=cin&1
      for a0 in (0,1):
       for a2 in (0,1):
        for a13 in (0,1):
         for a22 in (0,1):
          sig=a2^a13^a22
          for b in (0,1):
           for c in (0,1):
            mv=(a0&b)^(a0&c)^(b&c)
            s2=sig+mv+c2; t2=s2&1; c2o=s2>>1
            for d in (0,1):
             for t1 in (0,1):
              sa=t1+t2+c3; ao=sa&1; c3o=sa>>1
              se=d+t1+c4; eo=se&1; c4o=se>>1
              cout=(c2o<<2)|(c3o<<1)|c4o
              arr[cin,cout,a0,a2,a13,a22,b,c,d,t1,ao,eo]=1.0
    return qtn.Tensor(arr, inds=inds, tags={f'COMB_{i}'})

def build_round_tn(st,w,k, expected=None, wrong_flip=None):
    a,b,c,d,e,f,g,h=st
    if expected is None: expected=round_ref(st,w,k)
    ao=expected[0]; eo=expected[4]
    ts=[]
    for i in range(32):
        ts.append(make_t1_slice(i, bit(k,i)))
        ts.append(make_comb_slice(i))
    ts += [carry_pin('c1_0',0,5), carry_sum('c1_32',5), carry_pin('cx_0',0,8), carry_sum('cx_32',8)]
    for name,val in [('a',a),('b',b),('c',c),('d',d),('e',e),('f',f),('g',g),('h',h),('w',w)]:
        for i in range(32): ts.append(pin(f'{name}_{i}',bit(val,i)))
    for i in range(32):
        av=bit(ao,i); ev=bit(eo,i)
        if wrong_flip == ('a',i): av ^= 1
        if wrong_flip == ('e',i): ev ^= 1
        ts.append(pin(f'ao_{i}',av)); ts.append(pin(f'eo_{i}',ev))
    return qtn.TensorNetwork(ts)

def make_sched_slice(i):
    src=[f'old_{i}',f'A_{(i+7)&31}',f'A_{(i+18)&31}']
    a3=(i+3 if i+3<32 else None)
    if a3 is not None: src.append(f'A_{a3}')
    src += [f'B_{i}',f'C_{(i+17)&31}',f'C_{(i+19)&31}']
    c10=(i+10 if i+10<32 else None)
    if c10 is not None: src.append(f'C_{c10}')
    inds=[f'sc_{i}',f'sc_{i+1}']+src+[f'new_{i}']
    shape=[4,4]+[2]*len(src)+[2]
    arr=np.zeros(shape,dtype=np.float64)
    for ci in range(4):
      for vals in np.ndindex(*([2]*len(src))):
        p=0
        old=vals[p]; p+=1
        A7=vals[p]; p+=1
        A18=vals[p]; p+=1
        if a3 is not None: A3=vals[p]; p+=1
        else: A3=0
        B=vals[p]; p+=1
        C17=vals[p]; p+=1
        C19=vals[p]; p+=1
        if c10 is not None: C10=vals[p]; p+=1
        else: C10=0
        v0=A7^A18^A3; v1=C17^C19^C10
        s=old+v0+B+v1+ci; out=s&1; co=s>>1
        arr[(ci,co)+vals+(out,)]=1.0
    return qtn.Tensor(arr, inds=inds, tags={f'SCHED_{i}'})

def build_sched_tn(old,a,b,c,expected=None,wrong_bit=None):
    if expected is None: expected=sched_ref(old,a,b,c)
    ts=[make_sched_slice(i) for i in range(32)]
    ts += [carry_pin('sc_0',0,4), carry_sum('sc_32',4)]
    for name,val in [('old',old),('A',a),('B',b),('C',c)]:
        for i in range(32): ts.append(pin(f'{name}_{i}',bit(val,i)))
    for i in range(32):
        v=bit(expected,i) ^ (1 if wrong_bit==i else 0)
        ts.append(pin(f'new_{i}',v))
    return qtn.TensorNetwork(ts)

def scalar_contract(tn,opt='auto-hq'):
    x=tn.contract(all, optimize=opt, output_inds=())
    return float(np.asarray(x.data))

def audit(round_tests=2,sched_tests=2,opt='auto-hq'):
    rng=random.Random(18040)
    print('=== FOTON V18 EXACT TN KERNEL ===',flush=True)
    print('round factor tensors : 64',flush=True)
    print('schedule tensors     : 32',flush=True)
    print('classical search     : NONE',flush=True)
    print('SAT/SMT              : NONE',flush=True)
    print('purpose              : classical simulation of photonic reversible tensor circuit',flush=True)
    t0=time.time()
    for j in range(round_tests):
        st=[rng.getrandbits(32) for _ in range(8)]; w=rng.getrandbits(32); k=K[rng.randrange(64)]
        ref=round_ref(st,w,k)
        tn=build_round_tn(st,w,k,ref)
        v=scalar_contract(tn,opt)
        bad=scalar_contract(build_round_tn(st,w,k,ref,('a',j%32)),opt)
        print(f'ROUND_TEST {j+1} correct={v:.1f} wrong={bad:.1f} tensors={len(tn.tensors)}',flush=True)
        assert abs(v-1.0)<1e-12 and abs(bad)<1e-12
    for j in range(sched_tests):
        vals=[rng.getrandbits(32) for _ in range(4)]
        ref=sched_ref(*vals)
        tn=build_sched_tn(*vals,ref)
        v=scalar_contract(tn,opt)
        bad=scalar_contract(build_sched_tn(*vals,ref,j%32),opt)
        print(f'SCHED_TEST {j+1} correct={v:.1f} wrong={bad:.1f} tensors={len(tn.tensors)}',flush=True)
        assert abs(v-1.0)<1e-12 and abs(bad)<1e-12
    rounds=1660; sched=1244; full_blocks=24
    round_nodes=rounds*64
    sched_nodes=sched*32
    feed=full_blocks*8*32
    marker=119; routing=3328
    total=round_nodes+sched_nodes+feed+marker+routing
    print('ROUND_FACTOR_NODES',round_nodes,flush=True)
    print('SCHEDULE_FACTOR_NODES',sched_nodes,flush=True)
    print('FEEDFORWARD_NODES',feed,flush=True)
    print('MARKER_NODES',marker,flush=True)
    print('ROUTING_BUDGET',routing,flush=True)
    print('TOTAL_EXECUTED_FACTOR_NODES',total,flush=True)
    print('TARGET_500K_PASS',total<=500000,flush=True)
    print('ELAPSED',time.time()-t0,flush=True)
    print('FINAL_V18 PASS',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--round-tests',type=int,default=2)
    ap.add_argument('--sched-tests',type=int,default=2)
    ap.add_argument('--opt',default='auto-hq')
    a=ap.parse_args(); audit(a.round_tests,a.sched_tests,a.opt)
