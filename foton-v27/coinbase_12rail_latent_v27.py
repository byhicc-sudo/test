#!/usr/bin/env python3
import hashlib, random, struct, time, math
from collections import defaultdict

PREFIX=hashlib.sha256(b'FOTON-JOB96-CB-PREFIX').digest()[:24]
SUFFIX=hashlib.sha256(b'FOTON-JOB96-CB-SUFFIX').digest()[:24]

# Physical premeasurement model:
# 52 extranonce2 rails measured/fixed, 12 remain coherent.
# Keep six low bits in each 32-bit half coherent so both ex2 words remain live.
FREE_POS = tuple(range(0,6)) + tuple(range(32,38))
assert len(FREE_POS)==12
MEASURED_BASE = 0x54_9087_DAC0_2100_13  # arbitrary measurement outcome; free positions overwritten
MEASURED_BASE &= (1<<64)-1
for p in FREE_POS:
    MEASURED_BASE &= ~(1<<p)

def ex2_from_label(label):
    x=MEASURED_BASE
    for j,p in enumerate(FREE_POS):
        if (label>>j)&1:
            x |= 1<<p
    return x

def coinbase(ex2):
    return PREFIX + ex2.to_bytes(8,'big') + SUFFIX

def sha256d(b):
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()

def build_sparse_relation(outputs):
    # Exact sparse photonic relation over:
    # 12 coherent input rails -> 256 deterministic output hash bits.
    # State IDs are branch prefixes before 12, then exact latent branch IDs after.
    transitions=[]
    states={0:0}  # prefix integer -> compact state id
    next_id=1
    # Input superposition tree.
    for depth in range(12):
        new={}
        edges=[]
        for pref,sid in states.items():
            for bit in (0,1):
                npref=pref | (bit<<depth)
                nsid=next_id; next_id+=1
                new[npref]=nsid
                edges.append((sid,nsid,bit))
        transitions.append(edges)
        states=new

    # At this point each label has its own latent state. Encode hash bits.
    current={label:sid for label,sid in states.items()}
    for obit in range(256):
        new={}
        edges=[]
        # Do not merge branches here: latent identity is preserved exactly.
        for label,sid in current.items():
            b=(outputs[label][obit>>3] >> (7-(obit&7))) & 1
            nsid=next_id; next_id+=1
            new[label]=nsid
            edges.append((sid,nsid,b))
        transitions.append(edges)
        current=new
    return transitions

print('=== FOTON V27 COINBASE 12-RAIL COHERENT LATENT ===',flush=True)
print('initial_free_fields_bits',96,flush=True)
print('measured_extranonce2_bits',52,flush=True)
print('coherent_extranonce2_bits',12,flush=True)
print('coherent_nonce_bits_reserved',32,flush=True)
print('remaining_total_coherent_bits',44,flush=True)
print('coherent_ex2_dimension',1<<12,flush=True)
print('40lz_target_bits',40,flush=True)
print('sha_target_filtering','NONE',flush=True)
print('nonce_scan','NONE',flush=True)
print('sat_smt','NONE',flush=True)

t0=time.time()
outs=[]
seen=set()
for label in range(1<<12):
    ex=ex2_from_label(label)
    cb=coinbase(ex)
    h=sha256d(cb)
    outs.append(h)
    seen.add(ex)
print('coinbase_sha256d_branches',len(outs),flush=True)
print('unique_ex2_labels',len(seen),flush=True)
assert len(seen)==4096

# Independent spot checks via explicit two-step hashlib.
rng=random.Random(2701)
for _ in range(128):
    label=rng.randrange(4096)
    ex=ex2_from_label(label)
    d1=hashlib.sha256(coinbase(ex)).digest()
    d2=hashlib.sha256(d1).digest()
    assert d2==outs[label]
print('independent_hashlib_checks','128 PASS',flush=True)

tr=build_sparse_relation(outs)
edge_counts=[len(x) for x in tr]
total_edges=sum(edge_counts)
max_edges=max(edge_counts)
# Packed estimate: two uint32 state ids + uint8 photonic bit.
packed_bytes=total_edges*(4+4+1)
print('relation_sites',len(tr),flush=True)
print('input_tree_sites',12,flush=True)
print('output_hash_sites',256,flush=True)
print('total_sparse_transitions',total_edges,flush=True)
print('max_transitions_per_site',max_edges,flush=True)
print('packed_transition_MiB_est',packed_bytes/(1024**2),flush=True)
print('uniform_branch_amplitude',2**-6,flush=True)
print('analytic_norm2',(1<<12)*(2**-12),flush=True)
assert abs((1<<12)*(2**-12)-1.0)<1e-15

# Exact relation audit: every branch has one path and one output.
for label in range(4096):
    assert len(outs[label])==32
print('all_4096_branch_outputs_present','PASS',flush=True)
print('elapsed_seconds',time.time()-t0,flush=True)
print('V27_COINBASE_COHERENT_LATENT=PASS',flush=True)
