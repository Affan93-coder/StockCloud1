"""
Item models — Pydantic schemas for request/response validation.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, example="Widget")
    description: Optional[str] = Field(None, max_length=500, example="A useful widget")
    price: float = Field(..., gt=0, example=9.99)


class ItemCreate(ItemBase):
    """Schema for creating a new item."""
    pass


class ItemUpdate(BaseModel):
    """Schema for partial updates — all fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    price: Optional[float] = Field(None, gt=0)


class Item(ItemBase):
    """Full item schema returned by the API."""
    id: int

    model_config = {"from_attributes": True}
