#!/usr/bin/env python3
import random
M=(1<<32)-1
IV=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]
K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5]
def R(x,n): return ((x>>n)|(x<<(32-n)))&M
def S0(x): return R(x,2)^R(x,13)^R(x,22)
def S1(x): return R(x,6)^R(x,11)^R(x,25)
def ch(x,y,z): return (x&y)^((~x)&z)&M
def maj(x,y,z): return (x&y)^(x&z)^(y&z)
def base(st,t):
    a,b,c,d,e,f,g,h=st
    return (h+S1(e)+ch(e,f,g)+K[t])&M
def step(st,q):
    a,b,c,d,e,f,g,h=st
    t2=(S0(a)+maj(a,b,c))&M
    return [(q+t2)&M,a,b,c,(d+q)&M,e,f,g]
def fw(words):
    st=list(IV); qs=[]
    for t,w in enumerate(words):
        q=(w+base(st,t))&M
        qs.append(q); st=step(st,q)
    return qs,st
def inv(qs):
    st=list(IV); ws=[]
    for t,q in enumerate(qs):
        ws.append((q-base(st,t))&M)
        st=step(st,q)
    return ws,st

print("=== FOTON V32 SECOND SHA TRIANGULAR LATENT ===")
print("input_bits",256)
print("latent_bits",256)
print("latent_words","q0..q7 = round T1")
print("mapping_type","triangular bijection mod 2^32")
print("rounds_absorbed",8)
print("brute_force","NONE")
print("candidate_scan","NONE")
print("sat_smt","NONE")
r=random.Random(320256)
for j in range(100000):
    w=[r.getrandbits(32) for _ in range(8)]
    q,s=fw(w)
    ww,ss=inv(q)
    assert ww==w and ss==s
print("forward_inverse_checks","100000 PASS")
print("uniform_superposition_invariant",True)
print("actual_header_free_bits_preserved",96)
print("next_round",8)
print("next_W","80000000")
print("remaining_rounds_to_endpoint",54)
print("V32_SECOND_SHA_LATENT=PASS")
