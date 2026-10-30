#!/usr/bin/env python3
import inspect, random
import numpy as np
import quimb.tensor as qtn
import foton_v18_tn_kernel as K
import split_strip_audit_v18 as S

rng=random.Random(1919)
st=[rng.getrandbits(32) for _ in range(8)]
w=rng.getrandbits(32); kk=K.K[rng.randrange(64)]
t1=S.t1_ref(st,w,kk)
tn=S.build_t1_only(st,w,kk,t1)
tree=tn.contraction_tree(output_inds=(), optimize='greedy')
print('BEFORE_MAX_SIZE',int(tree.max_size()),flush=True)
print('BEFORE_BYTES_F64',int(tree.max_size())*8,flush=True)
for name in dir(tree):
    if 'slice' in name.lower() or 'reconfig' in name.lower():
        try:
            obj=getattr(tree,name)
            sig=inspect.signature(obj) if callable(obj) else ''
        except Exception as e:
            sig='?'
        print('METHOD',name,sig,flush=True)
for attr in ('nslices','sliced_inds','multiplicity','total_flops','max_size'):
    if hasattr(tree,attr):
        try:
            v=getattr(tree,attr)
            if callable(v): v=v()
            print('ATTR',attr,v,flush=True)
        except Exception as e:
            print('ATTR_ERR',attr,repr(e),flush=True)
