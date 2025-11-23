import os
import time
from typing import Iterable

from flask import Flask, render_template, request, abort, session
import pyfiglet
from dotenv import load_dotenv
from markupsafe import Markup, escape

# Attempt to load environment variables from a .env file if present.
load_dotenv()

from common.telegram_client import send_telegram_message


MARKET_LINKS: Iterable[tuple[str, str]] = (
    ("경제달력", "https://kr.investing.com/economic-calendar/"),
    ("중앙은행 기준금리", "https://kr.investing.com/central-banks/"),
)

def format_links_message() -> str:
    return "\n".join(f"{name}: {url}" for name, url in MARKET_LINKS)


def format_for_display(text: str) -> Markup:
    safe_text = escape(text)
    return Markup("<br>".join(str(safe_text).splitlines()))


def dispatch_market_links(prefix: str | None = None) -> str:
    message = format_links_message()
    if prefix:
        message = f"{prefix}\n{message}"
    return message


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change_me')
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

    raw_text = request.form.get('text', '').strip()
    message = f"[Web Dispatch] IP: {ip}\n{raw_text}" if raw_text else f"[Web Dispatch] IP: {ip}"
    success = send_telegram_message(message, timeout=10, retries=1)

    display_text = format_for_display(raw_text or "(메시지 없음)")
    status_text = "텔레그램 전송을 완료했습니다" if success else "텔레그램 전송에 실패했습니다"
    status_tag = "Dispatch Sent" if success else "Dispatch Failed"
    status_hint = "에디터가 곧 확인 후 회신합니다" if success else "환경 변수(TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)를 확인해주세요"

    return render_template(
        'result.html',
        text=display_text,
        status_text=status_text,
        status_tag=status_tag,
        status_hint=status_hint,
    )


@app.route('/send-links', methods=['POST'])
def send_links() -> str:
    ip = request.remote_addr or 'unknown'
    check_rate_limit(ip)

    token = request.form.get('csrf_token', '')
    if not token or token != session.get('csrf_token'):
        abort(400)

    message = dispatch_market_links(prefix=f"[Manual Trigger] IP: {ip}")
    success = send_telegram_message(message, timeout=10, retries=1)

    display_text = format_for_display(format_links_message())
    status_text = "텔레그램 전송을 완료했습니다" if success else "텔레그램 전송에 실패했습니다"
    status_tag = "Dispatch Sent" if success else "Dispatch Failed"
    status_hint = "에디터가 곧 확인 후 회신합니다" if success else "환경 변수(TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)를 확인해주세요"

    return render_template(
        'result.html',
        text=display_text,
        status_text=status_text,
        status_tag=status_tag,
        status_hint=status_hint,
    )

if __name__ == '__main__':
    # Default port is 5000. Change to 80 for production if needed.
    app.run(host='0.0.0.0', port=5000)
