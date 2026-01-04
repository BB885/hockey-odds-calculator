import httpx
import asyncio
from datetime import date as dt_date
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings


def _get_nested(d: Dict[str, Any], path: List[str], default=None):
    cur: Any = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def _points_pct(w: int, l: int, otl: int) -> Optional[float]:
    games = w + l + otl
    if games <= 0:
        return None
    pts = 2 * w + 1 * otl
    max_pts = 2 * games
    return pts / max_pts if max_pts else None


def _parse_streak(team_row: Dict[str, Any]) -> Tuple[Optional[str], int]:
    """
    Best-effort, because NHL API fields vary:
    - Sometimes: streakCode = "W", streakCount = 3
    - Sometimes: streak = "W3"
    """
    code = team_row.get("streakCode")
    count = team_row.get("streakCount")

    if isinstance(code, str) and isinstance(count, int):
        return code.upper(), count

    streak = team_row.get("streak")
    if isinstance(streak, str) and len(streak) >= 2:
        c = streak[0].upper()
        try:
            n = int(streak[1:])
            return c, n
        except Exception:
            pass

    return None, 0


class NHLClient:
    """
    Uses NHL public endpoints:
    - Standings: https://api-web.nhle.com/v1/standings/<YYYY-MM-DD>
    - Schedule:  https://api-web.nhle.com/v1/schedule/<YYYY-MM-DD>
    - Goalie leaders: https://api-web.nhle.com/v1/goalie-stats-leaders/current?categories=savePctg&limit=10
    """

    def __init__(self):
        self.base = settings.nhl_api_base.rstrip("/")
        self._timeout = 20.0

        # tiny per-process cache (so one /today call doesn’t re-fetch standings 20 times)
        self._standings_cache_date: Optional[str] = None
        self._standings_cache: Optional[List[Dict[str, Any]]] = None

        # computed goal ranks cache
        self._goal_rank_cache: Optional[Dict[str, Dict[str, int]]] = None

        # Team goalie factor cache (by team abbrev)
        self._team_goalie_factor_cache_date: Optional[str] = None
        self._team_goalie_factor_cache: Optional[Dict[str, Dict[str, Any]]] = None



    async def _get_json(self, url: str):
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                r = await client.get(
                    url,
                    headers={
                        "User-Agent": "hockey-odds-calculator/1.0",
                        "Accept": "application/json",
                    },
                )
                if r.status_code != 200:
                    # keep it quiet in normal operation; return None gracefully
                    return None
                return r.json()
        except Exception:
            return None

    async def get_schedule_today(self) -> Optional[List[Dict[str, Any]]]:
        today = dt_date.today().isoformat()
        url = f"{self.base}/schedule/{today}"
        data = await self._get_json(url)
        if not data:
            return None

        games_out: List[Dict[str, Any]] = []

        # NHL returns a "gameWeek" list; we ONLY want the day that matches today.
        week = data.get("gameWeek")
        if isinstance(week, list):
            for day in week:
                if not isinstance(day, dict):
                    continue

                day_date = day.get("date")
                if isinstance(day_date, str) and day_date != today:
                    continue  # <-- this is the key filter

                games = day.get("games")
                if not isinstance(games, list):
                    continue

                for g in games:
                    home = g.get("homeTeam", {}) or {}
                    away = g.get("awayTeam", {}) or {}
                    game_id = str(g.get("id") or g.get("gameId") or "")

                    games_out.append({
                        "gameId": game_id,
                        "date": today,
                        "homeAbbrev": home.get("abbrev") or home.get("triCode") or home.get("abbreviation"),
                        "awayAbbrev": away.get("abbrev") or away.get("triCode") or away.get("abbreviation"),
                    })

        # Fallback if gameWeek isn't present: sometimes "games" is directly today
        if not games_out:
            games_direct = data.get("games")
            if isinstance(games_direct, list):
                for g in games_direct:
                    home = g.get("homeTeam", {}) or {}
                    away = g.get("awayTeam", {}) or {}
                    game_id = str(g.get("id") or g.get("gameId") or "")
                    games_out.append({
                        "gameId": game_id,
                        "date": today,
                        "homeAbbrev": home.get("abbrev") or home.get("triCode") or home.get("abbreviation"),
                        "awayAbbrev": away.get("abbrev") or away.get("triCode") or away.get("abbreviation"),
                    })

        games_out = [x for x in games_out if x["gameId"] and x["homeAbbrev"] and x["awayAbbrev"]]
        return games_out


    async def _get_standings(self, date_str: str) -> Optional[List[Dict[str, Any]]]:
        if self._standings_cache_date == date_str and self._standings_cache is not None:
            return self._standings_cache

        url = f"{self.base}/standings/{date_str}"
        data = await self._get_json(url)
        if not data:
            return None

        standings = data.get("standings")
        if not isinstance(standings, list):
            return None

        self._standings_cache_date = date_str
        self._standings_cache = standings

        # standings changed → invalidate goal ranks cache
        self._goal_rank_cache = None

        return standings

    def _extract_abbrev(self, row: Dict[str, Any]) -> Optional[str]:
        v = row.get("teamAbbrev")
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            d = v.get("default")
            if isinstance(d, str):
                return d
        tri = row.get("teamTriCode") or row.get("triCode")
        return tri if isinstance(tri, str) else None

    def _compute_goal_ranks(self, standings: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
        rows: List[Tuple[str, float, float]] = []

        for r in standings:
            ab = self._extract_abbrev(r)
            if not ab:
                continue
            gf = r.get("goalFor")
            ga = r.get("goalAgainst")
            if isinstance(gf, (int, float)) and isinstance(ga, (int, float)):
                rows.append((ab.upper(), float(gf), float(ga)))

        if not rows:
            return {}

        gf_sorted = sorted(rows, key=lambda x: x[1], reverse=True)
        gf_rank = {ab: i + 1 for i, (ab, _, __) in enumerate(gf_sorted)}

        ga_sorted = sorted(rows, key=lambda x: x[2])
        ga_rank = {ab: i + 1 for i, (ab, _, __) in enumerate(ga_sorted)}

        out: Dict[str, Dict[str, int]] = {}
        for ab, _, __ in rows:
            out[ab] = {
                "goals_for_rank": gf_rank.get(ab, 0),
                "goals_against_rank": ga_rank.get(ab, 0),
            }
        return out

    async def get_team_snapshot(self, team_abbrev: str, game_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Build the full dict needed for scoring from standings.
        Goalie (v1): use DailyFaceoff projected/confirmed starter status, then match to NHL top10 SV% by name.
        """
        today = dt_date.today().isoformat()
        standings = await self._get_standings(today)

        snap: Dict[str, Any] = {
            "team": team_abbrev,
            "points_pct": None,
            "home_points_pct": None,
            "away_points_pct": None,
            "goals_for_rank": None,
            "goals_against_rank": None,
            "last10_points_pct": None,
            "streak_type": None,
            "streak_len": 0,
            "out_top50_scorers": 0,
            "out_top15_scorers": 0,


                        # goalie factor (team #1 by GP)
            "goalie_factor": 0,
            "goalie_sv_pct_used": None,
            "goalie_gp_used": 0,
            "goalie_used_split": False,

        }

        if not standings:
            return snap

        # Find team row
        team_row = None
        for r in standings:
            ab = self._extract_abbrev(r)
            if ab and ab.upper() == team_abbrev.upper():
                team_row = r
                break

        if not team_row:
            return snap

        # points pct
        p = team_row.get("pointPctg")
        if isinstance(p, (int, float)):
            snap["points_pct"] = float(p)
        else:
            w = int(team_row.get("wins") or 0)
            l = int(team_row.get("losses") or 0)
            otl = int(team_row.get("otLosses") or 0)
            snap["points_pct"] = _points_pct(w, l, otl)

        # home/away points pct
        hw = int(team_row.get("homeWins") or 0)
        hl = int(team_row.get("homeLosses") or 0)
        hotl = int(team_row.get("homeOtLosses") or 0)
        aw = int(team_row.get("roadWins") or team_row.get("awayWins") or 0)
        al = int(team_row.get("roadLosses") or team_row.get("awayLosses") or 0)
        aotl = int(team_row.get("roadOtLosses") or team_row.get("awayOtLosses") or 0)

        snap["home_points_pct"] = _points_pct(hw, hl, hotl)
        snap["away_points_pct"] = _points_pct(aw, al, aotl)

        # last 10
        l10w = int(team_row.get("l10Wins") or 0)
        l10l = int(team_row.get("l10Losses") or 0)
        l10otl = int(team_row.get("l10OtLosses") or 0)
        snap["last10_points_pct"] = _points_pct(l10w, l10l, l10otl)

        # streak
        stype, slen = _parse_streak(team_row)
        snap["streak_type"] = stype
        snap["streak_len"] = slen

        # goals ranks cached
        if self._goal_rank_cache is None:
            self._goal_rank_cache = self._compute_goal_ranks(standings)

        ranks = self._goal_rank_cache.get(team_abbrev.upper(), {})
        snap["goals_for_rank"] = ranks.get("goals_for_rank")
        snap["goals_against_rank"] = ranks.get("goals_against_rank")

                
        # -----------------------
        # Goalie factor (Team #1 by GP)
        # -----------------------
        gf = await self.get_team_goalie_factor(team_abbrev.upper())
        snap["goalie_factor"] = int(gf.get("score") or 0)
        snap["goalie_sv_pct_used"] = gf.get("sv_pct")
        snap["goalie_gp_used"] = int(gf.get("gp") or 0)
        snap["goalie_used_split"] = bool(gf.get("used_split") or False)

        return snap

    async def get_head_to_head_lastN(
        self,
        home_team: str,
        away_team: str,
        n: int = 5,
        max_seasons_back: int = 5,
    ) -> Optional[Dict[str, Any]]:
        """
        Find up to last N head-to-head games between home_team and away_team
        across seasons using club-schedule-season.
        """

        def _season_ids_back(start_season: str, count: int) -> List[str]:
            start_year = int(start_season[:4])
            return [f"{start_year - i}{start_year - i + 1}" for i in range(count)]

        base_season = getattr(settings, "nhl_season", None)
        if not isinstance(base_season, str) or len(base_season) != 8:
            base_season = self._current_season_id()

        seasons = _season_ids_back(base_season, max_seasons_back)

        home_wins = 0
        away_wins = 0
        found = 0

        for season in seasons:
            if found >= n:
                break

            url = f"{self.base}/club-schedule-season/{home_team.upper()}/{season}"
            data = await self._get_json(url)
            if not isinstance(data, dict):
                continue

            games = data.get("games")
            if not isinstance(games, list):
                continue

            # iterate most recent first
            for g in reversed(games):
                if found >= n:
                    break

                home = g.get("homeTeam")
                away = g.get("awayTeam")
                if not isinstance(home, dict) or not isinstance(away, dict):
                    continue

                h_ab = home.get("abbrev")
                a_ab = away.get("abbrev")

                # must be a matchup between these two teams
                if {h_ab, a_ab} != {home_team.upper(), away_team.upper()}:
                    continue

                h_score = home.get("score")
                a_score = away.get("score")
                if not isinstance(h_score, int) or not isinstance(a_score, int):
                    continue

                if h_score > a_score:
                    winner = h_ab
                elif a_score > h_score:
                    winner = a_ab
                else:
                    found += 1
                    continue

                if winner == home_team.upper():
                    home_wins += 1
                else:
                    away_wins += 1

                found += 1

        if found == 0:
            return None

        return {
            "home_wins": home_wins,
            "away_wins": away_wins,
            "games_found": found,
        }

    def _goalie_bucket_score(self, sv_pct: Optional[float]) -> int:
        """
        Your buckets:
        >= .920 => +2
        .910-.919 => +1
        .900-.909 => 0
        .890-.899 => -1
        < .890 => -2
        """
        if not isinstance(sv_pct, (int, float)):
            return 0

        v = float(sv_pct)
        if v >= 0.920:
            return 2
        if v >= 0.910:
            return 1
        if v >= 0.900:
            return 0
        if v >= 0.890:
            return -1
        return -2

    def _current_season_id(self) -> str:
        """
        NHL season id format: "20252026".
        If month is Jan–Jun, we're in the season that started previous year.
        If month is Jul–Dec, we're in the season that starts this year.
        """
        today = dt_date.today()
        if today.month <= 6:
            start = today.year - 1
            end = today.year
        else:
            start = today.year
            end = today.year + 1
        return f"{start}{end}"


    async def _build_team_goalie_factor_map(self) -> Dict[str, Dict[str, Any]]:
        """
        Build goalie factor per team using club-stats:
        - pick goalie with most GP
        - if top GP < 8 => score 0
        - if top2 GP diff <= 3 => average their save% (1A/1B)
        - buckets (using save percentage as a decimal):
            >= .920 => +2
            .910-.919 => +1
            .900-.909 => 0
            .890-.899 => -1
            < .890 => -2
        """
        today = dt_date.today().isoformat()
        if self._team_goalie_factor_cache_date == today and isinstance(self._team_goalie_factor_cache, dict):
            return self._team_goalie_factor_cache

        season = getattr(settings, "nhl_season", None) or self._current_season_id()
        game_type = 2  # regular season

        standings = await self._get_standings(today)
        if not standings:
            self._team_goalie_factor_cache_date = today
            self._team_goalie_factor_cache = {}
            return {}

        team_abbrevs: List[str] = []
        for r in standings:
            ab = self._extract_abbrev(r)
            if isinstance(ab, str) and ab.strip():
                team_abbrevs.append(ab.strip().upper())
        team_abbrevs = sorted(set(team_abbrevs))

        sem = asyncio.Semaphore(8)

        async def fetch_team(team: str) -> Tuple[str, Dict[str, Any]]:
            url = f"{self.base}/club-stats/{team}/{season}/{game_type}"
            async with sem:
                data = await self._get_json(url)

            if not isinstance(data, dict):
                return team, {"score": 0, "sv_pct": None, "gp": 0, "used_split": False}

            goalies = data.get("goalies")
            if not isinstance(goalies, list) or not goalies:
                return team, {"score": 0, "sv_pct": None, "gp": 0, "used_split": False}

            # Build list of (gp, sv%) using club-stats keys:
            # gamesPlayed + savePercentage
            parsed: List[Tuple[int, Optional[float]]] = []
            for g in goalies:
                if not isinstance(g, dict):
                    continue
                gp = g.get("gamesPlayed")
                sv = g.get("savePercentage")  # <-- IMPORTANT: this is the correct key
                if isinstance(gp, int):
                    parsed.append((gp, float(sv) if isinstance(sv, (int, float)) else None))

            if not parsed:
                return team, {"score": 0, "sv_pct": None, "gp": 0, "used_split": False}

            parsed.sort(key=lambda x: x[0], reverse=True)
            top_gp, top_sv = parsed[0]

            # Guardrail: not enough sample
            if top_gp < 8:
                return team, {"score": 0, "sv_pct": None, "gp": top_gp, "used_split": False}

            used_split = False
            used_sv: Optional[float] = top_sv

            # 1A/1B split: top2 GP within 3 => average SV% (only if both present)
            if len(parsed) >= 2:
                gp2, sv2 = parsed[1]
                if abs(top_gp - gp2) <= 3:
                    used_split = True
                    if isinstance(top_sv, (int, float)) and isinstance(sv2, (int, float)):
                        used_sv = (float(top_sv) + float(sv2)) / 2.0
                    else:
                        return team, {"score": 0, "sv_pct": None, "gp": top_gp, "used_split": True}

            score = self._goalie_bucket_score(used_sv)
            return team, {"score": score, "sv_pct": used_sv, "gp": top_gp, "used_split": used_split}

        results = await asyncio.gather(*(fetch_team(t) for t in team_abbrevs))
        out = {team: payload for team, payload in results}

        self._team_goalie_factor_cache_date = today
        self._team_goalie_factor_cache = out
        return out




    async def get_team_goalie_factor(self, team_abbrev: str) -> Dict[str, Any]:
        """
        Public helper: returns goalie factor dict for a team abbrev.
        """
        m = await self._build_team_goalie_factor_map()
        return m.get(team_abbrev.upper(), {"score": 0, "sv_pct": None, "gp": 0, "used_split": False})
