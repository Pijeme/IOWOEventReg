from flask import Flask, request, jsonify, render_template_string, redirect
import sqlite3
import os
from datetime import datetime
import requests

app = Flask(__name__)

DB_FILE = 'data.db'
ADMIN_PASSWORD = '1234567890'
ERASE_PASSWORD = 'psr550'
SHEET_BEST_ENDPOINT = 'https://api.sheetbest.com/sheets/5579b6ce-f97d-484c-9f62-f670ed64e5ff'

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT UNIQUE,
                church TEXT,
                area INTEGER,
                group_id TEXT,
                status TEXT DEFAULT 'Pending'
            );
        """)

        # Restore from Google Sheets if local database is empty
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM registrations')
        if cursor.fetchone()[0] == 0:
            print("SQLite is empty. Restoring from Google Sheets...")
            try:
                response = requests.get(SHEET_BEST_ENDPOINT)
                data = response.json()
                for row in data:
                    cursor.execute(
                        'INSERT OR IGNORE INTO registrations (full_name, church, area, group_id, status) VALUES (?, ?, ?, ?, ?)',
                        (row['full_name'], row['church'], row['area'], row['group_id'], row.get('status', 'Pending'))
                    )
                conn.commit()
                print("Data restored successfully.")
            except Exception as e:
                print(f"Failed to restore data: {e}")

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

    new_entries = []

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        for name in names:
            cursor.execute(
                'SELECT COUNT(*) FROM registrations WHERE full_name = ?',
                (name,))
            if cursor.fetchone()[0] > 0:
                return jsonify({
                    'status': 'error',
                    'message': f"The name '{name}' has already been registered."
                })

        for name in names:
            cursor.execute(
                'INSERT INTO registrations (full_name, church, area, group_id) VALUES (?, ?, ?, ?)',
                (name, church, area, group_id))
            new_entries.append({
                "full_name": name,
                "church": church,
                "area": area,
                "group_id": group_id,
                "status": "Pending"
            })

        conn.commit()

    # Sync to Google Sheets
    try:
        requests.post(SHEET_BEST_ENDPOINT, json=new_entries)
        print("Synced to Google Sheets.")
    except Exception as e:
        print(f"Failed to sync with Google Sheets: {e}")

    return jsonify({'status': 'success', 'group_id': group_id})

@app.route('/status')
def status():
    group_id = request.args.get('id')
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT full_name, status FROM registrations WHERE group_id = ?', (group_id,))
        rows = cursor.fetchall()

    all_approved = all(row[1] == 'Approved' for row in rows)

    return render_template_string("...your status HTML here...", rows=rows, all_approved=all_approved)

@app.route('/admin', methods=['GET'])
def admin_login():
    password = request.args.get('password')
    if password != ADMIN_PASSWORD:
        return 'Access Denied'

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT full_name, church, area, status FROM registrations')
        rows = cursor.fetchall()
        cursor.execute('SELECT DISTINCT church FROM registrations')
        churches = [row[0] for row in cursor.fetchall()]
        cursor.execute('SELECT DISTINCT area FROM registrations')
        areas = [row[0] for row in cursor.fetchall()]

    return render_template_string("...your admin HTML here...", rows=rows, churches=churches, areas=areas, erase_pass=ERASE_PASSWORD)

@app.route('/approve', methods=['POST'])
def approve():
    full_name = request.json['full_name']
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('UPDATE registrations SET status = "Approved" WHERE full_name = ?', (full_name,))
    return '', 204

@app.route('/erase', methods=['POST'])
def erase():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('DELETE FROM registrations')
    return '', 204

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
