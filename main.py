import os
import time
import html
from flask import (
    Flask,
    render_template,
    request,
    abort,
    session,
    current_app,
)
import requests
from dotenv import load_dotenv

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


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change_me')
    app.config['BOT_TOKEN'] = BOT_TOKEN
    app.config['CHAT_ID'] = CHAT_ID
    return app


app = create_app()

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

@app.route('/submit', methods=['POST'])
def submit() -> str:
    ip = request.remote_addr or 'unknown'
    check_rate_limit(ip)

    token = request.form.get('csrf_token', '')
    if not token or token != session.get('csrf_token'):
        abort(400)

    text = html.escape(request.form.get('text', ''), quote=True)
    message = f'IP: {ip}\nMessage: {text}'
    bot_token = current_app.config['BOT_TOKEN']
    chat_id = current_app.config['CHAT_ID']
    if bot_token and chat_id:
        url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
        data = {'chat_id': chat_id, 'text': message}
        try:
            response = requests.post(url, data=data, timeout=5)
            print(response.status_code, response.text)
        except Exception as e:
            print('텔레그램 전송 오류:', str(e))
    return 'OK'

if __name__ == '__main__':
    # Default port is 5000. Change to 80 for production if needed.
    app.run(host='0.0.0.0', port=5000)
