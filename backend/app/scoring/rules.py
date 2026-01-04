from typing import Any, Dict, List, Tuple
from app.models import EdgeBreakdown

def _add_edge(breakdown: List[EdgeBreakdown], factor: str, team: str | None, points: int, reason: str):
    breakdown.append(EdgeBreakdown(factor=factor, team=team, points=points, reason=reason))

def points_pct_edge(home: Dict[str, Any], away: Dict[str, Any], breakdown: List[EdgeBreakdown]) -> Tuple[int, int]:
    hp = home.get("points_pct")
    ap = away.get("points_pct")
    if hp is None or ap is None:
        _add_edge(breakdown, "points_pct", None, 0, "Missing points% data")
        return 0, 0
    if hp > ap:
        _add_edge(breakdown, "points_pct", home["team"], +5, "Higher points%")
        return +5, 0
    if ap > hp:
        _add_edge(breakdown, "points_pct", away["team"], +5, "Higher points%")
        return 0, +5
    _add_edge(breakdown, "points_pct", None, 0, "Equal points%")
    return 0, 0

def home_away_edge(home: Dict[str, Any], away: Dict[str, Any], breakdown: List[EdgeBreakdown]) -> Tuple[int, int]:
    hh = home.get("home_points_pct")
    aa = away.get("away_points_pct")
    if hh is None or aa is None:
        _add_edge(breakdown, "home_away", None, 0, "Missing home/away data")
        return 0, 0

    home_winning = hh > 0.5
    away_winning = aa > 0.5

    # Strong edge cases
    if home_winning and not away_winning:
        _add_edge(breakdown, "home_away", home["team"], +2, "Home winning; away losing")
        return +2, 0
    if away_winning and not home_winning:
        _add_edge(breakdown, "home_away", away["team"], +2, "Away winning; home losing")
        return 0, +2

    # Both winning => slight home edge
    if home_winning and away_winning:
        _add_edge(breakdown, "home_away", home["team"], +1, "Both winning splits; home slight edge")
        return +1, 0

    # Both losing => slight home edge (your explanation)
    if (not home_winning) and (not away_winning):
        _add_edge(breakdown, "home_away", home["team"], +1, "Both losing splits; home slight edge")
        return +1, 0

    _add_edge(breakdown, "home_away", None, 0, "No meaningful split edge")
    return 0, 0

def injuries_edge(home: Dict[str, Any], away: Dict[str, Any], breakdown: List[EdgeBreakdown]) -> Tuple[int, int]:
    # Only penalize for confirmed OUT players (you’ll enforce that in data layer)
    h_top15 = int(home.get("out_top15_scorers") or 0)
    a_top15 = int(away.get("out_top15_scorers") or 0)
    h_top50 = int(home.get("out_top50_scorers") or 0)
    a_top50 = int(away.get("out_top50_scorers") or 0)

    hs = 0
    as_ = 0
    if h_top15 > 0:
        hs -= 5
        _add_edge(breakdown, "injuries", home["team"], -5, f"Missing top-15 scorer(s): {h_top15}")
    elif h_top50 > 0:
        hs -= 3
        _add_edge(breakdown, "injuries", home["team"], -3, f"Missing top-50 scorer(s): {h_top50}")

    if a_top15 > 0:
        as_ -= 5
        _add_edge(breakdown, "injuries", away["team"], -5, f"Missing top-15 scorer(s): {a_top15}")
    elif a_top50 > 0:
        as_ -= 3
        _add_edge(breakdown, "injuries", away["team"], -3, f"Missing top-50 scorer(s): {a_top50}")

    if hs == 0 and as_ == 0:
        _add_edge(breakdown, "injuries", None, 0, "No significant scoring injuries")
    return hs, as_

