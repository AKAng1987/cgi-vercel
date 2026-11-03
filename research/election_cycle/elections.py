"""elections.py -- the 19 US midterm election dates 1950-2022 (computed: Tuesday after the first Monday in November) and the
hand-entered results (EXPLORATORY ONLY; see RESULTS_SOURCES)."""
import datetime as dt

def election_day(year: int) -> dt.date:
    d = dt.date(year, 11, 1)
    first_monday = d + dt.timedelta(days=(0 - d.weekday()) % 7)
    return first_monday + dt.timedelta(days=1)

MIDTERMS = list(range(1950, 2023, 4))
DATES = {y: election_day(y) for y in MIDTERMS}
LIVE = election_day(2026)

# ---- hand-entered results: EXPLORATORY ONLY -------------------------------------------------------------------------------
# House: history.house.gov/Institution/Party-Divisions/Party-Divisions/ (House Clerk), fetched 2026-11-04. Seats at the START of
# each Congress (D, R, other). Senate: the senate.gov history page returned HTTP 403 to scripts, so the Senate counts and majority
# come from en.wikipedia.org/wiki/Party_divisions_of_United_States_Congresses (fetched 2026-11-04); this is a source deviation.
# President's party at each midterm: standard presidential roll (not fetched; public record).
HOUSE = {81: (263, 171, 1), 82: (235, 199, 1), 83: (213, 221, 1), 84: (232, 203, 0), 85: (232, 203, 0), 86: (282, 153, 1),
         87: (264, 173, 0), 88: (258, 176, 1), 89: (295, 140, 0), 90: (248, 187, 0), 91: (243, 192, 0), 92: (255, 180, 0),
         93: (243, 192, 0), 94: (291, 144, 0), 95: (292, 143, 0), 96: (278, 157, 0), 97: (243, 192, 0), 98: (269, 166, 0),
         99: (253, 181, 0), 100: (258, 177, 0), 101: (260, 175, 0), 102: (267, 167, 1), 103: (258, 176, 1), 104: (204, 230, 1),
         105: (207, 226, 2), 106: (211, 223, 1), 107: (212, 221, 2), 108: (205, 229, 1), 109: (202, 232, 1), 110: (233, 202, 0),
         111: (257, 178, 0), 112: (193, 242, 0), 113: (201, 234, 0), 114: (188, 247, 0), 115: (194, 241, 0), 116: (235, 199, 0),
         117: (222, 212, 0), 118: (213, 222, 0)}
# Senate majority at the start of the Congress (D includes caucusing independents where the source says so).
SENATE_MAJ = {81: "D", 82: "D", 83: "R", 84: "D", 85: "D", 86: "D", 87: "D", 88: "D", 89: "D", 90: "D", 91: "D", 92: "D",
              93: "D", 94: "D", 95: "D", 96: "D", 97: "R", 98: "R", 99: "R", 100: "D", 101: "D", 102: "D", 103: "D", 104: "R",
              105: "R", 106: "R", 107: "R", 108: "R", 109: "R", 110: "D", 111: "D", 112: "D", 113: "D", 114: "R", 115: "R",
              116: "R", 117: "R", 118: "D"}
PRESIDENT = {1950: "D", 1954: "R", 1958: "R", 1962: "D", 1966: "D", 1970: "R", 1974: "R", 1978: "D", 1982: "R", 1986: "R",
             1990: "R", 1994: "D", 1998: "D", 2002: "R", 2006: "R", 2010: "D", 2014: "D", 2018: "R", 2022: "D"}


def congress_after(year: int) -> int:
    return 82 + (year - 1950) // 2


def results(year: int) -> dict:
    c = congress_after(year)
    p = PRESIDENT[year]
    idx = 0 if p == "D" else 1
    seats_before, seats_after = HOUSE[c - 1][idx], HOUSE[c][idx]
    house_maj = "D" if HOUSE[c][0] > HOUSE[c][1] else "R"
    house_maj_before = "D" if HOUSE[c - 1][0] > HOUSE[c - 1][1] else "R"
    sen = SENATE_MAJ[c]
    return {"president": p, "pres_house_seat_change": seats_after - seats_before, "house_after": house_maj,
            "house_flipped": house_maj != house_maj_before, "senate_after": sen,
            "pres_lost_house": house_maj != p, "pres_lost_senate": sen != p,
            "divided_after": not (house_maj == p and sen == p)}
