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
        # Check if table is empty
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

    # Send to Google Sheets
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
            <style>
                body { background-color: #1f1f1f; color: white; font-family: Arial, sans-serif; text-align: center; padding: 20px; }
                .status-box { background: #333; padding: 15px; margin: 10px auto; width: 300px; border-radius: 5px; }
                .approved { background-color: green; }
                .pending { background-color: red; }
                button { margin-top: 20px; padding: 10px 20px; font-size: 16px; background-color: #00bfff; color: white; border: none; border-radius: 5px; cursor: pointer; }
            </style>
        </head>
        <body>
            <img src="/static/logo.png" alt="Logo" style="height: 100px;" />
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
            <style>
                body { background-color: #1f1f1f; color: white; font-family: Arial, sans-serif; text-align: center; }
                table { margin: auto; background-color: #333; color: white; border-collapse: collapse; }
                th, td { padding: 10px; border: 1px solid #fff; }
                button { margin-top: 10px; padding: 10px; background-color: #00bfff; color: white; border: none; border-radius: 5px; cursor: pointer; }
                select { margin: 10px; padding: 5px; }
            </style>
        </head>
        <body>
            <img src="/static/logo.png" alt="Logo" style="height: 100px;" />
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
                        <td style="background-color: {{ 'green' if status == 'Approved' else 'red' }};">
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
    return '', 204

@app.route('/erase', methods=['POST'])
def erase():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('DELETE FROM registrations')
    return '', 204

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
