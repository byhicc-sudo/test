#!/usr/bin/env python3
import random, time, copy
import foton_v18_tn_kernel as K
import split_strip_audit_v18 as S

rng=random.Random(1919)
st=[rng.getrandbits(32) for _ in range(8)]
w=rng.getrandbits(32); kk=K.K[rng.randrange(64)]
t1=S.t1_ref(st,w,kk)
tn=S.build_t1_only(st,w,kk,t1)

print("=== FOTON V19 EXACT INDEX SLICING ===", flush=True)
t0=time.time()
base=tn.contraction_tree(output_inds=(), optimize='greedy')
print("BASE_MAX_ELEMS", int(base.max_size()), flush=True)
print("BASE_MAX_BYTES", int(base.max_size())*8, flush=True)
print("BASE_FLOPS", int(base.total_flops()), flush=True)
print("BASE_SECONDS", time.time()-t0, flush=True)

targets=[
    ("1GiB", 1*1024**3//8),
    ("512MiB", 512*1024**2//8),
    ("256MiB", 256*1024**2//8),
]
for label,target in targets:
    t=time.time()
    tr=base.slice(target_size=target, minimize='flops', allow_outer=False, seed=19)
    print("TARGET",label,flush=True)
    print("  TARGET_ELEMS",target,flush=True)
    print("  MAX_ELEMS",int(tr.max_size()),flush=True)
    print("  MAX_BYTES",int(tr.max_size())*8,flush=True)
    print("  NSLICES",int(tr.nslices),flush=True)
    print("  MULTIPLICITY",int(tr.multiplicity),flush=True)
    print("  SLICED_INDS",tr.sliced_inds,flush=True)
    print("  FLOPS",int(tr.total_flops()),flush=True)
    print("  FLOP_OVERHEAD",float(tr.total_flops())/float(base.total_flops()),flush=True)
    print("  PLAN_SECONDS",time.time()-t,flush=True)
    assert int(tr.max_size()) <= target
print("V19_SLICING_PLAN=PASS",flush=True)
