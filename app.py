from flask import Flask, request, jsonify, render_template, send_file
import sqlite3
import os
from datetime import datetime, timedelta
import requests
import pandas as pd

app = Flask(__name__)

DB_FILE = 'data.db'
ADMIN_PASSWORD = '1234567890'
ERASE_PASSWORD = 'psr550'
SHEET_BEST_URL = 'https://api.sheetbest.com/sheets/5579b6ce-f97d-484c-9f62-f670ed64e5ff'
LAST_SYNC_FILE = 'last_sync.txt'

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                church TEXT NOT NULL,
                area TEXT NOT NULL,
                group_id TEXT NOT NULL,
                status TEXT DEFAULT 'Pending'
            )
        ''')
        conn.commit()

def generate_group_id():
    return datetime.now().strftime('%Y%m%d%H%M%S%f')

def should_sync_to_sheets():
    if not os.path.exists(LAST_SYNC_FILE):
        return True
    with open(LAST_SYNC_FILE, 'r') as f:
        last_sync = datetime.fromisoformat(f.read().strip())
    return datetime.now() - last_sync >= timedelta(minutes=9)

def update_last_sync_time():
    with open(LAST_SYNC_FILE, 'w') as f:
        f.write(datetime.now().isoformat())

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    data = request.get_json()
    area = data.get('area')
    church = data.get('church')
    names = data.get('names')

    if not area or not church or not names:
        return jsonify({'status': 'error', 'message': 'Missing required fields'})

    group_id = generate_group_id()

    try:
        with get_db_connection() as conn:
            for name in names:
                existing = conn.execute('SELECT 1 FROM registrations WHERE full_name = ?', (name,)).fetchone()
                if existing:
                    return jsonify({'status': 'error', 'message': f'Duplicate name: {name}'})
                conn.execute('INSERT INTO registrations (full_name, church, area, group_id) VALUES (?, ?, ?, ?)',
                             (name, church, area, group_id))
            conn.commit()

        # Google Sheets Sync (every 9 minutes)
        try:
            if should_sync_to_sheets():
                payload = [{
                    'full_name': name,
                    'church': church,
                    'area': area,
                    'group_id': group_id,
                    'status': 'Pending'
                } for name in names]
                requests.post(SHEET_BEST_URL, json=payload)
                update_last_sync_time()
        except Exception as e:
            print("Google Sheets sync failed:", e)

        return jsonify({'status': 'success', 'group_id': group_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# Other routes like /status, /admin, /download, etc., remain unchanged

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
