#!/usr/bin/env python3
import math, hashlib, struct, time
import numpy as np
import quimb.tensor as qtn
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import reverse_cuthill_mckee

MASK=(1<<32)-1
IV=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]
K=[
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,
0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,
0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,
0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,
0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]

H=np.array([[1,1],[1,-1]],dtype=complex)/math.sqrt(2)
X=np.array([[0,1],[1,0]],dtype=complex)
T=np.diag([1,np.exp(1j*math.pi/4)]).astype(complex)
TD=np.diag([1,np.exp(-1j*math.pi/4)]).astype(complex)
CX=np.array([[1,0,0,0],[0,1,0,0],[0,0,0,1],[0,0,1,0]],dtype=complex).reshape(2,2,2,2)

class C:
    def __init__(self): self.next=0
    def reg(self,n=32):
        r=list(range(self.next,self.next+n)); self.next+=n; return r

def xg(gs,a): gs.append(('X',a))
def cxg(gs,a,b): gs.append(('CX',a,b))
def ccxg(gs,a,b,c): gs.append(('CCX',a,b,c))
def cp(gs,a,b):
    for x,y in zip(a,b): cxg(gs,x,y)
def tconst(gs,r,v):
    for i,q in enumerate(r):
        if (v>>i)&1: xg(gs,q)
def xor_sigma(gs,src,dst,rots):
    for i in range(32):
        for r in rots: cxg(gs,src[(i+r)&31],dst[i])
def ch(gs,e,f,g,d):
    for i in range(32):
        ccxg(gs,e[i],f[i],d[i]); xg(gs,e[i]); ccxg(gs,e[i],g[i],d[i]); xg(gs,e[i])
def maj(gs,a,b,c,d):
    for i in range(32):
        ccxg(gs,a[i],b[i],d[i]); ccxg(gs,a[i],c[i],d[i]); ccxg(gs,b[i],c[i],d[i])
def maj_carry(gs,a,b,cin):
    cxg(gs,a,b); cxg(gs,a,cin); ccxg(gs,b,cin,a)
def uma_carry(gs,a,b,cin):
    ccxg(gs,b,cin,a); cxg(gs,a,cin); cxg(gs,cin,b)
def add_inplace(gs,x,y,anc):
    maj_carry(gs,x[0],y[0],anc)
    for i in range(1,32): maj_carry(gs,x[i],y[i],x[i-1])
    for i in range(31,0,-1): uma_carry(gs,x[i],y[i],x[i-1])
    uma_carry(gs,x[0],y[0],anc)

c=C()
EXH=c.reg(); EXL=c.reg(); NON=c.reg()
W=[c.reg() for _ in range(16)]
S=[c.reg() for _ in range(8)]
anc=c.reg(1)[0]
rS1=c.reg(); rCH=c.reg(); rS0=c.reg(); rMJ=c.reg(); Kreg=c.reg()

