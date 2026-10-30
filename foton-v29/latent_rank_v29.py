#!/usr/bin/env python3
# V29: local coordinate/rank audit for the exact 40-LZ photonic phase.
# Classical work here only audits the reversible photonic coordinate map.
import hashlib, struct, random, collections

MASK=(1<<32)-1
IV=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]
K=[
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
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

def rr(st,w,t):
    a,b,c,d,e,f,g,h=st
    t1=(h+S1(e)+ch(e,f,g)+w+K[t])&MASK
    t2=(S0(a)+maj(a,b,c))&MASK
    return [(t1+t2)&MASK,a,b,c,(d+t1)&MASK,e,f,g],t1,t2

def compress(words, iv):
    W=list(words)+[0]*48
    for t in range(16,64):
        W[t]=(s1(W[t-2])+W[t-7]+s0(W[t-15])+W[t-16])&MASK
    st=list(iv)
    for t in range(64):
        st,_,_=rr(st,W[t],t)
    return [(iv[i]+st[i])&MASK for i in range(8)]

PREFIX=hashlib.sha256(b'FOTON-JOB96-CB-PREFIX').digest()[:24]
SUFFIX=hashlib.sha256(b'FOTON-JOB96-CB-SUFFIX').digest()[:24]
BRANCH=hashlib.sha256(b'FOTON-JOB96-MERKLE-BRANCH').digest()
PREV=hashlib.sha256(b'FOTON-JOB96-PREVHASH').digest()
VERSION=0x20000000
NTIME=0x6903ABCD
NBITS=0x1d00ffff

# V27/V28 triangular coordinates.
pwords=list(struct.unpack('>6I',PREFIX))
swords=list(struct.unpack('>6I',SUFFIX))
Wcb=pwords+[None,None]+swords+[0x80000000,0]
st=list(IV)
for t in range(6):
    st,_,_=rr(st,Wcb[t],t)
pre6=st[:]
_,base_t1_6,t2_6=rr(pre6,0,6)
CE=(pre6[3]+base_t1_6)&MASK
A5,B5,C5,D5,E5,F5,G5,H5=pre6

def F7(u):
    return (G5+S1(u)+ch(u,E5,F5)+K[7])&MASK

def uv_to_ex2(u,v):
    x=(u-CE)&MASK
    y=(v-F7(u))&MASK
    return x,y

def sha256d(b):
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()

def merkle_from_ex2(x,y):
    ex=((x&MASK)<<32)|(y&MASK)
    cb=PREFIX+ex.to_bytes(8,'big')+SUFFIX
    return sha256d(sha256d(cb)+BRANCH)

def header_words(x,y,z):
    mr=merkle_from_ex2(x,y)
    return [VERSION]+list(struct.unpack('>8I',PREV))+list(struct.unpack('>8I',mr))+[NTIME,NBITS,z&MASK]

def pre_nonce_round_state(x,y):
    hw=header_words(x,y,0)
    h0=compress(hw[:16],IV)
    st=list(h0)
    for t,w in enumerate([hw[16],hw[17],hw[18]]):
        st,_,_=rr(st,w,t)
    return st

def Fnonce(x,y):
    st=pre_nonce_round_state(x,y)
    a,b,c,d,e,f,g,h=st
    return (h+S1(e)+ch(e,f,g)+K[3])&MASK

def uvq_to_xyz(u,v,q):
    x,y=uv_to_ex2(u,v)
    z=(q-Fnonce(x,y))&MASK
    return x,y,z

def feature(u,v,q):
    x,y,z=uvq_to_xyz(u,v,q)
    hb=b''.join(struct.pack('>I',w) for w in header_words(x,y,z))
    d1=hashlib.sha256(hb).digest()
    d2=hashlib.sha256(d1).digest()
    # Bitcoin display order: reverse the 32-byte double-SHA digest.
    target40=int.from_bytes(d2[::-1][:5],'big')
    d1i=int.from_bytes(d1,'big')
    return target40,d1i

def row_rank(rows, ncols=96):
    basis=[0]*ncols
    rank=0
    for x0 in rows:
        x=x0
        while x:
            p=x.bit_length()-1
            if basis[p]:
                x^=basis[p]
            else:
                basis[p]=x
                rank+=1
                break
    return rank

def independent_extension(base_rows,candidates,ncols=96):
    rows=list(base_rows)
    r=row_rank(rows,ncols)
    picked=[]
    for idx,row in enumerate(candidates):
        nr=row_rank(rows+[row],ncols)
        if nr>r:
            rows.append(row); picked.append(idx); r=nr
            if r==ncols: break
    return r,picked

def derivative_rows(u,v,q):
    t0,d10=feature(u,v,q)
    trows=[0]*40
    drows=[0]*256
    vals=[u,v,q]
    for col in range(96):
        w=vals.copy()
        w[col//32]^=1<<(col%32)
        t,d=feature(*w)
        dt=t0^t
        dd=d10^d
        for r in range(40):
            if (dt>>r)&1:
                trows[r]|=1<<col
        for r in range(256):
            if (dd>>r)&1:
                drows[r]|=1<<col
    return trows,drows

print('=== FOTON V29 40-LZ LATENT COORDINATE RANK AUDIT ===')
print('free_latent_bits',96)
print('phase_target_bits',40)
print('target_definition','first 40 displayed Bitcoin hash bits')
print('classical_role','photonic reversible coordinate audit only')
print('brute_force','NONE')
print('candidate_scan','NONE')
print('sat_smt','NONE')

rng=random.Random(290040)
samples=[]
freq=collections.Counter()
for s in range(8):
    u,v,q=[rng.getrandbits(32) for _ in range(3)]
    trows,drows=derivative_rows(u,v,q)
    tr=row_rank(trows)
    fr=row_rank(trows+drows)
    er,picked=independent_extension(trows,drows)
    print(f'SAMPLE {s} target_rank={tr} full_rank={fr} completed_rank={er} d1_rows_used={len(picked)}')
    assert tr==40
    assert fr==96
    assert er==96
    assert len(picked)==56
    freq.update(picked)
    samples.append((trows,drows,picked))
print('TARGET_RANK_40_ALL_SAMPLES PASS')
print('LOCAL_96_COORDINATE_COMPLETION_ALL_SAMPLES PASS')

# Try a fixed 56-row D1 complement based on frequency, then improve greedily.
ordered=[i for i,_ in freq.most_common()]
ordered += [i for i in range(256) if i not in freq]
fixed=ordered[:56]
fixed_ranks=[row_rank(t+d for t,d,p in [])] if False else []
ranks=[row_rank(trows+[drows[i] for i in fixed]) for trows,drows,_ in samples]
print('frequency_fixed56_ranks',ranks)
print('frequency_fixed56_min_rank',min(ranks))

# Multi-sample greedy: choose a row only if it improves the sum of ranks.
selected=[]
current=[row_rank(trows) for trows,_,_ in samples]
remaining=set(range(256))
for step in range(56):
    best=None; best_score=None; best_new=None
    for idx in remaining:
        nr=[row_rank(samples[j][0]+[samples[j][1][i] for i in selected+[idx]]) for j in range(len(samples))]
        score=(min(nr),sum(nr),sum(1 for j in range(len(samples)) if nr[j]>current[j]))
        if best_score is None or score>best_score:
            best_score=score; best=idx; best_new=nr
    selected.append(best); remaining.remove(best); current=best_new
print('greedy_fixed56_ranks',current)
print('greedy_fixed56_min_rank',min(current))
print('greedy_fixed56_all_full',all(r==96 for r in current))

# This audit establishes local coordinate feasibility, not a global bijection proof.
print('global_bijection_proven',False)
print('next_requirement','construct exact fixed residual56 photonic coordinates and inverse')
print('V29_LATENT_RANK_AUDIT=PASS')
