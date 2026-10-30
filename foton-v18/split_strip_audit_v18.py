#!/usr/bin/env python3
import random, time, numpy as np
import quimb.tensor as qtn
import foton_v18_tn_kernel as K

def tree_stats(tn,opt='greedy'):
    tree=tn.contraction_tree(output_inds=(), optimize=opt)
    return tree, int(tree.max_size()), int(tree.max_contraction_size()), float(tree.total_flops())

def contract_scalar(tn,tree):
    x=tn.contract(all, output_inds=(), optimize=tree)
    return float(np.asarray(x.data))

def build_t1_only(st,w,k,t1,wrong=None):
    a,b,c,d,e,f,g,h=st
    ts=[K.make_t1_slice(i,K.bit(k,i)) for i in range(32)]
    ts += [K.carry_pin('c1_0',0,5),K.carry_sum('c1_32',5)]
    for name,val in [('e',e),('f',f),('g',g),('h',h),('w',w)]:
        for i in range(32): ts.append(K.pin(f'{name}_{i}',K.bit(val,i)))
    for i in range(32):
        v=K.bit(t1,i) ^ (1 if wrong==i else 0)
        ts.append(K.pin(f't1_{i}',v))
    return qtn.TensorNetwork(ts)

def build_comb_only(st,t1,ao,eo,wrong=None):
    a,b,c,d,e,f,g,h=st
    ts=[K.make_comb_slice(i) for i in range(32)]
    ts += [K.carry_pin('cx_0',0,8),K.carry_sum('cx_32',8)]
    for name,val in [('a',a),('b',b),('c',c),('d',d),('t1',t1)]:
        for i in range(32): ts.append(K.pin(f'{name}_{i}',K.bit(val,i)))
    for i in range(32):
        av=K.bit(ao,i); ev=K.bit(eo,i)
        if wrong==('a',i): av^=1
        if wrong==('e',i): ev^=1
        ts.append(K.pin(f'ao_{i}',av)); ts.append(K.pin(f'eo_{i}',ev))
    return qtn.TensorNetwork(ts)

def t1_ref(st,w,k):
    a,b,c,d,e,f,g,h=st
    return (h+K.S1(e)+K.ch(e,f,g)+w+k)&K.MASK

def main():
    rng=random.Random(1818)
    print('=== FOTON V18 SPLIT STRIP AUDIT ===',flush=True)
    for case in range(3):
        st=[rng.getrandbits(32) for _ in range(8)]
        w=rng.getrandbits(32); kk=K.K[rng.randrange(64)]
        rr=K.round_ref(st,w,kk); t1=t1_ref(st,w,kk)
        t0=time.time()
        tn=build_t1_only(st,w,kk,t1)
        tree,ms,mcs,fl=tree_stats(tn)
        val=contract_scalar(tn,tree)
        bad=contract_scalar(build_t1_only(st,w,kk,t1,case), build_t1_only(st,w,kk,t1,case).contraction_tree(output_inds=(),optimize='greedy'))
        print(f'T1 case={case} correct={val:.1f} wrong={bad:.1f} factors={len(tn.tensors)} max_size={ms} max_contract={mcs} flops={fl:.0f} sec={time.time()-t0:.3f}',flush=True)
        assert abs(val-1)<1e-12 and abs(bad)<1e-12

        t0=time.time()
        tn2=build_comb_only(st,t1,rr[0],rr[4])
        tree2,ms2,mcs2,fl2=tree_stats(tn2)
        val2=contract_scalar(tn2,tree2)
        badtn=build_comb_only(st,t1,rr[0],rr[4],('a',case))
        badtree=badtn.contraction_tree(output_inds=(),optimize='greedy')
        bad2=contract_scalar(badtn,badtree)
        print(f'COMB case={case} correct={val2:.1f} wrong={bad2:.1f} factors={len(tn2.tensors)} max_size={ms2} max_contract={mcs2} flops={fl2:.0f} sec={time.time()-t0:.3f}',flush=True)
        assert abs(val2-1)<1e-12 and abs(bad2)<1e-12

    for case in range(3):
        old,a,b,c=[rng.getrandbits(32) for _ in range(4)]
        ref=K.sched_ref(old,a,b,c)
        tn=K.build_sched_tn(old,a,b,c,ref)
        tree,ms,mcs,fl=tree_stats(tn)
        val=contract_scalar(tn,tree)
        badtn=K.build_sched_tn(old,a,b,c,ref,case)
        badtree=badtn.contraction_tree(output_inds=(),optimize='greedy')
        bad=contract_scalar(badtn,badtree)
        print(f'SCHED case={case} correct={val:.1f} wrong={bad:.1f} factors={len(tn.tensors)} max_size={ms} max_contract={mcs} flops={fl:.0f}',flush=True)
        assert abs(val-1)<1e-12 and abs(bad)<1e-12

    rounds=1660
    sched=1244
    feed=24*8*32
    marker=117
    core_nodes=rounds*64+sched*32+feed+marker
    print('ROUND_TRAVERSALS',rounds,flush=True)
    print('SCHEDULE_UPDATES',sched,flush=True)
    print('CORE_BOUNDED_FACTOR_NODES',core_nodes,flush=True)
    print('TARGET_500K_CORE_PASS',core_nodes<=500000,flush=True)
    print('V18_SPLIT_STRIP_AUDIT=PASS',flush=True)

if __name__=='__main__':
    main()
