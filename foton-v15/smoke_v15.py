#!/usr/bin/env python3
import math
import numpy as np
import quimb
import quimb.tensor as qtn
import cotengra, scipy

N=1615
FREE=list(range(40))
ANC=list(range(40,79))

H=np.array([[1,1],[1,-1]],dtype=complex)/math.sqrt(2)
X=np.array([[0,1],[1,0]],dtype=complex)
Z=np.array([[1,0],[0,-1]],dtype=complex)
T=np.diag([1,np.exp(1j*math.pi/4)]).astype(complex)
TD=np.diag([1,np.exp(-1j*math.pi/4)]).astype(complex)
CX=np.array([[1,0,0,0],
             [0,1,0,0],
             [0,0,0,1],
             [0,0,1,0]],dtype=complex).reshape(2,2,2,2)

MAX_BOND=8
CUTOFF=1e-8

def g1(psi,G,q):
    psi.gate_(G,q,contract='swap+split',max_bond=MAX_BOND,cutoff=CUTOFF)

def g2(psi,G,a,b):
    psi.gate_(G,(a,b),contract='swap+split',max_bond=MAX_BOND,cutoff=CUTOFF)

def ccx(psi,a,b,t):
    # Exact Toffoli decomposition using only 1- and 2-site gates.
    g1(psi,H,t)
    g2(psi,CX,b,t)
    g1(psi,TD,t)
    g2(psi,CX,a,t)
    g1(psi,T,t)
    g2(psi,CX,b,t)
    g1(psi,TD,t)
    g2(psi,CX,a,t)
    g1(psi,T,b)
    g1(psi,T,t)
    g1(psi,H,t)
    g2(psi,CX,a,b)
    g1(psi,T,a)
    g1(psi,TD,b)
    g2(psi,CX,a,b)

print("PYTHON_REMOTE_SMOKE=START", flush=True)
print("quimb", quimb.__version__, flush=True)
print("sites",N,"free",len(FREE),"anc",len(ANC), flush=True)

psi=qtn.MPS_computational_state('0'*N)
for q in FREE:
    g1(psi,H,q)
print("prepared max_bond",max(psi.bond_sizes() or [1]), flush=True)

for q in FREE:
    g1(psi,X,q)

ccx(psi,FREE[0],FREE[1],ANC[0])
for j in range(2,40):
    ccx(psi,ANC[j-2],FREE[j],ANC[j-1])

g1(psi,Z,ANC[-1])

for j in range(39,1,-1):
    ccx(psi,ANC[j-2],FREE[j],ANC[j-1])
ccx(psi,FREE[0],FREE[1],ANC[0])

for q in FREE:
    g1(psi,X,q)

norm=float(np.real(psi.H @ psi))
print("final max_bond",max(psi.bond_sizes() or [1]), flush=True)
print("norm",norm, flush=True)
assert abs(norm-1.0) < 1e-6
print("PYTHON_REMOTE_SMOKE=PASS", flush=True)
