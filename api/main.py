import os
from pathlib import Path

from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes_chat import router as chat_router
from api.routes_leads import router as leads_router

project_root = Path(__file__).resolve().parents[1]
load_dotenv(project_root / ".env")
load_dotenv(project_root / "api.env", override=True)

app = FastAPI()

allow_origins = os.environ.get("CORS_ALLOW_ORIGINS", "")
origins = [o.strip() for o in allow_origins.split(",") if o.strip()] or ["*"]
allow_credentials = "*" not in origins

app.add_middleware(
  CORSMiddleware,
  allow_origins=origins,
  allow_credentials=allow_credentials,
  allow_methods=["*"],
  allow_headers=["*"],
)

app.include_router(leads_router)
app.include_router(chat_router)
