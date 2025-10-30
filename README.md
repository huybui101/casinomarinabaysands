# Casino/Lottery Web (Flask)

This project provides a modern multi-language Flask web app with:
- User register/login, personal page
- Home/Casino/Lottery/Lobby sections and mobile-friendly bottom nav
- Betting pages with 10-minute VN-time countdown and round IDs
- Deposit link to Telegram, withdraw form with min $100 and withdraw PIN
- Bank account linking with a list of Vietnamese banks
- Admin backend at `/admin` to edit site name/color/Telegram, game odds (1.98/2.1), and manage images (upload/delete, optional background removal if `rembg` installed)

## Quick start (Windows PowerShell)

```powershell
# 1) Ensure Python is installed (3.10+)
# 2) Install dependencies
"C:/Users/Kinjina/Desktop/WEB 2.1/.venv/Scripts/python.exe" -m pip install -r requirements.txt

# 3) Run the app
"C:/Users/Kinjina/Desktop/WEB 2.1/.venv/Scripts/python.exe" run.py
```

- User site: http://127.0.0.1:5000/
- Admin site: http://127.0.0.1:5000/admin (requires `is_admin=True` on your user; set manually in DB for now)

## Deploy to Vercel (demo only)
Vercel can run this Flask app via a Python Serverless Function defined in `api/index.py` with routing configured in `vercel.json`.

Important: Vercel’s filesystem is read‑only and ephemeral. SQLite will not persist. For a real deployment use a managed DB (Neon/Supabase/MySQL) or a platform like Render/Railway/Fly.io. For a quick demo, set the DB path to `/tmp`:

1) Push your code to GitHub (already set up).
2) On Vercel Project Settings → Environment Variables, add:
	- `DATABASE_URL` = `sqlite:////tmp/app.db`
	- `SECRET_KEY` = a long random string
3) Trigger a deploy (or push any commit). Your app will be available at the Vercel domain.

Static assets under `app/static/` are served directly by Vercel. All other routes are handled by the Flask app.

## Deploy to Render (recommended for stable runtime)
This repo includes a `render.yaml` blueprint and `Procfile` to run the app reliably with persistent storage.

Steps:
1) Push this repo to GitHub (done).
2) Go to https://dashboard.render.com → New → Blueprint → connect this repo.
3) Accept defaults; Render will create a Web Service with a persistent disk mounted at `/opt/render/project/src/data`.
4) The app uses:
	- `DATABASE_URL=sqlite:////opt/render/project/src/data/app.db` (persists across deploys)
	- `UPLOAD_DIR=/opt/render/project/src/data/uploads` (user uploads persist)
	- `SECRET_KEY` is auto-generated.
5) First deploy takes a few minutes. After deploy:
	- User site: your Render URL
	- Admin: your Render URL + `/admin`

## Notes
- Default language is Vietnamese. You can extend translations later via Flask-Babel.
 - Image background removal uses `rembg` if installed; otherwise uploads remain unchanged.
 - Game settlement logic is not implemented; bets are stored as PENDING for demo.