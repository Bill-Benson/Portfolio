# Bill Benson - Portfolio

Personal portfolio website built with Python and Flask, deployed on Render.

## Stack
- **Backend:** Python, Flask
- **Frontend:** HTML5, CSS3, vanilla JavaScript (no frameworks)
- **Security:** CSRF protection (Flask-WTF), rate limiting (Flask-Limiter)
- **Contact form:** SMTP email via Gmail, submissions logged to CSV
- **Production:** served with gunicorn on Render

## Features
- **Markdown blog engine:** posts live in `posts/` and are rendered with markdown2 (fenced code blocks, tables, strikethrough). The index at `/blog` sorts newest first by an ISO `date` field in each post's front matter, and `/blog/<slug>` validates the slug against `^[a-z0-9-]+$` before touching the filesystem.
- **Hardened contact form:** CSRF protection and rate limiting, with submissions emailed over Gmail SMTP and appended to a CSV log.

## Running locally

1. Clone the repo
2. Create a virtual environment and install dependencies:
   ```
   python3 -m venv venv
   venv/bin/pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your credentials:
   ```
   cp .env.example .env
   ```
4. Generate a secret key and add it to `.env`:
   ```
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
5. Run the app:
   ```
   venv/bin/python server.py
   ```

The app will be available at `http://127.0.0.1:5000`.

## Environment variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | Flask secret key for CSRF and session signing |
| `SENDER_EMAIL` | Gmail address used to send contact form emails |
| `SENDER_PASSWORD` | Gmail app password (not your account password) |
| `RECIPIENT_EMAIL` | Email address to receive contact form submissions |
