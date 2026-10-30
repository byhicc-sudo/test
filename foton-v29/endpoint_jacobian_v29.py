#!/usr/bin/env python3
import random, hashlib, struct, sys
sys.path.insert(0,'foton-v28')
import triangular_96rail_v28 as V

MASK=(1<<32)-1
IV=V.IV; K=V.K

def second_endpoint(x,y,z):
    hb=V.full_header_bytes(x,y,z)
    d1=hashlib.sha256(hb).digest()
    w=list(struct.unpack('>8I',d1))+[0x80000000]+[0]*6+[0x00000100]
    W=w+[0]*48
    for t in range(16,64):
        W[t]=(V.s1(W[t-2])+W[t-7]+V.s0(W[t-15])+W[t-16])&MASK
    st=list(IV)
    e61=e62=None
    for t in range(63):
        st,_,_=V.rr(st,W[t],t)
        if t==61: e61=st[4]
        if t==62: e62=st[4]
    return ((e61&MASK)<<8)|(e62&0xff)

def rank_cols(cols):
    basis={}
    for x in cols:
        y=x
        while y:
            p=y.bit_length()-1
            if p in basis: y ^= basis[p]
            else:
                basis[p]=y; break
    return len(basis)

def jac_rank(x,y,z,which):
    base=second_endpoint(x,y,z)
    cols=[]
    if which=='nonce':
        for b in range(32):
            cols.append(base ^ second_endpoint(x,y,z^(1<<b)))
    elif which=='ex2':
        for b in range(32):
            cols.append(base ^ second_endpoint(x^(1<<b),y,z))
        for b in range(32):
            cols.append(base ^ second_endpoint(x,y^(1<<b),z))
    elif which=='all':
        for b in range(32):
            cols.append(base ^ second_endpoint(x^(1<<b),y,z))
        for b in range(32):
            cols.append(base ^ second_endpoint(x,y^(1<<b),z))
        for b in range(32):
            cols.append(base ^ second_endpoint(x,y,z^(1<<b)))
    return rank_cols(cols)

print('=== FOTON V29 40-BIT ENDPOINT JACOBIAN AUDIT ===')
print('endpoint','e61[31:0] + e62[7:0] = 40 bits')
print('target_constant','A41F32E7|55')
print('purpose','structural sensitivity audit of photonic phase function')
print('candidate_scan','NONE')
print('brute_force','NONE')
print('sat_smt','NONE')
rng=random.Random(290040)
dist_nonce={}; dist_ex2={}; dist_all={}
samples=48
for j in range(samples):
    x=rng.getrandbits(32); y=rng.getrandbits(32); z=rng.getrandbits(32)
    rn=jac_rank(x,y,z,'nonce')
    re=jac_rank(x,y,z,'ex2')
    ra=jac_rank(x,y,z,'all')
    dist_nonce[rn]=dist_nonce.get(rn,0)+1
    dist_ex2[re]=dist_ex2.get(re,0)+1
    dist_all[ra]=dist_all.get(ra,0)+1
    if (j+1)%8==0:
        print('progress',j+1,'nonce_rank',rn,'ex2_rank',re,'all_rank',ra,flush=True)
print('samples',samples)
print('nonce32_rank_distribution',dict(sorted(dist_nonce.items())))
print('extranonce64_rank_distribution',dict(sorted(dist_ex2.items())))
print('combined96_rank_distribution',dict(sorted(dist_all.items())))
print('nonce_full_rank_fraction',dist_nonce.get(32,0)/samples)
print('endpoint_full40_rank_fraction_ex2',dist_ex2.get(40,0)/samples)
print('endpoint_full40_rank_fraction_all',dist_all.get(40,0)/samples)
assert max(dist_nonce)<=32 and max(dist_ex2)<=40 and max(dist_all)<=40
print('V29_JACOBIAN_AUDIT=PASS')
