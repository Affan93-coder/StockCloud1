"""
FastAPI Python Web App Template
--------------------------------
Entry point. Run with:
    uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import items, health

app = FastAPI(
    title="My API",
    description="A FastAPI template with example CRUD endpoints.",
    version="0.1.0",
)

# Allow all origins in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router, tags=["health"])
app.include_router(items.router, prefix="/items", tags=["items"])
