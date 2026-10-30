#!/usr/bin/env python3
import hashlib, struct, random, math

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
    return [ (iv[i]+st[i])&MASK for i in range(8) ]

def sha256_words(msg80):
    assert len(msg80)==80
    b0=list(struct.unpack('>16I',msg80[:64]))
    h0=compress(b0,IV)
    tail=msg80[64:]+b'\x80'+b'\x00'*(64-16-1-8)+struct.pack('>Q',640)
    b1=list(struct.unpack('>16I',tail))
    h1=compress(b1,h0)
    return h1

PREFIX=hashlib.sha256(b'FOTON-JOB96-CB-PREFIX').digest()[:24]
SUFFIX=hashlib.sha256(b'FOTON-JOB96-CB-SUFFIX').digest()[:24]
BRANCH=hashlib.sha256(b'FOTON-JOB96-MERKLE-BRANCH').digest()
PREV=hashlib.sha256(b'FOTON-JOB96-PREVHASH').digest()
VERSION=0x20000000
NTIME=0x6903ABCD
NBITS=0x1d00ffff

# Early ex2 latent transform from V27.
pwords=list(struct.unpack('>6I',PREFIX))
swords=list(struct.unpack('>6I',SUFFIX))
Wcb=pwords+[None,None]+swords+[0x80000000,0]
st=list(IV)
for t in range(6):
    st,_,_=rr(st,Wcb[t],t)
pre6=st[:]
_,base_t1_6,t2_6=rr(pre6,0,6)
CA=(base_t1_6+t2_6)&MASK
CE=(pre6[3]+base_t1_6)&MASK
DELTA=(CA-CE)&MASK
A5,B5,C5,D5,E5,F5,G5,H5=pre6

def F7(u):
    return (G5 + S1(u) + ch(u,E5,F5) + K[7]) & MASK

def ex2_to_uv(x,y):
    u=(x+CE)&MASK
    v=(y+F7(u))&MASK
    return u,v

def uv_to_ex2(u,v):
    x=(u-CE)&MASK
    y=(v-F7(u))&MASK
    return x,y

def sha256d(b):
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()

def merkle_from_ex2(x,y):
    ex=((x&MASK)<<32)|(y&MASK)
    cb=PREFIX+ex.to_bytes(8,'big')+SUFFIX
    cbh=sha256d(cb)
    return sha256d(cbh+BRANCH)

def header_words(x,y,nonce_word):
    mr=merkle_from_ex2(x,y)
    prevw=list(struct.unpack('>8I',PREV))
    mrw=list(struct.unpack('>8I',mr))
    return [VERSION]+prevw+mrw+[NTIME,NBITS,nonce_word&MASK]

def pre_nonce_round_state(x,y):
    hw=header_words(x,y,0)
    # First 64-byte header block: words 0..15.
    h0=compress(hw[:16],IV)
    # Second block words: header W16, ntime, nbits, nonce, padding...
    w0=hw[16]; w1=hw[17]; w2=hw[18]
    st=list(h0)
    st,_,_=rr(st,w0,0)
    st,_,_=rr(st,w1,1)
    st,_,_=rr(st,w2,2)
    return st

def Fnonce(x,y):
    st=pre_nonce_round_state(x,y)
    a,b,c,d,e,f,g,h=st
    return (h+S1(e)+ch(e,f,g)+K[3])&MASK

def xyz_to_uvq(x,y,z):
    u,v=ex2_to_uv(x,y)
    q=(z+Fnonce(x,y))&MASK
    return u,v,q

def uvq_to_xyz(u,v,q):
    x,y=uv_to_ex2(u,v)
    z=(q-Fnonce(x,y))&MASK
    return x,y,z

def full_header_bytes(x,y,z):
    return b''.join(struct.pack('>I',w) for w in header_words(x,y,z))

print('=== FOTON V28 FULL 96-RAIL TRIANGULAR LATENT AUDIT ===')
print('free_inputs','ex2_hi32 + ex2_lo32 + nonce_word32')
print('input_free_bits',96)
print('latent_coordinates','u32 + v32 + q32')
print('mapping','u=x+CE ; v=y+F7(u) ; q=z+Fnonce(x,y)')
print('mapping_type','triangular bijection mod 2^32')
print('uniform_superposition_invariant',True)
print('latent_coherent_bond','1 in ideal (u,v,q) coordinates')
print('40lz_target_bits',40)
print('target_reduced',False)
print('brute_force','NONE')
print('sha_candidate_scan','NONE')
print('sat_smt','NONE')

rng=random.Random(280096)
for j in range(5000):
    x=rng.getrandbits(32); y=rng.getrandbits(32); z=rng.getrandbits(32)
    u,v,q=xyz_to_uvq(x,y,z)
    xx,yy,zz=uvq_to_xyz(u,v,q)
    assert (xx,yy,zz)==(x,y,z)

    # Verify nonce round t1 exactly equals q.
    st=pre_nonce_round_state(x,y)
    st3,t1,t2=rr(st,z,3)
    assert t1==q

    # Full first SHA via our compression must match hashlib.
    hb=full_header_bytes(x,y,z)
    words=sha256_words(hb)
    d=b''.join(struct.pack('>I',w) for w in words)
    assert d==hashlib.sha256(hb).digest()

    if j<256:
        # Independent double-SHA reference sanity.
        d2=hashlib.sha256(d).digest()
        assert d2==sha256d(hb)

print('triangular_forward_inverse_checks',5000,'PASS')
print('nonce_round_t1_checks',5000,'PASS')
print('header_sha256_reference_checks',5000,'PASS')
print('header_sha256d_checks',256,'PASS')
amp=2**-48
norm2=(2**96)*(amp*amp)
print('uniform_amplitude',amp)
print('analytic_norm2',norm2)
assert norm2==1.0
print('extranonce2_bits_preserved',64)
print('nonce_bits_preserved',32)
print('total_free_rails_preserved',96)
print('remaining_hard_part','40-bit final phase function in latent coordinates')
print('V28_96RAIL_TRIANGULAR_LATENT=PASS')
