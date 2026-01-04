from fastapi import APIRouter, HTTPException
from datetime import date as dt_date

from app.services.nhl_client import NHLClient
from app.services.odds_service import build_today_odds
from app.models import TodayResponse

router = APIRouter()

@router.get("/today", response_model=TodayResponse)
async def today():
    client = NHLClient()
    today_str = dt_date.today().isoformat()

    games = await client.get_schedule_today()
    if games is None:
        raise HTTPException(status_code=502, detail="Failed to fetch NHL schedule")

    resp = await build_today_odds(today_str, games, client)
    return resp
