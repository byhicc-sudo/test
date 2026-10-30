#!/usr/bin/env python3
import math, time
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
CCX=np.zeros((8,8),dtype=complex)
for i in range(8):
    a=(i>>2)&1; b=(i>>1)&1
    j=i^(1 if a and b else 0)
    CCX[j,i]=1
CCX=CCX.reshape(2,2,2,2,2,2)

def g1(psi,G,q):
    psi.gate_(G,q,contract='swap+split',max_bond=8,cutoff=1e-8)
def g3(psi,G,a,b,c):
    psi.gate_(G,(a,b,c),contract='swap+split',max_bond=8,cutoff=1e-8)

print("PYTHON_REMOTE_SMOKE=START", flush=True)
print("quimb", quimb.__version__, flush=True)
print("sites", N, "free", len(FREE), "anc", len(ANC), flush=True)
psi=qtn.MPS_computational_state('0'*N)
for q in FREE: g1(psi,H,q)
print("prepared max_bond", max(psi.bond_sizes() or [1]), flush=True)

# 40-control reversible phase scaffold + uncompute.
for q in FREE: g1(psi,X,q)
g3(psi,CCX,FREE[0],FREE[1],ANC[0])
for j in range(2,40):
    g3(psi,CCX,ANC[j-2],FREE[j],ANC[j-1])
g1(psi,Z,ANC[-1])
for j in range(39,1,-1):
    g3(psi,CCX,ANC[j-2],FREE[j],ANC[j-1])
g3(psi,CCX,FREE[0],FREE[1],ANC[0])
for q in FREE: g1(psi,X,q)

norm=float(np.real(psi.H @ psi))
print("final max_bond", max(psi.bond_sizes() or [1]), flush=True)
print("norm", norm, flush=True)
assert abs(norm-1.0) < 1e-6
print("PYTHON_REMOTE_SMOKE=PASS", flush=True)
