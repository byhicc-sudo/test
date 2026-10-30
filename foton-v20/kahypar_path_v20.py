#!/usr/bin/env python3
import random,time
import cotengra as ctg
import foton_v18_tn_kernel as K
import split_strip_audit_v18 as S

rng=random.Random(2020)
st=[rng.getrandbits(32) for _ in range(8)]
w=rng.getrandbits(32); kk=K.K[rng.randrange(64)]
t1=S.t1_ref(st,w,kk)
tn=S.build_t1_only(st,w,kk,t1)

print("=== V20 KAHYPAR PATH AUDIT ===",flush=True)
print("tensors",len(tn.tensors),flush=True)

opts=[
 ("greedy","greedy"),
 ("kahypar_size",ctg.HyperOptimizer(methods=["kahypar"],max_repeats=32,minimize="size",progbar=False)),
 ("kahypar_combo",ctg.HyperOptimizer(methods=["kahypar"],max_repeats=32,minimize="combo",progbar=False)),
]
for name,opt in opts:
    t0=time.time()
    tree=tn.contraction_tree(output_inds=(),optimize=opt)
    sec=time.time()-t0
    print("PATH",name,flush=True)
    print(" max_elements",int(tree.max_size()),flush=True)
    print(" max_MiB_f64",tree.max_size()*8/(1024**2),flush=True)
    print(" flops",float(tree.total_flops()),flush=True)
    print(" path_seconds",sec,flush=True)
    # exact internal slicing, never outer indices
    target=(512*1024*1024)//8
    s0=time.time()
    tr=tree.slice_and_reconfigure(
        target_size=target,
        step_size=2,
        max_repeats=8,
        allow_outer=False,
        progbar=False,
        inplace=False,
        reconf_opts={"subtree_size":8,"maxiter":64},
    )
    print(" sliced_512_MiB",tr.max_size()*8/(1024**2),flush=True)
    print(" nslices",int(tr.nslices),flush=True)
    print(" sliced_inds",dict(tr.sliced_inds),flush=True)
    print(" sliced_flops",float(tr.total_flops()),flush=True)
    print(" slice_plan_seconds",time.time()-s0,flush=True)

print("V20_KAHYPAR_AUDIT=PASS",flush=True)
