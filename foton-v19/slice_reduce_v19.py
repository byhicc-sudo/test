#!/usr/bin/env python3
import random,time,copy,numpy as np
import foton_v18_tn_kernel as K
import split_strip_audit_v18 as S

rng=random.Random(191919)
st=[rng.getrandbits(32) for _ in range(8)]
w=rng.getrandbits(32); kk=K.K[rng.randrange(64)]
t1=S.t1_ref(st,w,kk)
tn=S.build_t1_only(st,w,kk,t1)
base=tn.contraction_tree(output_inds=(),optimize='greedy')
print('=== V19 EXACT INTERNAL SLICING ===',flush=True)
print('base_max_elements',int(base.max_size()),flush=True)
print('base_max_GiB_f64',base.max_size()*8/(1024**3),flush=True)
print('base_flops',float(base.total_flops()),flush=True)

for mib in (1024,512,256,128):
    target=(mib*1024*1024)//8
    t0=time.time()
    tr=base.slice_and_reconfigure(
        target_size=target,
        step_size=2,
        max_repeats=8,
        allow_outer=False,
        progbar=False,
        inplace=False,
        reconf_opts={'subtree_size':8,'maxiter':64}
    )
    dt=time.time()-t0
    print(f'TARGET_MiB {mib}',flush=True)
    print(' max_elements',int(tr.max_size()),flush=True)
    print(' max_MiB_f64',tr.max_size()*8/(1024**2),flush=True)
    print(' nslices',int(tr.nslices),flush=True)
    print(' sliced_inds',dict(tr.sliced_inds),flush=True)
    print(' total_flops',float(tr.total_flops()),flush=True)
    print(' multiplicity',int(tr.multiplicity),flush=True)
    print(' plan_seconds',dt,flush=True)
    if mib==512:
        arrays=[x.data for x in tn.tensors]
        s0=time.time()
        val=tr.contract_slice(arrays,0)
        sec=time.time()-s0
        arr=np.asarray(val)
        print(' first_slice_shape',arr.shape,flush=True)
        print(' first_slice_value',arr,flush=True)
        print(' first_slice_seconds',sec,flush=True)
        print(' projected_all_slices_seconds',sec*tr.nslices,flush=True)

print('V19_SLICE_PLAN=PASS',flush=True)
