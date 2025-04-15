from flask import Flask, request, jsonify
import sqlite3
import requests
import os

app = Flask(__name__)

DATABASE = 'registrations.db'
SHEET_BEST_URL = "https://api.sheetbest.com/sheets/5579b6ce-f97d-484c-9f62-f670ed64e5ff"

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area INTEGER,
            church TEXT,
            name TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_to_db(area, church, names, status="Pending"):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    for name in names:
        c.execute("INSERT INTO registrations (area, church, name, status) VALUES (?, ?, ?, ?)", (area, church, name, status))
    conn.commit()
    conn.close()

def sync_to_google_sheets(area, church, names, status="Pending"):
    for name in names:
        data = {
            "area": area,
            "church": church,
            "name": name,
            "status": status
        }
        requests.post(SHEET_BEST_URL, json=data)

def get_status(area, church):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT name, status FROM registrations WHERE area = ? AND church = ?", (area, church))
    rows = c.fetchall()
    conn.close()
    return rows

@app.route('/')
def index():
    return open('index.html').read()

@app.route('/submit', methods=['POST'])
def submit():
    data = request.get_json()
    area = data['area']
    church = data['church']
    names = data['names']

    save_to_db(area, church, names)
    sync_to_google_sheets(area, church, names)

    return jsonify({"message": "Registration submitted successfully!"})

@app.route('/status', methods=['POST'])
def status():
    data = request.get_json()
    area = data['area']
    church = data['church']
    rows = get_status(area, church)
    return jsonify(rows)

@app.route('/admin', methods=['GET'])
def admin():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT id, area, church, name, status FROM registrations")
    rows = c.fetchall()
    conn.close()
    return jsonify(rows)

# ✅ STATUS UPDATE CODE PRESERVED
@app.route('/approve', methods=['POST'])
def approve():
    data = request.get_json()
    entry_id = data['id']

    # Update SQLite
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("UPDATE registrations SET status = 'Approved' WHERE id = ?", (entry_id,))
    conn.commit()

    # Fetch entry for syncing
    c.execute("SELECT area, church, name FROM registrations WHERE id = ?", (entry_id,))
    row = c.fetchone()
    conn.close()

    if row:
        area, church, name = row
        # Sync status to Google Sheets
        requests.patch(SHEET_BEST_URL, json={
            "area": area,
            "church": church,
            "name": name
        }, params={"status": "Approved"})

    return jsonify({"message": "Status updated to Approved"})

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 3000))
    app.run(host='0.0.0.0', port=port)
