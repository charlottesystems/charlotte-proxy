from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import base64
import json
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
CORS(app, origins=[
    'https://charlottesystems.github.io',
    'http://localhost',
    'http://127.0.0.1'
], supports_credentials=False)

PLATE_RECOGNIZER_TOKEN = os.environ.get('PLATE_RECOGNIZER_TOKEN', '')
SHEET_ID = '1cR5QwltHucbvBgXuu-NLl0l0p3S6EOOPltkgRV6gkwY'
GMAIL_USER = os.environ.get('GMAIL_USER', '')
GMAIL_PASSWORD = os.environ.get('GMAIL_PASSWORD', '')

# Token di sblocco temporanei: {token: timestamp_scadenza}
sblocco_tokens = {}

def get_sheet():
    creds_json = os.environ.get('GOOGLE_CREDENTIALS', '')
    creds_dict = json.loads(creds_json)
    scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)
    try:
        ws = sheet.worksheet('Soste')
    except:
        ws = sheet.add_worksheet('Soste', rows=10000, cols=10)
        ws.append_row(['id', 'targa', 'tipo', 'garage', 'convenzione', 'categoria', 'ingresso', 'uscita', 'durata'])
    return ws

def invia_email_blocco(token):
    try:
        sblocco_url = f'https://charlotte-proxy.onrender.com/sblocca?token={token}'
        msg = MIMEMultipart('alternative')
        msg['Subject'] = '🔒 Charlotte — Dispositivo bloccato (3 tentativi PIN falliti)'
        msg['From'] = GMAIL_USER
        msg['To'] = GMAIL_USER

        html = f'''
        <html><body style="font-family:Arial,sans-serif;background:#0a0a0f;color:#e8e8f0;padding:24px;">
        <div style="max-width:500px;margin:0 auto;background:#16161f;border-radius:16px;padding:24px;border:1px solid #2a2a3a;">
          <h2 style="color:#ef4444;">🔒 Dispositivo bloccato</h2>
          <p>Un dispositivo ha effettuato <strong>3 tentativi PIN falliti</strong> sull'app Charlotte — City Parking.</p>
          <p>Il dispositivo è bloccato per <strong>1 ora</strong>.</p>
          <p>Se sei stato tu o un tuo operatore, clicca il pulsante per sbloccare immediatamente:</p>
          <a href="{sblocco_url}" style="display:inline-block;margin-top:16px;padding:14px 28px;background:#7c3aed;color:white;border-radius:10px;text-decoration:none;font-weight:bold;font-size:16px;">
            🔓 Sblocca dispositivo
          </a>
          <p style="margin-top:24px;font-size:12px;color:#6b6b85;">
            Se non riconosci questo accesso, ignora questa email. Il dispositivo si sbloccherà automaticamente dopo 1 ora.
          </p>
        </div>
        </body></html>
        '''
        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
        return True
    except Exception as e:
        print(f'Errore invio email: {e}')
        return False

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/alert-blocco', methods=['POST', 'OPTIONS'])
def alert_blocco():
    if request.method == 'OPTIONS':
        return '', 204
    # Genera token univoco valido 2 ore
    import time
    token = secrets.token_urlsafe(32)
    sblocco_tokens[token] = time.time() + 7200
    invia_email_blocco(token)
    return jsonify({'ok': True, 'token': token})

