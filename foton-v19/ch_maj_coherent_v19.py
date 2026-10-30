#!/usr/bin/env python3
import math,time,numpy as np
import quimb.tensor as qtn

H=np.array([[1,1],[1,-1]],complex)/math.sqrt(2)
T=np.diag([1,np.exp(1j*math.pi/4)]).astype(complex)
TD=np.diag([1,np.exp(-1j*math.pi/4)]).astype(complex)
CX=np.array([[1,0,0,0],[0,1,0,0],[0,0,0,1],[0,0,1,0]],complex).reshape(2,2,2,2)
MB=64; CO=1e-14

def g1(psi,G,q):
    psi.gate_(G,q,contract='swap+split',max_bond=MB,cutoff=CO)
def g2(psi,G,a,b):
    psi.gate_(G,(a,b),contract='swap+split',max_bond=MB,cutoff=CO)
def ccx(psi,a,b,t):
    g1(psi,H,t); g2(psi,CX,b,t); g1(psi,TD,t); g2(psi,CX,a,t)
    g1(psi,T,t); g2(psi,CX,b,t); g1(psi,TD,t); g2(psi,CX,a,t)
    g1(psi,T,b); g1(psi,T,t); g1(psi,H,t); g2(psi,CX,a,b)
    g1(psi,T,a); g1(psi,TD,b); g2(psi,CX,a,b)

def run(kind):
    # per-bit interleaving: x,y,z,s
    N=128
    psi=qtn.MPS_computational_state('0'*N)
    for i in range(32):
        base=4*i
        for q in (base,base+1,base+2):
            g1(psi,H,q)
    peak=1; t0=time.time()
    for i in range(32):
        a,b,c,s=4*i,4*i+1,4*i+2,4*i+3
        if kind=='ch':
            g2(psi,CX,c,s)
            ccx(psi,a,b,s)
            ccx(psi,a,c,s)
        else:
            ccx(psi,a,b,s)
            ccx(psi,a,c,s)
            ccx(psi,b,c,s)
        peak=max(peak,max(psi.bond_sizes() or [1]))
    fwd=time.time()-t0
    norm=float(np.real(psi.norm()))
    print(kind,'forward_sec',fwd,'peak_bond',peak,'final_bond',max(psi.bond_sizes() or [1]),'norm',norm,flush=True)
    t1=time.time()
    for i in reversed(range(32)):
        a,b,c,s=4*i,4*i+1,4*i+2,4*i+3
        if kind=='ch':
            ccx(psi,a,c,s)
            ccx(psi,a,b,s)
            g2(psi,CX,c,s)
        else:
            ccx(psi,b,c,s)
            ccx(psi,a,c,s)
            ccx(psi,a,b,s)
    inv=time.time()-t1
    for i in range(32):
        base=4*i
        for q in (base,base+1,base+2):
            g1(psi,H,q)
    restore_norm=float(np.real(psi.norm()))
    amp0=complex(psi.amplitude('0'*N))
    restore_prob=abs(amp0)**2
    print(kind,'inverse_sec',inv,'restore_prob_zero',restore_prob,'restore_norm',restore_norm,flush=True)
    assert abs(norm-1)<1e-9 and abs(restore_norm-1)<1e-9 and abs(restore_prob-1)<1e-8
    print(kind.upper()+'_COHERENT_MPS=PASS',flush=True)

print('=== V19 CH MAJ COHERENT MPS ===',flush=True)
run('ch'); run('maj')
print('V19_CH_MAJ=PASS',flush=True)
