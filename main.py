import os
import time
import html
from flask import Flask, render_template, request, abort, session
import requests
import config

app = Flask(__name__, static_folder=None)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change_me')

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
    if config.BOT_TOKEN and config.CHAT_ID:
        url = f'https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage'
        data = {'chat_id': config.CHAT_ID, 'text': message}
        try:
            response = requests.post(url, data=data, timeout=5)
            print(response.status_code, response.text)
        except Exception as e:
            print('텔레그램 전송 오류:', str(e))
    return 'OK'

if __name__ == '__main__':
    # Default port is 5000. Change to 80 for production if needed.
    app.run(host='0.0.0.0', port=5000)
