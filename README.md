# Telegram Drive

**Your Telegram. Your Drive.**

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/YOUR_GITHUB_USERNAME/telegram-drive)

> Replace `YOUR_GITHUB_USERNAME/telegram-drive` above (and inside `app.json`'s
> `repository` field) with your actual GitHub repo URL once you've pushed the
> code — see [§12](#12-push-to-github) below. The button reads `app.json` in
> your repo to configure the Heroku app automatically (SECRET_KEY is
> generated for you; add a Postgres add-on is done for you too).

A self-hosted, Google-Drive-style file manager that uses *your own* Telegram
account (via a private channel or supergroup) as unlimited-feeling storage.
Backend: FastAPI + Telethon + SQLAlchemy. Frontend: plain HTML/CSS/JS
(no React, no Node build step).

---

## 1. How it works

- You connect your own Telegram account (phone + OTP, or an existing
  Telethon StringSession).
- The app creates a private Telegram channel or supergroup on your behalf
  ("storage location").
- When you upload a file on the website, the server streams it to Telegram
  through your account, then stores only *metadata* (filename, size,
  Telegram message ID, folder) in a local database.
- Downloads work in reverse: the server fetches the file from Telegram and
  streams it back to your browser. Files are never permanently kept on the
  web server's disk — only briefly, during transfer.
- Folders ("My Drive", "Photos", etc.) are a **website-only** concept stored
  in the database. They are not Telegram folders/topics.

## 2. Requirements

- Python 3.11+
- A Telegram **API ID** and **API Hash** from <https://my.telegram.org>
  (free, takes 2 minutes — log in with the phone number you'll connect)
- Any of: local machine, a Python-capable cPanel host (Passenger WSGI/ASGI),
  or a Heroku-style platform

## 3. Local setup (Windows / Linux / macOS)

```bash
git clone <this project>  # or unzip it
cd telegram-drive
python -m venv venv

# Linux/macOS
source venv/bin/activate
# Windows
venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env: at minimum set SECRET_KEY (see the generator command in the file)

python run.py
```

Visit `http://localhost:8000`, create a website account (this is separate
from your Telegram account), then go to **Settings → Connect Telegram**.

## 4. First-time walkthrough

1. **Register** a website account (username/password — this just protects
   your dashboard; it is unrelated to your Telegram login).
2. **Connect Telegram**: enter API ID, API Hash, and phone number → enter
   the OTP Telegram sends you → enter your Two-Step Verification password
   if you have one enabled. (Advanced users can instead paste an existing
   Telethon StringSession.)
3. **Create a storage location**: Settings → "Create Telegram Storage"
   (private channel) or "Create Storage Group" (private supergroup). The
   first one you create becomes the default upload destination.
4. Go to **My Drive**, create folders, and start uploading. Drag-and-drop
   works on desktop; use the Upload button on mobile.

## 5. Security notes

- API Hash and the Telethon StringSession are encrypted at rest (Fernet,
  keyed from `SECRET_KEY`) before being written to the database. They are
  never sent to the browser, logged, or included in error messages.
- Website passwords are hashed with bcrypt.
- CSRF tokens protect every state-changing form/POST.
- Login attempts (website login and Telegram OTP requests) are rate-limited
  per IP+identifier.
- `sessions/` and `.env` are meant to stay out of version control — see
  `.gitignore`-worthy entries below if you set up git.
- This is a single-user-per-account app: each website user connects and
  manages their *own* Telegram account. There is no admin access to other
  users' Telegram data.

## 6. Architecture / scaling notes

- Telegram operations connect-operate-disconnect per request rather than
  keeping a persistent client per user in the background. This keeps the
  app compatible with restrictive shared hosting (no long-running worker
  required for normal browsing/upload/download).
- The **login flow** (send code → submit code → submit 2FA password) does
  need to reuse the same in-progress Telethon client across a couple of
  requests. That in-progress client is currently held in an in-memory
  dict inside the app process. This means:
  - Run with a **single worker** (`Procfile` already does `-w 1`) unless
    you add a shared/sticky-session mechanism, or
  - It's fine to scale everything else (uploads/downloads/browsing) beyond
    one worker; only the few-second login handshake needs process affinity.
- For heavier concurrent upload/download workloads, consider moving the
  Telegram calls into a background task queue (e.g. Celery/RQ) — the
  `telegram_service.py` module is written so its functions can be called
  from a worker process just as easily as from a request handler.

## 7. Deployment: Python-compatible cPanel

Most shared cPanel hosts that advertise "Python App" support (via
`Setup Python App` in cPanel, backed by Phusion Passenger) can run this.
**Ordinary PHP-only cPanel cannot run this app** — you need the Python
application feature specifically.

1. In cPanel → **Setup Python App**, create an app:
   - Python version: 3.11 (or newest available)
   - Application root: e.g. `telegram-drive`
   - Application URL: your domain/subdomain
   - Application startup file: `passenger_wsgi.py` (create this — see below)
   - Application Entry point: `application`
2. Upload the project files into the application root (via File Manager,
   Git, or FTP), excluding `venv/`.
3. Create `passenger_wsgi.py` in the project root:

   ```python
   import sys, os
   sys.path.insert(0, os.path.dirname(__file__))
   from asgiref.wsgi import WsgiToAsgi  # not needed — Passenger Python apps are WSGI
   # Most cPanel Python App setups run Passenger's WSGI mode. Since this app is
   # ASGI (FastAPI), the simplest reliable path on cPanel is to run Uvicorn as
   # its own process (step 4) and reverse-proxy to it, OR use a host whose
   # Python App feature explicitly supports ASGI/Passenger 6+ (asgi_app).
   ```

   If your cPanel's Passenger version supports ASGI directly (Passenger 6+,
   check with your host), instead set the entry point to `app.main:app` and
   skip the shim file entirely — this is the simpler path.

4. If your host does **not** support ASGI passthrough, run Uvicorn as a
   background process instead and reverse-proxy `/` to it:
   - Via the cPanel Python App's "Run Pip Install"/terminal, or SSH:
     ```bash
     source /home/<user>/virtualenv/telegram-drive/3.11/bin/activate
     cd ~/telegram-drive
     pip install -r requirements.txt
     nohup gunicorn app.main:app -k uvicorn.workers.UvicornWorker \
       -w 1 --bind 127.0.0.1:8001 > app.log 2>&1 &
     ```
   - Then add a proxy rule (via `.htaccess` + `mod_proxy`, or your host's
     "Application Manager" reverse proxy option) forwarding your domain to
     `127.0.0.1:8001`. Ask your host's support for their specific reverse
     proxy steps if `mod_proxy` isn't enabled by default.
5. Set environment variables in the cPanel Python App's "Environment
   Variables" section (same keys as `.env.example`).
6. Make sure `sessions/` and your SQLite file's directory are writable by
   the app user.
7. Use a process manager or cPanel's built-in restart to keep the Uvicorn
   process alive across restarts (cron `@reboot` entry is a common fallback
   on shared hosts).

## 8. Deployment: Heroku-compatible platforms

**Easiest path:** click the **Deploy to Heroku** button at the top of this
README once it's pointed at your GitHub repo (see §13). Heroku reads
`app.json`, provisions a Postgres add-on, generates `SECRET_KEY` for you,
and prompts you for the optional Telegram API ID/Hash.

**Manual path**, if you'd rather use the CLI:

```bash
heroku create your-app-name
heroku config:set SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
heroku config:set ENV=production
# Optional: heroku config:set TELEGRAM_API_ID=... TELEGRAM_API_HASH=...

# For Postgres instead of SQLite (recommended on Heroku, whose filesystem is ephemeral):
heroku addons:create heroku-postgresql:mini
# DATABASE_URL is set automatically; SQLAlchemy will use it as-is.

git push heroku main
```

The included `Procfile` already defines the `web` process
(`gunicorn ... -k uvicorn.workers.UvicornWorker -w 1`).

**Important:** on Heroku (and similar platforms with ephemeral filesystems),
do **not** use SQLite — the database file will be wiped on every dyno
restart/deploy. Use the Postgres add-on as shown above.

## 9. Environment variables

See `.env.example` for the full list. At minimum:

| Variable | Required | Notes |
|---|---|---|
| `SECRET_KEY` | Yes | Long random string; also used to derive the encryption key for stored Telegram credentials |
| `DATABASE_URL` | No | Defaults to local SQLite; use Postgres in production |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | No | Pre-fills the setup form; users can still enter their own |
| `MAX_UPLOAD_SIZE_MB` | No | Default 2000 |
| `TEMP_UPLOAD_DIR` | No | Scratch space for in-flight transfers, cleaned automatically |

## 10. Project structure

```
telegram-drive/
├── app/
│   ├── main.py              # FastAPI app, routing, dashboard/trash pages
│   ├── config.py            # Env-based settings
│   ├── database.py          # SQLAlchemy engine/session
│   ├── models.py            # User, TelegramAccount, StorageLocation, Folder, FileRecord
│   ├── telegram_service.py  # All Telethon calls (login, storage, upload/download)
│   ├── auth.py               # Website auth (sessions, CSRF, password hashing)
│   ├── security.py          # Hashing, encryption, CSRF, rate limiting
│   ├── main_templates.py    # Shared Jinja2Templates instance
│   ├── routes/
│   │   ├── auth.py          # /register /login /logout
│   │   ├── telegram.py      # /setup, OTP verification, disconnect
│   │   ├── storage.py       # /settings, storage create/rename/delete
│   │   ├── folders.py       # /api/folders/*
│   │   └── files.py         # /api/files/*, /files/upload, /files/download/{id},
│   │                        # /files/thumbnail/{id}, share-link create/revoke,
│   │                        # and the public /s/{token} shared-download route
│   ├── templates/           # Server-rendered HTML (Jinja2)
│   └── static/              # CSS + vanilla JS
├── sessions/                 # (unused placeholder — sessions live encrypted in the DB)
├── app.json                  # Heroku one-click deploy manifest
├── .env.example
├── requirements.txt
├── Procfile
├── run.py
└── README.md
```

## 11. Known limitations (MVP scope)

- Single-process login handshake (see §6) — fine for typical personal use.
- Image thumbnails are generated locally at upload time; video thumbnails
  are fetched from Telegram's server-generated preview when one is
  available on the message right after sending (best-effort — if Telegram
  hasn't finished processing yet, the file falls back to a plain icon,
  which is honest rather than showing something fake).
- Folder nesting has no depth limit at the data-model level, and the
  dashboard lets you drill into subfolders (via folder cards + breadcrumb)
  and pick any nested folder by its indented path in the "Move" dialog.

## 12. Sharing files with a public link

Each file's menu has **Share / Copy Link**, which creates a random,
unguessable link (`/s/<token>`) that lets anyone with the link download
that one file — no website account required. You choose an expiry (1 day,
7 days, 30 days, or never) when you generate it.

Notes:

- The link never exposes your Telegram API credentials or session — it only
  maps to a database row that your server uses to fetch the file from
  Telegram on the requester's behalf.
- Links can be revoked at any time (`POST /api/files/share/revoke`); an
  expired or revoked link returns a plain "no longer available" response.
- This exists because Telegram messages inside a *private* channel/group
  have no public URL of their own — making the channel itself public
  wasn't a requirement, so a signed proxy-download link is the safer
  equivalent.

## 13. Push to GitHub

```bash
cd telegram-drive
git init
git add .
git commit -m "Initial commit: Telegram Drive"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/telegram-drive.git
git push -u origin main
```

`.gitignore` already excludes `.env`, `venv/`, `*.db`, and temp upload
folders, so secrets and local artifacts won't be committed. After pushing:

1. Update the Heroku button URL at the top of this README and the
   `repository` field in `app.json` to your real repo URL.
2. Commit that change too (`git commit -am "Update repo URL"` then
   `git push`) so the Deploy button works for anyone who visits your repo.
