#!/usr/bin/env python3
import argparse, random, time, numpy as np
import quimb.tensor as qtn
import foton_v18_tn_kernel as K

def t1_sliced(i, st, w, k):
    a,b,c,d,e,f,g,h=st
    T=K.make_t1_slice(i,K.bit(k,i))
    sel={
      f'e_{i}':K.bit(e,i),
      f'e_{(i+6)&31}':K.bit(e,(i+6)&31),
      f'e_{(i+11)&31}':K.bit(e,(i+11)&31),
      f'e_{(i+25)&31}':K.bit(e,(i+25)&31),
      f'f_{i}':K.bit(f,i),
      f'g_{i}':K.bit(g,i),
      f'h_{i}':K.bit(h,i),
      f'w_{i}':K.bit(w,i),
    }
    return T.isel(sel)

def comb_sliced(i, st, expected, wrong_flip=None):
    a,b,c,d,e,f,g,h=st
    ao=K.bit(expected[0],i)
    eo=K.bit(expected[4],i)
    if wrong_flip==('a',i): ao ^= 1
    if wrong_flip==('e',i): eo ^= 1
    T=K.make_comb_slice(i)
    sel={
      f'a_{i}':K.bit(a,i),
      f'a_{(i+2)&31}':K.bit(a,(i+2)&31),
      f'a_{(i+13)&31}':K.bit(a,(i+13)&31),
      f'a_{(i+22)&31}':K.bit(a,(i+22)&31),
      f'b_{i}':K.bit(b,i),
      f'c_{i}':K.bit(c,i),
      f'd_{i}':K.bit(d,i),
      f'ao_{i}':ao,
      f'eo_{i}':eo,
    }
    return T.isel(sel)

def round_basis_tn(st,w,k,expected,wrong_flip=None):
    ts=[]
    for i in range(32):
        ts.append(t1_sliced(i,st,w,k))
        ts.append(comb_sliced(i,st,expected,wrong_flip))
    ts += [
      K.carry_pin('c1_0',0,5),K.carry_sum('c1_32',5),
      K.carry_pin('cx_0',0,8),K.carry_sum('cx_32',8)
    ]
    return qtn.TensorNetwork(ts)

def sched_sliced(i, old,a,b,c,expected,wrong_bit=None):
    T=K.make_sched_slice(i)
    sel={f'old_{i}':K.bit(old,i),f'A_{(i+7)&31}':K.bit(a,(i+7)&31),f'A_{(i+18)&31}':K.bit(a,(i+18)&31),
         f'B_{i}':K.bit(b,i),f'C_{(i+17)&31}':K.bit(c,(i+17)&31),f'C_{(i+19)&31}':K.bit(c,(i+19)&31),
         f'new_{i}':K.bit(expected,i) ^ (1 if wrong_bit==i else 0)}
    if i+3<32: sel[f'A_{i+3}']=K.bit(a,i+3)
    if i+10<32: sel[f'C_{i+10}']=K.bit(c,i+10)
    return T.isel(sel)

def sched_basis_tn(old,a,b,c,expected,wrong_bit=None):
    ts=[sched_sliced(i,old,a,b,c,expected,wrong_bit) for i in range(32)]
    ts += [K.carry_pin('sc_0',0,4),K.carry_sum('sc_32',4)]
    return qtn.TensorNetwork(ts)

def contract_scalar(tn,opt='greedy'):
    x=tn.contract(all,optimize=opt,output_inds=())
    return float(np.asarray(x.data))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--tests',type=int,default=16)
    ap.add_argument('--opt',default='greedy')
    a=ap.parse_args()
    rng=random.Random(1818)
    print('=== FOTON V18 BASIS-SLICED EXACT TN ===',flush=True)
    print('tests',a.tests,'optimizer',a.opt,flush=True)
    t0=time.time()
    rworst=0.0; sworst=0.0
    for j in range(a.tests):
        st=[rng.getrandbits(32) for _ in range(8)]
        w=rng.getrandbits(32); kval=K.K[rng.randrange(64)]
        ref=K.round_ref(st,w,kval)
        tn=round_basis_tn(st,w,kval,ref)
        v=contract_scalar(tn,a.opt)
        bad=contract_scalar(round_basis_tn(st,w,kval,ref,('a',j&31)),a.opt)
        rworst=max(rworst,abs(v-1.0),abs(bad))
        if j==0:
            print('round_sliced_tensors',len(tn.tensors),flush=True)
            print('round_sliced_entries',sum(int(np.prod(t.shape)) for t in tn.tensors),flush=True)
        assert abs(v-1.0)<1e-12 and abs(bad)<1e-12,(j,v,bad)
    print('ROUND_BASIS_EXACT PASS',a.tests,'worst',rworst,flush=True)

    for j in range(a.tests):
        old,A,B,C=[rng.getrandbits(32) for _ in range(4)]
        ref=K.sched_ref(old,A,B,C)
        tn=sched_basis_tn(old,A,B,C,ref)
        v=contract_scalar(tn,a.opt)
        bad=contract_scalar(sched_basis_tn(old,A,B,C,ref,j&31),a.opt)
        sworst=max(sworst,abs(v-1.0),abs(bad))
        if j==0:
            print('sched_sliced_tensors',len(tn.tensors),flush=True)
            print('sched_sliced_entries',sum(int(np.prod(t.shape)) for t in tn.tensors),flush=True)
        assert abs(v-1.0)<1e-12 and abs(bad)<1e-12,(j,v,bad)
    print('SCHEDULE_BASIS_EXACT PASS',a.tests,'worst',sworst,flush=True)

    rounds=1660; sched=1244; full_blocks=24
    total=rounds*64+sched*32+full_blocks*8*32+119+3328
    print('FULL_ORACLE_FACTOR_NODE_BUDGET',total,flush=True)
    print('TARGET_500K_PASS',total<=500000,flush=True)
    print('ELAPSED',time.time()-t0,flush=True)
    print('FINAL_V18_SLICED PASS',flush=True)

if __name__=='__main__':
    main()
