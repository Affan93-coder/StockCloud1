"""
Health check endpoint.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthStatus(BaseModel):
    status: str
    version: str


@router.get("/healthz", response_model=HealthStatus)
def health_check():
    """Returns service health status."""
    return {"status": "ok", "version": "0.1.0"}
