import math
from typing import Any, Dict, List, Tuple

from app.config import settings
from app.models import EdgeBreakdown
from app.scoring.rules import (
    points_pct_edge,
    home_away_edge,
    injuries_edge,
    goals_edge,
    form_edge,
    head_to_head_edge,
    goalie_edge,
)


def logistic_prob(diff: int) -> float:
    capped = max(-settings.max_abs_diff, min(settings.max_abs_diff, diff))
    T = settings.logistic_temperature
    return 1.0 / (1.0 + math.exp(-capped / T))


def projected_total_goals(home: Dict[str, Any], away: Dict[str, Any]) -> float:
    # Quick MVP using ranks (works immediately with your current snapshots)
    base = 6.0

    # ranks: 1 best, 32 worst (lower GA rank = better defense)
    gf_boost = (
        (16 - int(home.get("goals_for_rank", 16)))
        + (16 - int(away.get("goals_for_rank", 16)))
    ) / 16.0

    ga_boost = (
        (int(home.get("goals_against_rank", 16)) - 16)
        + (int(away.get("goals_against_rank", 16)) - 16)
    ) / 16.0

    total = base + (0.6 * gf_boost) + (0.6 * ga_boost)

    # clamp
    if total < 4.0:
        total = 4.0
    if total > 8.5:
        total = 8.5

    return float(total)


def score_matchup(
    home: Dict[str, Any],
    away: Dict[str, Any],
    h2h: Dict[str, Any] | None,
) -> Tuple[int, int, int, float, float, float, List[EdgeBreakdown]]:
    breakdown: List[EdgeBreakdown] = []
    hs, as_ = 0, 0

    for fn in (points_pct_edge, home_away_edge, injuries_edge, goals_edge, form_edge, goalie_edge):
        dh, da = fn(home, away, breakdown)
        hs += dh
        as_ += da

    dh2h, da2h = head_to_head_edge(h2h, home["team"], away["team"], breakdown)
    hs += dh2h
    as_ += da2h

    diff = hs - as_
    p_home = logistic_prob(diff)
    p_away = 1.0 - p_home

    ptg = projected_total_goals(home, away)

    return hs, as_, diff, p_home, p_away, ptg, breakdown