@app.route('/sblocca', methods=['GET'])
def sblocca():
    import time
    token = request.args.get('token', '')
    scadenza = sblocco_tokens.get(token, 0)
    if token and scadenza > time.time():
        del sblocco_tokens[token]
        return '''
        <html><body style="font-family:Arial,sans-serif;background:#0a0a0f;color:#e8e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;">
        <div style="text-align:center;background:#16161f;padding:40px;border-radius:16px;border:1px solid #10b981;">
          <div style="font-size:64px;">✅</div>
          <h2 style="color:#10b981;margin-top:16px;">Dispositivo sbloccato</h2>
          <p style="color:#6b6b85;">Il dispositivo può ora accedere nuovamente a Charlotte.</p>
          <p style="color:#6b6b85;font-size:12px;margin-top:16px;">Riapri l'app sul dispositivo e inserisci il PIN.</p>
        </div>
        </body></html>
        ''', 200, {'Content-Type': 'text/html'}
    else:
        return '''
        <html><body style="font-family:Arial,sans-serif;background:#0a0a0f;color:#e8e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;">
        <div style="text-align:center;background:#16161f;padding:40px;border-radius:16px;border:1px solid #ef4444;">
          <div style="font-size:64px;">❌</div>
          <h2 style="color:#ef4444;margin-top:16px;">Link non valido o scaduto</h2>
          <p style="color:#6b6b85;">Il link di sblocco è già stato usato o è scaduto.</p>
        </div>
        </body></html>
        ''', 400, {'Content-Type': 'text/html'}

@app.route('/read-plate', methods=['POST', 'OPTIONS'])
def read_plate():
    if request.method == 'OPTIONS':
        return '', 204
    if request.content_type and 'application/json' in request.content_type:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'error': 'Nessuna immagine ricevuta'}), 400
        image_bytes = base64.b64decode(data['image'])
        mime = data.get('mime', 'image/jpeg')
        response = requests.post(
            'https://api.platerecognizer.com/v1/plate-reader/',
            headers={'Authorization': f'Token {PLATE_RECOGNIZER_TOKEN}'},
            files={'upload': ('targa.jpg', image_bytes, mime)},
            data={'regions': 'it'}
        )
    else:
        if 'image' not in request.files:
            return jsonify({'error': 'Nessuna immagine ricevuta'}), 400
        image = request.files['image']
        response = requests.post(
            'https://api.platerecognizer.com/v1/plate-reader/',
            headers={'Authorization': f'Token {PLATE_RECOGNIZER_TOKEN}'},
            files={'upload': image},
            data={'regions': 'it'}
        )
    return jsonify(response.json()), response.status_code

@app.route('/soste', methods=['GET', 'POST', 'PUT', 'OPTIONS'])
def soste():
    if request.method == 'OPTIONS':
        return '', 204
    ws = get_sheet()
    if request.method == 'GET':
        garage = request.args.get('garage', '')
        targa = request.args.get('targa', '').upper()
        solo_attive = request.args.get('attive', '')
        rows = ws.get_all_records()
        if garage:
            rows = [r for r in rows if r.get('garage') == garage]
        if targa:
            rows = [r for r in rows if targa in r.get('targa', '')]
        if solo_attive == '1':
            rows = [r for r in rows if not r.get('uscita')]
        return jsonify(rows)
    elif request.method == 'POST':
        data = request.get_json()
        row = [
            data.get('id', ''), data.get('targa', ''), data.get('tipo', ''),
            data.get('garage', ''), data.get('convenzione', ''), data.get('categoria', ''),
            data.get('ingresso', ''), data.get('uscita', ''), data.get('durata', '')
        ]
        ws.append_row(row)
        return jsonify({'ok': True}), 201
    elif request.method == 'PUT':
        data = request.get_json()
        targa = data.get('targa', '')
        garage = data.get('garage', '')
        uscita = data.get('uscita', '')
        durata = data.get('durata', '')
        rows = ws.get_all_values()
        header = rows[0]
        targa_col = header.index('targa') + 1
        garage_col = header.index('garage') + 1
        uscita_col = header.index('uscita') + 1
        durata_col = header.index('durata') + 1
        for i, row in enumerate(rows[1:], start=2):
            if row[targa_col-1] == targa and row[garage_col-1] == garage and not row[uscita_col-1]:
                ws.update_cell(i, uscita_col, uscita)
                ws.update_cell(i, durata_col, durata)
                return jsonify({'ok': True})
        return jsonify({'error': 'Sosta non trovata'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
