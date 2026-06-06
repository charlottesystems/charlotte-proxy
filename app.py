from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

PLATE_RECOGNIZER_TOKEN = os.environ.get('PLATE_RECOGNIZER_TOKEN', '')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/read-plate', methods=['POST'])
def read_plate():
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

@app.route('/soste', methods=['GET', 'POST'])
def soste():
    # Carica soste da file JSON
    import json
    soste_file = 'soste.json'
    
    if request.method == 'GET':
        garage = request.args.get('garage', '')
        data = request.args.get('data', '')
        targa = request.args.get('targa', '').upper()
        
        try:
            with open(soste_file, 'r') as f:
                soste = json.load(f)
        except:
            soste = []
        
        if garage:
            soste = [s for s in soste if s.get('garage') == garage]
        if data:
            soste = [s for s in soste if s.get('ingresso', '').startswith(data)]
        if targa:
            soste = [s for s in soste if targa in s.get('targa', '')]
        
        return jsonify(soste)
    
    elif request.method == 'POST':
        data = request.get_json()
        
        try:
            with open(soste_file, 'r') as f:
                soste = json.load(f)
        except:
            soste = []
        
        soste.append(data)
        
        with open(soste_file, 'w') as f:
            json.dump(soste, f, indent=2)
        
        return jsonify({'ok': True}), 201

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
