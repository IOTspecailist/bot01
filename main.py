from flask import Flask, render_template, request
import requests
import config

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    text = request.form.get('text', '')
    ip = request.remote_addr
    message = f'IP: {ip}\nMessage: {text}'
    if config.BOT_TOKEN and config.CHAT_ID:
        url = f'https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage'
        data = {'chat_id': config.CHAT_ID, 'text': message}
        try:
            requests.post(url, data=data)
        except Exception:
            pass
    return 'OK'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
