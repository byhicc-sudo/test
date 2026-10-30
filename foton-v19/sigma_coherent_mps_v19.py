#!/usr/bin/env python3
import time, math, numpy as np
import quimb.tensor as qtn

H=np.array([[1,1],[1,-1]],dtype=complex)/math.sqrt(2)
CX=np.array([[1,0,0,0],[0,1,0,0],[0,0,0,1],[0,0,1,0]],dtype=complex).reshape(2,2,2,2)

ORDERS={
"sigma1":[46,7,15,25,41,2,20,55,59,33,45,51,60,32,21,6,11,16,1,42,47,3,37,12,29,38,30,54,36,61,28,50,26,56,24,40,17,8,63,22,19,10,14,58,27,52,34,53,35,0,48,13,9,49,62,43,23,5,39,31,4,57,44,18],
"sigma0":[12,3,33,14,56,23,45,44,43,54,24,42,63,0,53,34,2,25,32,13,55,11,1,21,52,15,22,41,26,4,57,51,10,46,5,36,35,61,47,16,28,58,62,38,31,50,8,37,27,17,18,20,6,9,39,59,48,30,29,49,40,19,7,60]
}
SHIFTS={"sigma1":[6,11,25],"sigma0":[2,13,22]}

def cut_rank_gf2(order,shifts):
    # graph-state entanglement rank proxy/exact for this bipartite CNOT-copy state
    adj=[set() for _ in range(64)]
    for i in range(32):
        s=32+i
        for sh in shifts:
            e=(i+sh)&31
            adj[e].add(s); adj[s].add(e)
    def rank(rows):
        basis={}
        r=0
        for x in rows:
            while x:
                p=x.bit_length()-1
                if p in basis: x^=basis[p]
                else: basis[p]=x; r+=1; break
        return r
    left=set(); right=set(order); prof=[]
    for v in order[:-1]:
        left.add(v); right.remove(v)
        rr=list(right); pos={x:i for i,x in enumerate(rr)}
        rows=[]
        for u in left:
            m=0
            for w in adj[u]:
                if w in pos: m|=1<<pos[w]
            rows.append(m)
        prof.append(rank(rows))
    return max(prof),prof

def run(name):
    order=ORDERS[name]; shifts=SHIFTS[name]
    pos={logical:i for i,logical in enumerate(order)}
    rmax,prof=cut_rank_gf2(order,shifts)
    print(f'=== V19 {name.upper()} COHERENT MPS ===',flush=True)
    print('predicted_max_cut_rank',rmax,flush=True)
    print('predicted_bond_upper',2**rmax,flush=True)
    psi=qtn.MPS_computational_state('0'*64)
    for e in range(32):
        psi.gate_(H,pos[e],contract='swap+split',max_bond=1024,cutoff=1e-14)
    initial=psi.copy()
    edges=[]
    for i in range(32):
        s=32+i
        for sh in shifts:
            e=(i+sh)&31
            edges.append((abs(pos[e]-pos[s]),e,s))
    edges.sort()
    t0=time.time(); peak=1
    for n,(_,e,s) in enumerate(edges,1):
        psi.gate_(CX,(pos[e],pos[s]),contract='swap+split',max_bond=1024,cutoff=1e-14)
        peak=max(peak,max(psi.bond_sizes() or [1]))
        if n%16==0: print('forward',n,'peak_bond',peak,'sec',time.time()-t0,flush=True)
    fwd=time.time()-t0
    norm=float(np.real(psi.norm()))
    print('forward_seconds',fwd,flush=True)
    print('forward_peak_bond',peak,flush=True)
    print('forward_final_bond',max(psi.bond_sizes() or [1]),flush=True)
    print('forward_norm',format(norm,'.16g'),flush=True)
    t1=time.time()
    for _,e,s in reversed(edges):
        psi.gate_(CX,(pos[e],pos[s]),contract='swap+split',max_bond=1024,cutoff=1e-14)
    inv=time.time()-t1
    ov=complex(initial.H @ psi)
    print('inverse_seconds',inv,flush=True)
    print('restore_overlap',abs(ov),flush=True)
    print('restore_norm',float(np.real(psi.norm())),flush=True)
    assert abs(norm-1)<1e-9
    assert abs(abs(ov)-1)<1e-8
    print(name.upper()+'_COHERENT_MPS=PASS',flush=True)

for n in ('sigma1','sigma0'):
    run(n)
print('V19_SIGMA_LAYOUT=PASS',flush=True)
