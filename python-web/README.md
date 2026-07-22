# Python Web App Template (FastAPI)

A clean FastAPI starter with example CRUD endpoints, Pydantic v2 models, and
auto-generated interactive docs.

## Quick start

```bash
cd python-web
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Interactive docs

| URL | Description |
|-----|-------------|
| `/docs` | Swagger UI — try every endpoint in the browser |
| `/redoc` | ReDoc — clean, read-only reference |
| `/openapi.json` | Raw OpenAPI schema |

## Project layout

```
python-web/
├── main.py              # App factory — middleware + router registration
├── requirements.txt
├── .env.example         # Copy to .env for local config
└── app/
    ├── models/
    │   └── item.py      # Pydantic request/response schemas
    └── routes/
        ├── health.py    # GET /healthz
        └── items.py     # CRUD  /items  (in-memory store — swap for a real DB)
```

## Swapping the in-memory store for a real database

1. Install SQLModel or SQLAlchemy + asyncpg:
   ```bash
   pip install sqlmodel asyncpg
   ```
2. Add `DATABASE_URL` to your `.env`.
3. Replace the `_db` dict in `app/routes/items.py` with SQLModel session calls.

## Adding a new resource

1. Create `app/models/thing.py` — define `ThingBase`, `ThingCreate`, `ThingUpdate`, `Thing`.
2. Create `app/routes/things.py` — define a router with your CRUD handlers.
3. Register it in `main.py`:
   ```python
   from app.routes import things
   app.include_router(things.router, prefix="/things", tags=["things"])
   ```
