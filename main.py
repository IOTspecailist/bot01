import os
import time
import atexit
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Iterable, Optional
from threading import Lock

from flask import (
    Flask,
    render_template,
    request,
    abort,
    session,
    current_app,
)
import requests
import pyfiglet
from dotenv import load_dotenv
from markupsafe import Markup, escape
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Attempt to load environment variables from a .env file if present.
if not load_dotenv():
    print("[INFO] .env file not found; falling back to system environment or secrets.py")

# Optional secrets.py allows tokens to be provided without a .env file
try:  # pragma: no cover - optional secret file
    from secrets import BOT_TOKEN as SECRET_BOT_TOKEN, CHAT_ID as SECRET_CHAT_ID
    print("[INFO] Credentials loaded from secrets.py")
except Exception:
    SECRET_BOT_TOKEN = None
    SECRET_CHAT_ID = None
    print("[INFO] secrets.py not found; relying on environment variables")

BOT_TOKEN = os.getenv("BOT_TOKEN") or SECRET_BOT_TOKEN
CHAT_ID = os.getenv("CHAT_ID") or SECRET_CHAT_ID
if not BOT_TOKEN or not CHAT_ID:
    print("[INFO] BOT_TOKEN or CHAT_ID not configured; Telegram sending disabled")


MARKET_LINKS: Iterable[tuple[str, str]] = (
    ("경제달력", "https://kr.investing.com/economic-calendar/"),
    ("중앙은행 기준금리", "https://kr.investing.com/central-banks/"),
)

SCHEDULE_TIMEZONE = ZoneInfo("Asia/Seoul")


MIN_SCHEDULE_DISPATCH_INTERVAL = timedelta(minutes=1)
LAST_SCHEDULED_DISPATCH: Optional[datetime] = None
LAST_SCHEDULED_DISPATCH_DATE: Optional[date] = None
SCHEDULE_DISPATCH_LOCK = Lock()


def _set_last_scheduled_dispatch(timestamp: datetime) -> None:
    global LAST_SCHEDULED_DISPATCH, LAST_SCHEDULED_DISPATCH_DATE
    LAST_SCHEDULED_DISPATCH = timestamp
    LAST_SCHEDULED_DISPATCH_DATE = timestamp.date()


def format_links_message() -> str:
    return "\n".join(f"{name}: {url}" for name, url in MARKET_LINKS)


def format_for_display(text: str) -> Markup:
    safe_text = escape(text)
    return Markup("<br>".join(str(safe_text).splitlines()))


def send_telegram_message(bot_token: Optional[str], chat_id: Optional[str], message: str) -> bool:
    if not bot_token or not chat_id:
        print("[WARN] Telegram credentials missing; message not sent")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    try:
        response = requests.post(url, data=data, timeout=5)
        print(f"[INFO] Telegram response: {response.status_code} {response.text}")
        return response.ok
    except Exception as exc:  # pragma: no cover - network related
        print("[ERROR] Telegram send failed:", str(exc))
        return False


def dispatch_market_links(
    prefix: Optional[str] = None,
    *,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> str:
    message = format_links_message()
    if prefix:
        message = f"{prefix}\n{message}"

    send_telegram_message(bot_token or BOT_TOKEN, chat_id or CHAT_ID, message)
    return message


def scheduled_links_job() -> None:
    now = datetime.now(SCHEDULE_TIMEZONE)
    with SCHEDULE_DISPATCH_LOCK:
        if (
            LAST_SCHEDULED_DISPATCH_DATE is not None
            and LAST_SCHEDULED_DISPATCH_DATE == now.date()
        ):
            print(
                "[INFO] Scheduled dispatch already sent for today; "
                f"last at {LAST_SCHEDULED_DISPATCH.isoformat()}, skipping"
            )
            return

        if (
            LAST_SCHEDULED_DISPATCH is not None
            and now - LAST_SCHEDULED_DISPATCH < MIN_SCHEDULE_DISPATCH_INTERVAL
        ):
            print(
                "[INFO] Duplicate scheduled dispatch detected; "
                f"last at {LAST_SCHEDULED_DISPATCH.isoformat()}, skipping"
            )
            return

        dispatch_market_links()
        _set_last_scheduled_dispatch(now)

    print(f"[INFO] Scheduled economic links dispatched at {now.isoformat()}")


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change_me')
    app.config['BOT_TOKEN'] = BOT_TOKEN
    app.config['CHAT_ID'] = CHAT_ID
    return app


app = create_app()


scheduler = BackgroundScheduler(timezone=SCHEDULE_TIMEZONE)
scheduler.add_job(
    scheduled_links_job,
    CronTrigger(hour=8, minute=20, timezone=SCHEDULE_TIMEZONE),
    id="daily_market_links",
    replace_existing=True,
)

SCHEDULER_STARTED = False


def start_scheduler() -> None:
    global SCHEDULER_STARTED
    if scheduler.running:
        return
    scheduler.start()
    SCHEDULER_STARTED = True
    print("[INFO] Daily market links scheduler started")


start_scheduler()


def shutdown_scheduler() -> None:
    if getattr(scheduler, "running", False):
        scheduler.shutdown(wait=False)
        print("[INFO] Scheduler shut down")


atexit.register(shutdown_scheduler)

# Simple in-memory rate limiter
RATE_LIMIT = {}
BAN_LIST = {}
REQUESTS_PER_MINUTE = 5
BAN_DURATION = 600  # seconds

def check_rate_limit(ip: str) -> None:
    now = time.time()
    if BAN_LIST.get(ip, 0) > now:
        abort(429)

    history = [t for t in RATE_LIMIT.get(ip, []) if now - t < 60]
    history.append(now)
    RATE_LIMIT[ip] = history

    if len(history) > REQUESTS_PER_MINUTE:
        BAN_LIST[ip] = now + BAN_DURATION
        abort(429)

@app.route('/')
def index() -> str:
    token = os.urandom(16).hex()
    session['csrf_token'] = token
    return render_template('index.html', csrf_token=token)


@app.route('/ascii')
def ascii_art() -> str:
    art = pyfiglet.figlet_format('Hello, ASCII!')
    return render_template('ascii.html', art=art)


@app.route('/market-overview')
def market_overview() -> str:
    return render_template('market_overview.html')

@app.route('/send', methods=['POST'])
def send() -> str:
    ip = request.remote_addr or 'unknown'
    check_rate_limit(ip)

    token = request.form.get('csrf_token', '')
    if not token or token != session.get('csrf_token'):
        abort(400)

    raw_text = request.form.get('text', '')
    display_text = format_for_display(raw_text)
    message = f"IP: {ip}\nMessage: {raw_text}"
    bot_token = current_app.config['BOT_TOKEN']
    chat_id = current_app.config['CHAT_ID']
    send_telegram_message(bot_token, chat_id, message)
    return render_template('result.html', text=display_text)


@app.route('/send-links', methods=['POST'])
def send_links() -> str:
    ip = request.remote_addr or 'unknown'
    check_rate_limit(ip)

    token = request.form.get('csrf_token', '')
    if not token or token != session.get('csrf_token'):
        abort(400)

    bot_token = current_app.config['BOT_TOKEN']
    chat_id = current_app.config['CHAT_ID']
    message = dispatch_market_links(prefix=f"[Manual Trigger] IP: {ip}", bot_token=bot_token, chat_id=chat_id)
    display_text = format_for_display(format_links_message())
    return render_template('result.html', text=display_text)

if __name__ == '__main__':
    # Default port is 5000. Change to 80 for production if needed.
    app.run(host='0.0.0.0', port=5000)
