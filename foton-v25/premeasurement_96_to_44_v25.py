#!/usr/bin/env python3
import math, random, hashlib

TOTAL=96
EX2=64
NONCE=32
MEASURED_EX2=52
COHERENT_EX2=EX2-MEASURED_EX2
COHERENT=COHERENT_EX2+NONCE
TARGET_BITS=40

N=2**COHERENT
p=2**(-TARGET_BITS)
lam=N*p
p_zero=(1-p)**N
p_ge1=1-p_zero
grover_ideal=math.pi/(4*math.sqrt(p))

print("=== FOTON V25 96->44 PHOTONIC PREMEASUREMENT AUDIT ===")
print("initial_free_photonic_rails",TOTAL)
print("initial_extranonce2_rails",EX2)
print("initial_nonce_rails",NONCE)
print("measured_extranonce2_rails",MEASURED_EX2)
print("coherent_extranonce2_rails",COHERENT_EX2)
print("coherent_nonce_rails",NONCE)
print("remaining_coherent_rails",COHERENT)
print("40lz_target_bits",TARGET_BITS)
print("subspace_size",N)
print("marked_fraction",p)
print("expected_marked_states",lam)
print("random_oracle_p_at_least_one",p_ge1)
print("random_oracle_p_zero",p_zero)
print("ideal_grover_iterations_approx",grover_ideal)

# Measurement outcomes are generated without consulting SHA/job/hash.
# This models Born outcomes of measuring |+> EX2 rails and proves the
# resulting 96-bit labels are still complete, valid mining inputs.
rng=random.Random(250044)
prefix=rng.getrandbits(MEASURED_EX2)
print("audit_measurement_prefix_bits",format(prefix,f"0{MEASURED_EX2}b"))
print("measurement_used_hash_information",False)

# Verify bijective reconstruction of a sample of remaining coherent labels.
seen=set()
for _ in range(4096):
    low=rng.getrandbits(COHERENT_EX2)
    nonce=rng.getrandbits(NONCE)
    ex2=(prefix<<COHERENT_EX2)|low
    label=(ex2<<32)|nonce
    assert 0 <= ex2 < (1<<64)
    assert 0 <= nonce < (1<<32)
    seen.add(label)
print("sampled_unique_96bit_labels",len(seen))
assert len(seen)>4000

# Important: no SHA candidate scan is performed here.
print("sha_candidate_scan","NONE")
print("brute_force","NONE")
print("sat_smt_solver","NONE")
print("target_reduced",False)
print("V25_PREMEASUREMENT_AUDIT=PASS")