prefix=hashlib.sha256(b'FOTON-JOB96-CB-PREFIX').digest()[:24]
suffix=hashlib.sha256(b'FOTON-JOB96-CB-SUFFIX').digest()[:24]
def words_be(b): return list(struct.unpack('>'+('I'*(len(b)//4)),b))
block=words_be(prefix)+[EXH,EXL]+words_be(suffix)+[0x80000000,0]

init_g=[]
for r,spec in zip(W,block):
    if isinstance(spec,int): tconst(init_g,r,spec)
    else: cp(init_g,spec,r)
for r,v in zip(S,IV): tconst(init_g,r,v)

def round_gates(t,regs):
    a,b,cw,d,e,f,g,h=regs
    w=W[t&15]
    gs=[]
    xor_sigma(gs,e,rS1,(6,11,25)); ch(gs,e,f,g,rCH)
    add_inplace(gs,rS1,h,anc); add_inplace(gs,rCH,h,anc)
    tconst(gs,Kreg,K[t]); add_inplace(gs,Kreg,h,anc); tconst(gs,Kreg,K[t])
    add_inplace(gs,w,h,anc)
    add_inplace(gs,h,d,anc)
    ch(gs,e,f,g,rCH); xor_sigma(gs,e,rS1,(6,11,25))
    xor_sigma(gs,a,rS0,(2,13,22)); maj(gs,a,b,cw,rMJ)
    add_inplace(gs,rS0,h,anc); add_inplace(gs,rMJ,h,anc)
    maj(gs,a,b,cw,rMJ); xor_sigma(gs,a,rS0,(2,13,22))
    return gs,[h,a,b,cw,d,e,f,g]

rounds=[]
regs=list(S)
for t in range(8):
    gs,regs=round_gates(t,regs)
    rounds.append(gs)

all_for_layout=init_g + [g for rr in rounds[:8] for g in rr]
rows=[]; cols=[]
for g in all_for_layout:
    qs=g[1:]
    for a in qs:
        for b in qs:
            if a!=b: rows.append(a); cols.append(b)
A=csr_matrix((np.ones(len(rows)),(rows,cols)),shape=(c.next,c.next))
perm=list(reverse_cuthill_mckee(A,symmetric_mode=True))
pos=np.empty(c.next,dtype=int)
for p,q in enumerate(perm): pos[q]=p

def span_stats(gs):
    spans=[]
    for g in gs:
        qs=[int(pos[q]) for q in g[1:]]
        if len(qs)>1: spans.append(max(qs)-min(qs))
    return (float(np.mean(spans)) if spans else 0.0, max(spans) if spans else 0)

print('=== V23 96-RAIL REAL JOB BOND PROBE ===',flush=True)
print('sites',c.next,flush=True)
print('free_coherent_rails',96,flush=True)
print('extranonce2',64,'nonce',32,flush=True)
print('rounds_built',len(rounds),flush=True)
print('init_gates',len(init_g),flush=True)
print('round_gate_counts',[len(x) for x in rounds],flush=True)
print('layout_avg_span_init10',span_stats(all_for_layout)[0],flush=True)
print('layout_max_span_init10',span_stats(all_for_layout)[1],flush=True)

MB=64; CO=1e-14
psi=qtn.MPS_computational_state('0'*c.next)
for q in EXH+EXL+NON:
    psi.gate_(H,int(pos[q]),contract='swap+split',max_bond=MB,cutoff=CO)

def g1(G,q):
    psi.gate_(G,int(pos[q]),contract='swap+split',max_bond=MB,cutoff=CO)
def g2(G,a,b):
    psi.gate_(G,(int(pos[a]),int(pos[b])),contract='swap+split',max_bond=MB,cutoff=CO)
def ccx(a,b,t):
    g1(H,t); g2(CX,b,t); g1(TD,t); g2(CX,a,t); g1(T,t); g2(CX,b,t); g1(TD,t); g2(CX,a,t)
    g1(T,b); g1(T,t); g1(H,t); g2(CX,a,b); g1(T,a); g1(TD,b); g2(CX,a,b)
def apply_gate(g):
    if g[0]=='X': g1(X,g[1])
    elif g[0]=='CX': g2(CX,g[1],g[2])
    elif g[0]=='CCX': ccx(g[1],g[2],g[3])

t0=time.time()
for i,g in enumerate(init_g,1):
    apply_gate(g)
print('INIT_PASS','bond',max(psi.bond_sizes() or [1]),'norm',float(np.real(psi.norm())),'sec',time.time()-t0,flush=True)

for t,gs in enumerate(rounds):
    rt=time.time()
    for j,g in enumerate(gs,1):
        apply_gate(g)
        if j%500==0:
            print(f'ROUND {t} gate {j}/{len(gs)} bond {max(psi.bond_sizes() or [1])}',flush=True)
    bond=max(psi.bond_sizes() or [1])
    norm=float(np.real(psi.norm()))
    print(f'ROUND_DONE {t} bond {bond} norm {norm:.16g} sec {time.time()-rt:.3f}',flush=True)
    if bond>=MB:
        print('BOND_CAP_REACHED',t,MB,flush=True)
        break
print('TOTAL_SEC',time.time()-t0,flush=True)
print('V23_PROBE_DONE',flush=True)
