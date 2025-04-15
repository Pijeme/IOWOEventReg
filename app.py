from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
from datetime import datetime
import pandas as pd
import requests
import io

app = Flask(__name__)

DB_FILE = "database.db"
SHEETBEST_URL = "https://api.sheetbest.com/sheets/5579b6ce-f97d-484c-9f62-f670ed64e5ff"

# Initialize DB
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                area_number TEXT NOT NULL,
                church_name TEXT NOT NULL,
                registrant_name TEXT NOT NULL,
                registration_type TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_updated DATETIME
            )
        ''')
        conn.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    data = request.get_json()
    area = data.get('area')
    church = data.get('church')
    names = data.get('names', [])
    registration_type = 'group' if len(names) > 1 else 'single'
    now = datetime.utcnow().isoformat()

    if not area or not church or not names:
        return jsonify({'status': 'error', 'message': 'Please complete all fields.'})

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        for name in names:
            cursor.execute('''
                INSERT INTO registrations (area_number, church_name, registrant_name, registration_type, last_updated)
                VALUES (?, ?, ?, ?, ?)
            ''', (area, church, name, registration_type, now))
        conn.commit()

    # Send to Google Sheets via Sheet.best
    payload = [
        {
            "Area Number": area,
            "Church Name": church,
            "Registrant Name": name,
            "Registration Type": registration_type,
            "Timestamp": now
        }
        for name in names
    ]
    try:
        requests.post(SHEETBEST_URL, json=payload)
    except Exception as e:
        print("Error syncing to Google Sheets:", e)

    return jsonify({"status": "success", "group_id": now})

@app.route('/status')
def status():
    group_id = request.args.get("id")
    return f"Registration successful! Group ID: {group_id}"

@app.route('/admin')
def admin():
    password = request.args.get("password")
    if password != "1234567890":
        return "Unauthorized", 401

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT area_number, church_name, registrant_name, registration_type, timestamp FROM registrations ORDER BY timestamp DESC")
        data = cursor.fetchall()

    return render_template("admin.html", registrations=data)

@app.route('/save-database')
def save_database():
    with sqlite3.connect(DB_FILE) as conn:
        df = pd.read_sql_query("SELECT * FROM registrations", conn)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Registrations')

    output.seek(0)
    return send_file(output, as_attachment=True, download_name="registrations.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
