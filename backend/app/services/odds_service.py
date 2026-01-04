from typing import Any, Dict, List

from app.models import TodayResponse, MatchupResult, MatchupScore, MatchupProb
from app.scoring.engine import score_matchup


def _default_snapshot(team: str) -> Dict[str, Any]:
    """
    Neutral fallback snapshot so the scoring engine never crashes.
    Produces near 50/50 odds until real stats are wired in.
    """
    return {
        "team": team,
        "points_pct": 0.5,
        "home_points_pct": 0.5,
        "away_points_pct": 0.5,
        "goals_for_rank": 16,
        "goals_against_rank": 16,
        "last10_points_pct": 0.5,
        "streak_type": None,
        "streak_len": 0,
        "out_top50_scorers": 0,
        "out_top15_scorers": 0,
        "starting_goalie_is_top10": None,
        "starting_goalie_is_backup": None,
        "goalie_factor": 0,
    }


async def build_today_odds(
    today_str: str,
    games: List[Dict[str, Any]],
    client,
) -> TodayResponse:
    matchups: List[MatchupResult] = []

    for g in games:
        home_abbrev = g["homeAbbrev"]
        away_abbrev = g["awayAbbrev"]

        home_snap = await client.get_team_snapshot(home_abbrev, game_id=g["gameId"])
        away_snap = await client.get_team_snapshot(away_abbrev, game_id=g["gameId"])

        if not home_snap:
            home_snap = _default_snapshot(home_abbrev)
        home_snap["team"] = home_abbrev

        if not away_snap:
            away_snap = _default_snapshot(away_abbrev)
        away_snap["team"] = away_abbrev

        h2h = await client.get_head_to_head_lastN(home_abbrev, away_abbrev, n=5)

        hs, as_, diff, p_home, p_away, ptg, breakdown = score_matchup(
            home_snap,
            away_snap,
            h2h,
        )

        matchups.append(
            MatchupResult(
                gameId=str(g["gameId"]),
                date=today_str,
                homeTeam=home_abbrev,
                awayTeam=away_abbrev,
                score=MatchupScore(home=hs, away=as_, diff=diff),
                probability=MatchupProb(home=round(p_home, 4), away=round(p_away, 4)),
                projectedTotalGoals=round(ptg, 2),
                breakdown=breakdown,
            )
        )

    return TodayResponse(date=today_str, matchups=matchups)
