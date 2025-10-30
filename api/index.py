import os
import sys

# Ensure sqlite3 is available in serverless (Vercel) environments
try:  # pragma: no cover
    import sqlite3  # noqa: F401
except Exception:  # pragma: no cover
    try:
        import pysqlite3 as sqlite3  # type: ignore
        sys.modules["sqlite3"] = sqlite3
    except Exception as e:
        # If even the shim fails, raise a clearer error
        raise RuntimeError(f"SQLite support not available: {e}")

# Create the Flask WSGI app for Vercel serverless
try:
    from app import create_app
except Exception as e:  # pragma: no cover
    # Helpful message in case import fails on Vercel
    raise RuntimeError(f"Failed to import Flask app: {e}")

app = create_app()


@app.get("/healthz")
def healthz():
    try:
        # verify DB works
        from app import db  # lazy import to avoid cycles at import time
        with app.app_context():
            db.session.execute("SELECT 1")
        return "ok", 200
    except Exception as e:
        # surface a concise error for debugging deploys
        return f"err:{type(e).__name__}", 500
