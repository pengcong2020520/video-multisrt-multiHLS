# apps/api

FastAPI service implementing the frozen Spec section 7 API surface.

## Local development

```bash
cd apps/api
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Defaults:

- Database: `sqlite:///./api.sqlite3`
- Public signed URL base: `http://localhost:8000/object`
- Auth: every `/api/*` request requires `X-User-Id` or a bearer token

FastAPI publishes OpenAPI at `/openapi.json` and `/docs`.
