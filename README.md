# bot01

Simple Flask-based webhook that sends form data to Telegram.

## Components

- **Web server:** Flask app served by Gunicorn and Nginx (unchanged).
- **Scheduler:** Standalone APScheduler process that sends a daily Telegram message. This runs independently from the web server.

## Environment variables

Set these in your deployment environment (e.g., systemd `EnvironmentFile` or shell):

- `SPORTSDATAIO_API_KEY` – Telegram bot token (use this instead of `TELEGRAM_BOT_TOKEN`)
- `TELEGRAM_CHAT_ID` – Target chat/channel id
- `SECRET_KEY` – Flask session secret (web server only)
- Optional: `SCHEDULER_TEST_MODE=true` to schedule a one-off test run 30 seconds after startup

Local development can still use a `.env` file, but production secrets should only be set via environment variables.

## Web server (unchanged)

Run locally:

```
python main.py
```

Production with Gunicorn:

```
gunicorn -w 1 -b 127.0.0.1:5000 main:app
```

A sample `bot01.service` unit is provided for running under systemd.

## Standalone scheduler

The scheduler lives in `scheduler/daily_telegram_sender.py` and uses `common/telegram_client.py` to send messages. It does **not** import the Flask app and runs in its own process so it is unaffected by Gunicorn worker counts or reloads.

### Running manually

- Run the scheduler normally (blocks and waits for the next 08:20 Asia/Seoul slot):

```
python scheduler/daily_telegram_sender.py
```

- Send a single message immediately and exit (no scheduler started):

```
python scheduler/daily_telegram_sender.py --run-once
```

- One-off scheduling for quick validation: start with `SCHEDULER_TEST_MODE=true` to register a `DateTrigger` 30 seconds in the future.

### systemd unit example

Create `/etc/systemd/system/bot01_scheduler.service` with the following content (adjust user/paths for your host):

```
[Unit]
Description=bot01 daily Telegram scheduler
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/bot01
Environment="PATH=/home/ubuntu/venv/bin"
EnvironmentFile=/home/ubuntu/bot01/.env
ExecStart=/home/ubuntu/venv/bin/python /home/ubuntu/bot01/scheduler/daily_telegram_sender.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Reload and start:

```
sudo systemctl daemon-reload
sudo systemctl enable bot01_scheduler
sudo systemctl start bot01_scheduler
journalctl -u bot01_scheduler.service -f
```

### Logging

Scheduler logs are written both to stdout/stderr (visible via `journalctl`) and to `logs/scheduler.log`.

## Files

- `common/telegram_client.py` – Reusable Telegram API client using environment variables only.
- `scheduler/daily_telegram_sender.py` – Standalone APScheduler process with CLI/testing aids.
- `bot01_scheduler.service` – Example systemd unit for the scheduler.
- `bot01.service` – Example systemd unit for the Flask/Gunicorn web server.
- `main.py` – Flask application (no embedded schedulers).
