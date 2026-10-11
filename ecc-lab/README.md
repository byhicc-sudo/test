# NEXIS ECC computational lab

This folder holds bounded, deterministic secp256k1 tests on synthetic keys. These are regression tests, **not** an always-on cryptographic key-search service. GitHub Actions runners are limited to software development and testing.

* Test 24-bit synthetic key `0xFE9E9D` and its compressed public key.
* Verify that reconstructed coordinates match, with all private test values confined to fixtures.
* Verify 64-bit target point syntax and the algebraic equivalence of two-end branches.

The benchmark must not assert that a real 64-bit or 256-bit private scalar has been recovered unless `kG=P` was directly verified.
