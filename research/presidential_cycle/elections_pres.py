"""elections_pres.py -- the 19 US presidential Election Days 1952-2024 (computed) and hand-entered public facts (EXPLORATORY ONLY).
Facts are the public record (not fetched): winner's party, party of the president before the vote, whether that president ran.
2024 is counted as an open seat: the incumbent withdrew and the incumbent party ran a different candidate."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "election_cycle"))
from elections import election_day, HOUSE, congress_after

YEARS = list(range(1952, 2025, 4))
DATES = {y: election_day(y) for y in YEARS}
WINNER = {1952: "R", 1956: "R", 1960: "D", 1964: "D", 1968: "R", 1972: "R", 1976: "D", 1980: "R", 1984: "R", 1988: "R", 1992: "D",
          1996: "D", 2000: "R", 2004: "R", 2008: "D", 2012: "D", 2016: "R", 2020: "D", 2024: "R"}
INCUMBENT_PARTY = {1952: "D", 1956: "R", 1960: "R", 1964: "D", 1968: "D", 1972: "R", 1976: "R", 1980: "D", 1984: "R", 1988: "R", 1992: "R",
                   1996: "D", 2000: "D", 2004: "R", 2008: "R", 2012: "D", 2016: "D", 2020: "R", 2024: "D"}
INCUMBENT_RAN = {1952: False, 1956: True, 1960: False, 1964: True, 1968: False, 1972: True, 1976: True, 1980: True, 1984: True, 1988: False,
                 1992: True, 1996: True, 2000: False, 2004: True, 2008: False, 2012: True, 2016: False, 2020: True, 2024: False}


# 119th Congress (elected 2024), House Clerk party divisions at the start of the Congress (D, R, other); not in election_cycle's table.
H119 = (215, 220, 0)


def house_maj(c):
    d, r, _ = H119 if c == 119 else HOUSE[c]
    return "D" if d > r else "R"


def facts(y):
    c = congress_after(y)
    return {"house_before": house_maj(c - 1), "house_after": house_maj(c), "house_flipped": house_maj(c - 1) != house_maj(c),
            "winner": WINNER[y], "incumbent_party": INCUMBENT_PARTY[y], "party_change": WINNER[y] != INCUMBENT_PARTY[y],
            "incumbent_ran": INCUMBENT_RAN[y]}
