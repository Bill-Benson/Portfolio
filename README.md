# Bill Benson — Portfolio

Personal portfolio website built with Python and Flask, deployed on Render.

## Stack
- **Backend:** Python, Flask
- **Frontend:** HTML5, CSS3, jQuery
- **Security:** CSRF protection (Flask-WTF), rate limiting (Flask-Limiter)
- **Contact form:** SMTP email via Gmail, submissions logged to CSV

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