def goals_edge(home: Dict[str, Any], away: Dict[str, Any], breakdown: List[EdgeBreakdown]) -> Tuple[int, int]:
    hgfr = home.get("goals_for_rank")
    hgaw = home.get("goals_against_rank")
    agfr = away.get("goals_for_rank")
    agaw = away.get("goals_against_rank")

    if None in (hgfr, hgaw, agfr, agaw):
        _add_edge(breakdown, "goals_balance", None, 0, "Missing goals rank data")
        return 0, 0

    def elite(gfr, gaw) -> bool:
        return (gfr <= 15) and (gaw <= 15)

    def poor(gfr, gaw) -> bool:
        return (gfr >= 18) and (gaw >= 18)  # bottom ~15 in a 32-team league

    home_elite = elite(hgfr, hgaw)
    away_elite = elite(agfr, agaw)
    home_poor = poor(hgfr, hgaw)
    away_poor = poor(agfr, agaw)

    if home_elite and not away_elite:
        _add_edge(breakdown, "goals_balance", home["team"], +2, "Top-15 goals for AND top-15 goals against")
        return +2, 0
    if away_elite and not home_elite:
        _add_edge(breakdown, "goals_balance", away["team"], +2, "Top-15 goals for AND top-15 goals against")
        return 0, +2

    if home_poor and not away_poor:
        _add_edge(breakdown, "goals_balance", home["team"], -2, "Bottom-15 goals for AND bottom-15 goals against")
        return -2, 0
    if away_poor and not home_poor:
        _add_edge(breakdown, "goals_balance", away["team"], -2, "Bottom-15 goals for AND bottom-15 goals against")
        return 0, -2

    _add_edge(breakdown, "goals_balance", None, 0, "No clear goals balance edge")
    return 0, 0

def form_edge(home: Dict[str, Any], away: Dict[str, Any], breakdown: List[EdgeBreakdown]) -> Tuple[int, int]:
    def edge(team: Dict[str, Any]) -> int:
        last10 = team.get("last10_points_pct")
        stype = team.get("streak_type")
        if last10 is None or stype not in ("W", "L", None):
            return 0

        above = last10 > 0.5
        below = last10 < 0.5
        streak_w = stype == "W"
        streak_l = stype == "L"

        if above and streak_w:
            return +2
        if above and streak_l:
            return -2
        if below and streak_l:
            return -2
        if below and streak_w:
            return +1  # your "slight edge"
        return 0

    hs = edge(home)
    as_ = edge(away)

    # If both equal, call it neutral in explanation
    if hs == as_:
        _add_edge(breakdown, "form", None, 0, "Form factors offset or equal")
        return 0, 0

    if hs != 0:
        _add_edge(breakdown, "form", home["team"], hs, "Last 10 + streak effect")
    if as_ != 0:
        _add_edge(breakdown, "form", away["team"], as_, "Last 10 + streak effect")
    return hs, as_

def head_to_head_edge(h2h: Dict[str, Any] | None, home_team: str, away_team: str, breakdown: List[EdgeBreakdown]) -> Tuple[int, int]:
    if not h2h:
        _add_edge(breakdown, "h2h_recent", None, 0, "No head-to-head data available")
        return 0, 0

    home_wins = h2h.get("home_wins")
    away_wins = h2h.get("away_wins")
    games_found = int(h2h.get("games_found") or 0)

    if home_wins is None or away_wins is None or games_found <= 0:
        _add_edge(breakdown, "h2h_recent", None, 0, "Incomplete head-to-head data")
        return 0, 0

    # Scale points by sample size
    if games_found >= 5:
        pts = 3
    elif games_found >= 3:
        pts = 2
    elif games_found >= 2:
        pts = 1
    else:
        pts = 0

    if pts == 0 or home_wins == away_wins:
        _add_edge(breakdown, "h2h_recent", None, 0, f"Even/too-small H2H sample (n={games_found})")
        return 0, 0

    if home_wins > away_wins:
        _add_edge(breakdown, "h2h_recent", home_team, pts, f"Better H2H in last {games_found} games")
        return pts, 0

    _add_edge(breakdown, "h2h_recent", away_team, pts, f"Better H2H in last {games_found} games")
    return 0, pts


def goalie_edge(home: Dict[str, Any], away: Dict[str, Any], breakdown: List[EdgeBreakdown]) -> Tuple[int, int]:
    h = int(home.get("goalie_factor") or 0)
    a = int(away.get("goalie_factor") or 0)

    if h == a:
        _add_edge(breakdown, "goalie", None, 0, "Equal team goalie factor")
        return 0, 0

    if h > a:
        _add_edge(breakdown, "goalie", home["team"], h - a, "Stronger team goalie (by SV% & usage)")
        return h - a, 0
    else:
        _add_edge(breakdown, "goalie", away["team"], a - h, "Stronger team goalie (by SV% & usage)")
        return 0, a - h
