#!/usr/bin/env python3
import hashlib, struct, random, time

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
PREFIX=hashlib.sha256(b'FOTON-JOB96-CB-PREFIX').digest()[:24]
SUFFIX=hashlib.sha256(b'FOTON-JOB96-CB-SUFFIX').digest()[:24]
BRANCH=hashlib.sha256(b'FOTON-JOB96-MERKLE-BRANCH').digest()
PREV=hashlib.sha256(b'FOTON-JOB96-PREVHASH').digest()
VERSION=0x20000000
NTIME=0x6903ABCD
NBITS=0x1d00ffff

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
    return [(t1+t2)&MASK,a,b,c,(d+t1)&MASK,e,f,g]

def schedule(words16):
    W=list(words16)+[0]*48
    for t in range(16,64):
        W[t]=(s1(W[t-2])+W[t-7]+s0(W[t-15])+W[t-16])&MASK
    return W

def sha256d(b):
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()

def header(x,y,z):
    ex=((x&MASK)<<32)|(y&MASK)
    cb=PREFIX+ex.to_bytes(8,'big')+SUFFIX
    cbh=sha256d(cb)
    mr=sha256d(cbh+BRANCH)
    words=[VERSION]+list(struct.unpack('>8I',PREV))+list(struct.unpack('>8I',mr))+[NTIME,NBITS,z&MASK]
    return b''.join(struct.pack('>I',w) for w in words)

def second_sha_endpoint(d1):
    assert len(d1)==32
    words=list(struct.unpack('>8I',d1))+[0x80000000]+[0]*6+[0x00000100]
    W=schedule(words)
    st=list(IV)
    e61=None
    e62=None
    for t in range(62):
        st=rr(st,W[t],t)
        if t==60:
            e61=st[4]
        if t==61:
            e62=st[4]
    assert e61 is not None and e62 is not None
    return e61,e62

def prefix40_from_endpoint(e61,e62):
    # final H7 = IV7 + e61, final H6 = IV6 + e62
    H7=(IV[7]+e61)&MASK
    H6=(IV[6]+e62)&MASK
    # Bitcoin display reverses digest bytes:
    # first 4 displayed bytes = little-endian H7
    # fifth displayed byte = low byte of H6.
    return int.from_bytes(struct.pack('<I',H7)+bytes([H6&0xff]),'big')

TARGET_E61=(-IV[7])&MASK
TARGET_E62_LOW=(-IV[6])&0xff

print('=== FOTON V31 EXACT 40-LZ ENDPOINT ORACLE ===',flush=True)
print('exact_target_e61',f'{TARGET_E61:08x}',flush=True)
print('exact_target_e62_low8',f'{TARGET_E62_LOW:02x}',flush=True)
print('second_sha_rounds_required',62,flush=True)
print('rounds_skipped',2,flush=True)
print('final_digest_feedforward_required',False,flush=True)
print('40_target_output_ancillas_required',False,flush=True)
print('phase_controls','e61[31:0] + e62[7:0] = 40',flush=True)
print('target_reduced',False,flush=True)
print('brute_force','NONE',flush=True)
print('candidate_scan','NONE',flush=True)
print('sat_smt','NONE',flush=True)

rng=random.Random(310040)
t0=time.time()
for j in range(20000):
    x=rng.getrandbits(32); y=rng.getrandbits(32); z=rng.getrandbits(32)
    hb=header(x,y,z)
    d1=hashlib.sha256(hb).digest()
    e61,e62=second_sha_endpoint(d1)
    p=prefix40_from_endpoint(e61,e62)
    d2=hashlib.sha256(d1).digest()
    ref=int.from_bytes(d2[::-1][:5],'big')
    assert p==ref,(j,hex(p),hex(ref))
print('endpoint_prefix40_numeric_checks',20000,'PASS',flush=True)

# Exact zero predicate identity follows numerically, but also audit separately.
for j in range(20000):
    x=rng.getrandbits(32); y=rng.getrandbits(32); z=rng.getrandbits(32)
    hb=header(x,y,z)
    d1=hashlib.sha256(hb).digest()
    e61,e62=second_sha_endpoint(d1)
    endpoint=(e61==TARGET_E61 and (e62&0xff)==TARGET_E62_LOW)
    display=(int.from_bytes(hashlib.sha256(d1).digest()[::-1][:5],'big')==0)
    assert endpoint==display
print('exact_40lz_predicate_checks',20000,'PASS',flush=True)

# Marker sanity independent of rarity.
assert ((IV[7]+TARGET_E61)&MASK)==0
assert ((IV[6]+TARGET_E62_LOW)&0xff)==0
assert prefix40_from_endpoint(TARGET_E61,TARGET_E62_LOW)==0
print('forced_endpoint_zero_marker_sanity','PASS',flush=True)

# Macro-factor accounting relative to a 64-round second-SHA forward+reverse oracle.
# Each round macro was represented by 64 exact bit-slice factors in V18.
saved_round_traversals=4  # two forward rounds + the same two during uncompute
saved_round_factor_nodes=saved_round_traversals*64
print('saved_round_traversals_per_oracle',saved_round_traversals,flush=True)
print('saved_round_factor_nodes_per_oracle',saved_round_factor_nodes,flush=True)
print('remaining_hard_part','memory-bounded coherent propagation to e61/e62',flush=True)
print('elapsed_seconds',time.time()-t0,flush=True)
print('V31_ENDPOINT_ORACLE=PASS',flush=True)
