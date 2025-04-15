from flask import Flask, request, jsonify, render_template_string, redirect, send_file
import sqlite3
import os
from datetime import datetime
import requests
import pandas as pd
from io import BytesIO

app = Flask(__name__)

DB_FILE = 'data.db'
ADMIN_PASSWORD = '1234567890'
ERASE_PASSWORD = 'psr550'
SHEET_BEST_URL = 'https://api.sheetbest.com/sheets/5579b6ce-f97d-484c-9f62-f670ed64e5ff'


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT UNIQUE,
                church TEXT,
                area INTEGER,
                group_id TEXT,
                status TEXT DEFAULT 'Pending',
                last_updated TEXT
            );
        """)
        # Check if table is empty
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM registrations")
        if cursor.fetchone()[0] == 0:
            try:
                response = requests.get(SHEET_BEST_URL)
                data = response.json()
                for row in data:
                    conn.execute('''
                        INSERT OR IGNORE INTO registrations (full_name, church, area, group_id, status, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        row['full_name'],
                        row['church'],
                        row['area'],
                        row['group_id'],
                        row.get('status', 'Pending'),
                        datetime.now().isoformat()
                    ))
                conn.commit()
                print("Restored data from Google Sheets.")
            except Exception as e:
                print("Error restoring from Google Sheets:", e)


init_db()


@app.route('/')
def index():
    return open('index.html').read()


@app.route('/submit', methods=['POST'])
def submit():
    data = request.json
    area = data.get('area')
    church = data.get('church')
    names = data.get('names')
    group_id = datetime.now().strftime('%Y%m%d%H%M%S')
    now = datetime.now().isoformat()

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        for name in names:
            cursor.execute('SELECT COUNT(*) FROM registrations WHERE full_name = ?', (name,))
            if cursor.fetchone()[0] > 0:
                return jsonify({'status': 'error', 'message': f"The name '{name}' has already been registered."})

        for name in names:
            cursor.execute(
                'INSERT INTO registrations (full_name, church, area, group_id, last_updated) VALUES (?, ?, ?, ?, ?)',
                (name, church, area, group_id, now)
            )
        conn.commit()

    try:
        payload = [{
            'full_name': name,
            'church': church,
            'area': area,
            'group_id': group_id,
            'status': 'Pending'
        } for name in names]
        requests.post(SHEET_BEST_URL, json=payload)
    except Exception as e:
        print("Failed to sync to Google Sheets:", e)

    return jsonify({'status': 'success', 'group_id': group_id})


@app.route('/download_excel')
def download_excel():
    with sqlite3.connect(DB_FILE) as conn:
        df = pd.read_sql_query("SELECT full_name, church, area, group_id, status FROM registrations", conn)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Registrations')
    output.seek(0)

    return send_file(output, download_name='registrations.xlsx', as_attachment=True)


# (Other routes remain the same)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
