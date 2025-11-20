# bot01

Simple Flask-based webhook that sends form data to Telegram.

## Setup

1. Copy `.env.example` to `.env` and fill in `BOT_TOKEN` and `CHAT_ID`.
   Alternatively, create a `secrets.py` containing `BOT_TOKEN` and `CHAT_ID`
   variables.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run the server with `python main.py` for local development.
4. For production with Gunicorn, start with a single worker to avoid duplicating the APScheduler instance:
   ```
   gunicorn -w 1 -b 127.0.0.1:5000 main:app
   ```
   A sample `bot01.service` unit is provided for running under systemd with this configuration.
