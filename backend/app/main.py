from fastapi import FastAPI
from app.routes.health import router as health_router
from app.routes.today import router as today_router
from fastapi.middleware.cors import CORSMiddleware



app = FastAPI(title="Hockey Odds API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://hockey-odds-calculator-rzdn.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health_router)
app.include_router(today_router)
