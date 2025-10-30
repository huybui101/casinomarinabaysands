import os

# Create the Flask WSGI app for Vercel serverless
try:
    from app import create_app
except Exception as e:  # pragma: no cover
    # Helpful message in case import fails on Vercel
    raise RuntimeError(f"Failed to import Flask app: {e}")

app = create_app()


@app.get("/healthz")
def healthz():
    return "ok", 200
