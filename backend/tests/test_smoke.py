"""Smoke test so CI has a green baseline from Iteration 0.

Real per-component test suites land in later iterations (see docs/TESTING.md):
  - tests/test_c1_*.py  numeric safeguard, CER/NAR
  - tests/test_c2_*.py  row clustering, chunk schema
  - tests/test_c3_*.py  plan validation, arithmetic accuracy
  - tests/test_c4_*.py  normalization, cross-doc recall
"""


def test_smoke():
    assert True
