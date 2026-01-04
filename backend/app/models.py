from pydantic import BaseModel
from typing import List, Optional


class EdgeBreakdown(BaseModel):
    factor: str
    team: Optional[str]
    points: int
    reason: str


class MatchupScore(BaseModel):
    home: int
    away: int
    diff: int  # home - away


class MatchupProb(BaseModel):
    home: float
    away: float


class MatchupResult(BaseModel):
    gameId: str
    date: str
    homeTeam: str
    awayTeam: str
    score: MatchupScore
    probability: MatchupProb
    projectedTotalGoals: Optional[float] = None
    breakdown: List[EdgeBreakdown]


class TodayResponse(BaseModel):
    date: str
    matchups: List[MatchupResult]
