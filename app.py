""from flask import Flask, request, jsonify, render_template_string, redirect
import sqlite3
import os
from datetime import datetime
import requests

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
                status TEXT DEFAULT 'Pending'
            );
        """)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM registrations")
        if cursor.fetchone()[0] == 0:
            try:
                response = requests.get(SHEET_BEST_URL)
                data = response.json()
                for row in data:
                    conn.execute('''
                        INSERT OR IGNORE INTO registrations (full_name, church, area, group_id, status)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (row['full_name'], row['church'], row['area'], row['group_id'], row.get('status', 'Pending')))
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

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        for name in names:
            cursor.execute('SELECT COUNT(*) FROM registrations WHERE full_name = ?', (name,))
            if cursor.fetchone()[0] > 0:
                return jsonify({'status': 'error', 'message': f"The name '{name}' has already been registered."})

        for name in names:
            cursor.execute(
                'INSERT INTO registrations (full_name, church, area, group_id) VALUES (?, ?, ?, ?)',
                (name, church, area, group_id)
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

@app.route('/status')
def status():
    group_id = request.args.get('id')
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT full_name, status FROM registrations WHERE group_id = ?',
            (group_id,))
        rows = cursor.fetchall()

    all_approved = all(row[1] == 'Approved' for row in rows)

    return render_template_string('''
    <html>
    <head>
        <title>Status</title>
        <style>
            body { font-family: Arial; padding: 20px; background: #f4f4f4; }
            .card { background: white; border-radius: 10px; padding: 20px; max-width: 600px; margin: auto; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
            .approved { color: green; font-weight: bold; }
            .pending { color: orange; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Status for Group ID: {{ request.args.get('id') }}</h2>
            <ul>
                {% for full_name, status in rows %}
                    <li>{{ full_name }} - <span class="{{ 'approved' if status == 'Approved' else 'pending' }}">{{ status }}</span></li>
                {% endfor %}
            </ul>
            {% if all_approved %}
                <p style="color: green; font-weight: bold;">All members approved ✅</p>
            {% else %}
                <p style="color: orange; font-weight: bold;">Waiting for approval ⏳</p>
            {% endif %}
        </div>
    </body>
    </html>
    ''', rows=rows, all_approved=all_approved)

@app.route('/admin')
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

    return render_template_string('''
    <html>
    <head>
        <title>Admin Panel</title>
        <style>
            body { font-family: Arial; padding: 20px; background: #eef2f3; }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 10px; border: 1px solid #ccc; text-align: left; }
            th { background-color: #f4f4f4; }
            .btn { padding: 5px 10px; background-color: #4CAF50; color: white; border: none; cursor: pointer; border-radius: 5px; }
            .btn:hover { background-color: #45a049; }
        </style>
        <script>
            function approve(full_name) {
                fetch('/approve', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ full_name: full_name })
                }).then(() => location.reload());
            }
        </script>
    </head>
    <body>
        <h2>Admin Panel</h2>
        <table>
            <tr><th>Name</th><th>Church</th><th>Area</th><th>Status</th><th>Action</th></tr>
            {% for full_name, church, area, status in rows %}
                <tr>
                    <td>{{ full_name }}</td>
                    <td>{{ church }}</td>
                    <td>{{ area }}</td>
                    <td>{{ status }}</td>
                    <td>
                        {% if status != 'Approved' %}
                            <button class="btn" onclick="approve('{{ full_name }}')">Approve</button>
                        {% endif %}
                    </td>
                </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    ''', rows=rows, churches=churches, areas=areas, erase_pass=ERASE_PASSWORD)

@app.route('/approve', methods=['POST'])
def approve():
    full_name = request.json['full_name']
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('UPDATE registrations SET status = "Approved" WHERE full_name = ?', (full_name,))
        conn.commit()

    try:
        response = requests.get(SHEET_BEST_URL)
        if response.status_code == 200:
            all_data = response.json()
            match = next((row for row in all_data if row['full_name'] == full_name), None)
            if match:
                update_url = f"{SHEET_BEST_URL}/full_name/{full_name}"
                requests.patch(update_url, json={"status": "Approved"})
    except Exception as e:
        print("Failed to update status in Google Sheets:", e)

    return '', 204

@app.route('/erase', methods=['POST'])
def erase():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('DELETE FROM registrations')
    return '', 204

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)""
