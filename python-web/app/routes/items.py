"""
Items routes — example CRUD endpoints backed by an in-memory store.
Swap the `db` dict for a real database (SQLAlchemy, SQLModel, etc.) when ready.
"""

from typing import Dict, List
from fastapi import APIRouter, HTTPException, status

from app.models.item import Item, ItemCreate, ItemUpdate

router = APIRouter()

# --- In-memory store (replace with a real DB) ---
_db: Dict[int, Item] = {
    1: Item(id=1, name="Widget", description="A classic widget", price=9.99),
    2: Item(id=2, name="Gadget", description="A modern gadget", price=24.99),
}
_next_id = 3


@router.get("/", response_model=List[Item])
def list_items():
    """Return all items."""
    return list(_db.values())


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: int):
    """Return a single item by ID."""
    item = _db.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.post("/", response_model=Item, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate):
    """Create a new item."""
    global _next_id
    item = Item(id=_next_id, **payload.model_dump())
    _db[_next_id] = item
    _next_id += 1
    return item


@router.patch("/{item_id}", response_model=Item)
def update_item(item_id: int, payload: ItemUpdate):
    """Partially update an existing item."""
    item = _db.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    updated = item.model_copy(update=payload.model_dump(exclude_unset=True))
    _db[item_id] = updated
    return updated


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int):
    """Delete an item by ID."""
    if item_id not in _db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    del _db[item_id]
