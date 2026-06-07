from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import base64
import json
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

# Credenziali Google da variabile d'ambiente
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

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

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
            data.get('id', ''),
            data.get('targa', ''),
            data.get('tipo', ''),
            data.get('garage', ''),
            data.get('convenzione', ''),
            data.get('categoria', ''),
            data.get('ingresso', ''),
            data.get('uscita', ''),
            data.get('durata', '')
        ]
        ws.append_row(row)
        return jsonify({'ok': True}), 201

    elif request.method == 'PUT':
        # Aggiorna uscita di una sosta esistente
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
