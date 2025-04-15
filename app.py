from flask import Flask, request, jsonify, render_template_string, redirect
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

    return render_template_string("""
        <html>
        <head>
            <title>Status Page</title>
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <style>
                body { font-family: Arial, sans-serif; background: linear-gradient(to right, #ffafbd, #ffc3a0); margin: 0; padding: 20px; text-align: center; }
                .container { max-width: 500px; margin: auto; }
                img { height: 80px; margin-bottom: 10px; }
                h1, h2 { color: #fff; text-shadow: 1px 1px 3px #333; }
                .status-box { padding: 15px; border-radius: 12px; margin: 10px 0; font-weight: bold; color: #fff; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
                .approved { background-color: #6bcf63; }
                .pending { background-color: #f96c6c; }
                button { margin: 10px 5px; padding: 10px 20px; font-size: 16px; background-color: #ff70a6; color: white; border: none; border-radius: 8px; cursor: pointer; }
                button:hover { background-color: #ff4d94; }
            </style>
        </head>
        <body>
            <div class="container">
                <img src="/static/logo.png" alt="Logo" />
                <h1>International One Way Outreach Church</h1>
                <h2>Status Page</h2>
                {% for name, status in rows %}
                    <div class="status-box {{ 'approved' if status == 'Approved' else 'pending' }}">
                        {{ name }} - {{ status }}
                    </div>
                {% endfor %}
                <button onclick="location.reload()">Refresh</button>
                {% if all_approved %}
                    <button onclick="window.location.href='/'">Done!</button>
                {% endif %}
            </div>
        </body>
        </html>
    """, rows=rows, all_approved=all_approved)

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

    return render_template_string("""
        <html>
        <head>
            <title>Admin Panel</title>
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <style>
                body { font-family: Arial, sans-serif; background: linear-gradient(to right, #a18cd1, #fbc2eb); margin: 0; padding: 20px; text-align: center; color: #fff; }
                img { height: 80px; margin-bottom: 10px; }
                h1, h2 { color: #fff; text-shadow: 1px 1px 3px #333; }
                select, button { padding: 8px 12px; border-radius: 8px; border: none; margin: 5px; font-size: 14px; }
                button { background-color: #ff70a6; color: white; cursor: pointer; }
                button:hover { background-color: #ff4d94; }
                table { width: 100%; max-width: 600px; margin: 20px auto; border-collapse: collapse; background: #fff; color: #333; border-radius: 12px; overflow: hidden; }
                th, td { padding: 10px; border: 1px solid #ccc; }
                th { background-color: #f8a5c2; }
                td button { background-color: #55efc4; color: #2d3436; }
                #count { margin-top: 10px; font-weight: bold; }
            </style>
        </head>
        <body>
            <img src="/static/logo.png" alt="Logo" />
            <h1>International One Way Outreach Church</h1>
            <h2>Admin Panel</h2>

            <label>Filter Registrations By:</label>
            <select id="filterType" onchange="applyFilter()">
                <option value="all">All</option>
                <option value="church">Church</option>
                <option value="area">Area</option>
            </select>

            <select id="filterValue" onchange="filterRows()" style="display:none;"></select>
            <div id="count"></div>

            <table>
                <tr><th>Full Name</th><th>Church</th><th>Area</th><th>Status</th></tr>
                {% for full_name, church, area, status in rows %}
                    <tr data-church="{{ church }}" data-area="{{ area }}">
                        <td>{{ full_name }}</td>
                        <td>{{ church }}</td>
                        <td>{{ area }}</td>
                        <td>
                            {{ status }}
                            {% if status == 'Pending' %}
                                <button onclick="approve('{{ full_name }}')">Approve</button>
                            {% endif %}
                        </td>
                    </tr>
                {% endfor %}
            </table>

            <button onclick="eraseData()">Erase All Data</button>
            <button onclick="location.reload()">Refresh Page</button>

            <script>
                const churches = {{ churches | tojson }};
                const areas = {{ areas | tojson }};

                function applyFilter() {
                    const type = document.getElementById('filterType').value;
                    const valDropdown = document.getElementById('filterValue');
                    const countDiv = document.getElementById('count');

                    if (type === 'all') {
                        valDropdown.style.display = 'none';
                        showAll();
                        const count = document.querySelectorAll('table tr[data-church]').length;
                        countDiv.innerText = "Total Registered: " + count;
                    } else {
                        valDropdown.style.display = 'inline';
                        valDropdown.innerHTML = '';
                        const list = type === 'church' ? churches : areas;

                        list.forEach(val => {
                            const opt = document.createElement('option');
                            opt.value = val;
                            opt.innerText = val;
                            valDropdown.appendChild(opt);
                        });

                        filterRows();
                    }
                }

                function filterRows() {
                    const type = document.getElementById('filterType').value;
                    const val = document.getElementById('filterValue').value;
                    let count = 0;
                    document.querySelectorAll('table tr[data-church]').forEach(row => {
                        if (row.dataset[type] == val) {
                            row.style.display = '';
                            count++;
                        } else {
                            row.style.display = 'none';
                        }
                    });
                    document.getElementById('count').innerText = "Total Registered: " + count;
                }

                function showAll() {
                    document.querySelectorAll('table tr[data-church]').forEach(row => row.style.display = '');
                }

                function approve(name) {
                    fetch('/approve', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ full_name: name })
                    }).then(() => location.reload());
                }

                function eraseData() {
                    const pass = prompt("Enter password to erase all data:");
                    if (pass === "{{ erase_pass }}") {
                        fetch('/erase', { method: 'POST' }).then(() => location.reload());
                    } else {
                        alert("Incorrect password.");
                    }
                }
            </script>
        </body>
        </html>
    """, rows=rows, churches=churches, areas=areas, erase_pass=ERASE_PASSWORD)

@app.route('/approve', methods=['POST'])
def approve():
    full_name = request.json['full_name']
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('UPDATE registrations SET status = "Approved" WHERE full_name = ?', (full_name,))
    try:
        sheet_data = requests.get(SHEET_BEST_URL).json()
        for row in sheet_data:
            if row.get('full_name') == full_name:
                update_url = f"{SHEET_BEST_URL}/full_name/{full_name}"
                requests.patch(update_url, json={'status': 'Approved'})
                break
    except Exception as e:
        print("Failed to update Google Sheets status:", e)

    return '', 204

@app.route('/erase', methods=['POST'])
def erase():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('DELETE FROM registrations')
    return '', 204

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
