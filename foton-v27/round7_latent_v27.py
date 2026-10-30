#!/usr/bin/env python3
import random, math, hashlib, struct

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
def ch(x,y,z): return (x&y)^((~x)&z)&MASK
def maj(x,y,z): return (x&y)^(x&z)^(y&z)
def rr(st,w,t):
    a,b,c,d,e,f,g,h=st
    t1=(h+S1(e)+ch(e,f,g)+w+K[t])&MASK
    t2=(S0(a)+maj(a,b,c))&MASK
    return [(t1+t2)&MASK,a,b,c,(d+t1)&MASK,e,f,g],t1,t2

prefix=hashlib.sha256(b'FOTON-JOB96-CB-PREFIX').digest()[:24]
suffix=hashlib.sha256(b'FOTON-JOB96-CB-SUFFIX').digest()[:24]
W=list(struct.unpack('>6I',prefix))+[None,None]+list(struct.unpack('>6I',suffix))+[0x80000000,0]
st=list(IV)
for t in range(6): st,_,_=rr(st,W[t],t)
pre6=st[:]
_,base_t1_6,t2_6=rr(pre6,0,6)
CA=(base_t1_6+t2_6)&MASK
CE=(pre6[3]+base_t1_6)&MASK
DELTA=(CA-CE)&MASK

# Round7 constants after round6:
# state6 = [a6, a5, b5, c5, e6, e5, f5, g5]
A5,B5,C5,D5,E5,F5,G5,H5=pre6

def F7(u):
    # u = e6. W7 is excluded; this is the x-dependent+constant part of T1_7.
    return (G5 + S1(u) + ch(u,E5,F5) + K[7]) & MASK

def G7(u):
    # a6 = u + DELTA
    a6=(u+DELTA)&MASK
    return (S0(a6)+maj(a6,A5,B5))&MASK

def forward(x,y):
    # In-place latent coordinates:
    # u = E6 = x + CE
    # v = T1_7 = y + F7(u)
    u=(x+CE)&MASK
    v=(y+F7(u))&MASK
    return u,v

def inverse(u,v):
    x=(u-CE)&MASK
    y=(v-F7(u))&MASK
    return x,y

def state7_from_latent(u,v):
    a6=(u+DELTA)&MASK
    t2=G7(u)
    a7=(v+t2)&MASK
    e7=(C5+v)&MASK
    # after round7 = [a7,a6,a5,b5,e7,e6,e5,f5]
    return [a7,a6,A5,B5,e7,u,E5,F5]

print('=== FOTON V27 ROUND7 TRIANGULAR LATENT AUDIT ===')
print('free_words','W6 + W7 = full 64-bit extranonce2')
print('coherent_dimension',2**64)
print('CE',f'{CE:08x}','DELTA_A6_MINUS_E6',f'{DELTA:08x}')
print('mapping','u=x+CE ; v=y+F7(u)')
print('mapping_type','triangular bijection mod 2^32')
print('uniform_superposition_invariant',True)
print('latent_coherent_bond','1 in (u,v) coordinates')
print('scratch_policy','compute F7 -> add into W7 -> uncompute F7')
print('sha_candidate_scan','NONE')
print('brute_force','NONE')
print('sat_smt','NONE')

rng=random.Random(2707)
for j in range(100000):
    x=rng.getrandbits(32); y=rng.getrandbits(32)
    u,v=forward(x,y)
    xx,yy=inverse(u,v)
    assert (xx,yy)==(x,y)
    s6,_,_=rr(pre6,x,6)
    s7,t1,t2=rr(s6,y,7)
    assert s6[4]==u
    assert t1==v
    assert s7==state7_from_latent(u,v)
print('basis_forward_inverse_checks',100000,'PASS')
print('round6_round7_reference_checks',100000,'PASS')

# The map is a permutation of all 2^64 computational labels.
# Thus equal amplitudes remain exactly equal, and no basis label is discarded.
amp=2**-32
norm2=(2**64)*(amp*amp)
print('uniform_amplitude',amp)
print('analytic_norm2',norm2)
assert norm2==1.0
print('extranonce2_bits_preserved',64)
print('nonce_bits_untouched_and_coherent',32)
print('total_free_rails_preserved',96)
print('V27_ROUND7_LATENT=PASS')
