"""check_liquidity_flip.py -- the market-implied FOMC flip must follow the compass rule: only a HIKE is "Tightening".

    api/.venv/bin/python scripts/check_liquidity_flip.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
import markov_data as m  # noqa: E402

fut = {"p_hike": 0.18, "p_hold": 0.82, "p_cut": 0.0}          # the Oct 20 2026 pricing
assert abs(m.liquidity_flip_p(fut, 0) - 0.82) < 1e-9, "tight axis: a hold flips it to easing"
assert abs(m.liquidity_flip_p(fut, 1) - 0.18) < 1e-9, "easing axis: only a hike flips it"
cut = {"p_hike": 0.0, "p_hold": 0.3, "p_cut": 0.7}
assert abs(m.liquidity_flip_p(cut, 0) - 1.0) < 1e-9, "tight axis: hold or cut always flips it"
hike = {"p_hike": 1.0, "p_hold": 0.0, "p_cut": 0.0}
assert m.liquidity_flip_p(hike, 0) == 0.0 and m.liquidity_flip_p(hike, 1) == 1.0
print("OK: liquidity flip = P(hike) when easing, P(hold)+P(cut) when tight")
