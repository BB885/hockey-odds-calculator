from pydantic import BaseModel

class Settings(BaseModel):
    # NHL API base. Keep configurable in case you change sources later.
    nhl_api_base: str = "https://api-web.nhle.com/v1"

    # Logistic temperature: smaller => more extreme probabilities.
    logistic_temperature: float = 4.0

    # Allow very confident predictions. Cap can still prevent absurd extremes.
    max_abs_diff: int = 15

settings = Settings()
