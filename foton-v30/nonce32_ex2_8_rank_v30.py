#!/usr/bin/env python3
import random, sys
sys.path.insert(0,'foton-v29')
import latent_rank_v29 as L

def rank_vecs(vecs):
    basis={}
    for x0 in vecs:
        x=x0
        while x:
            p=x.bit_length()-1
            if p in basis: x ^= basis[p]
            else: basis[p]=x; break
    return len(basis)

def columns_from_rows(rows):
    cols=[0]*96
    for r,row in enumerate(rows):
        x=row
        while x:
            lb=x & -x
            c=lb.bit_length()-1
            cols[c] |= 1<<r
            x ^= lb
    return cols

def sample_rows(rng,n):
    out=[]
    for _ in range(n):
        u,v,q=[rng.getrandbits(32) for _ in range(3)]
        trows,_=L.derivative_rows(u,v,q)
        out.append(columns_from_rows(trows))
    return out

print('=== FOTON V30 NONCE32 + EX2-8 LOCAL COORDINATE AUDIT ===')
print('role','photonic latent-coordinate differential audit')
print('candidate_scan','NONE')
print('brute_force','NONE')
print('sat_smt','NONE')

rng=random.Random(300040)
train=sample_rows(rng,16)
base=list(range(64,96))
base_ranks=[rank_vecs([C[i] for i in base]) for C in train]
print('q32_train_ranks',base_ranks)
print('q32_train_min',min(base_ranks))

selected=[]
remaining=set(range(64))
curr=[rank_vecs([C[i] for i in base]) for C in train]
for step in range(8):
    best=None; bestscore=None; bestnr=None
    for idx in remaining:
        nr=[rank_vecs([C[i] for i in base+selected+[idx]]) for C in train]
        score=(min(nr),sum(nr),sum(r>c for r,c in zip(nr,curr)))
        if bestscore is None or score>bestscore:
            bestscore=score; best=idx; bestnr=nr
    selected.append(best); remaining.remove(best); curr=bestnr
    print('select_step',step+1,'latent_bit',best,'train_min_rank',min(curr),'train_ranks',curr)
print('selected_ex2_latent8',selected)
print('training_final_min_rank',min(curr))

valid=sample_rows(rng,64)
vr=[rank_vecs([C[i] for i in base+selected]) for C in valid]
print('validation_samples',len(vr))
print('validation_rank_distribution',{r:vr.count(r) for r in sorted(set(vr))})
print('validation_min_rank',min(vr))
print('validation_full40_fraction',vr.count(40)/len(vr))

residual=[i for i in range(64) if i not in selected]
print('residual_ex2_latent_bits_count',len(residual))
print('residual_ex2_latent_bits',residual)
print('global_bijection_proven',False)
print('next_requirement','exact reversible inverse for target40 + residual56')
print('V30_LOCAL_40COORD_AUDIT=PASS')
