from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import requests
import threading
import time
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    area = db.Column(db.Integer, nullable=False)
    church = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()  # ✅ This ensures the table is created if it doesn't exist

SHEETBEST_URL = 'https://api.sheetbest.com/sheets/5579b6ce-f97d-484c-9f62-f670ed64e5ff'
LAST_SYNC_TIME = datetime.utcnow() - timedelta(minutes=9)
SYNC_INTERVAL = timedelta(minutes=9)

def sync_to_google_sheets():
    global LAST_SYNC_TIME
    while True:
        time.sleep(60)
        if datetime.utcnow() - LAST_SYNC_TIME >= SYNC_INTERVAL:
            with app.app_context():
                data = Registration.query.all()
                payload = [
                    {
                        "ID": r.id,
                        "Group ID": r.group_id,
                        "Name": r.name,
                        "Area": r.area,
                        "Church": r.church,
                        "Timestamp": r.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    } for r in data
                ]
                try:
                    requests.post(SHEETBEST_URL, json=payload)
                    LAST_SYNC_TIME = datetime.utcnow()
                except Exception as e:
                    print(f"Sync failed: {e}")

threading.Thread(target=sync_to_google_sheets, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    data = request.form
    group_id = data.get('group_id')
    names = data.getlist('name')
    area = data.get('area')
    church = data.get('church')

    # Server-side validation
    if not area or not area.isdigit() or not (1 <= int(area) <= 7):
        return "Please input Area number 1 to 7 only", 400
    if not church:
        return "Please provide your Church information to proceed", 400

    for name in names:
        if name.strip():
            existing = Registration.query.filter_by(name=name).first()
            if not existing:
                new_entry = Registration(
                    group_id=group_id,
                    name=name.strip(),
                    area=int(area),
                    church=church.strip()
                )
                db.session.add(new_entry)
    db.session.commit()
    return redirect(url_for('status'))

@app.route('/status')
def status():
    entries = Registration.query.order_by(Registration.timestamp.desc()).all()
    return render_template('index.html', entries=entries, show_status=True)

@app.route('/admin')
def admin():
    password = request.args.get('password')
    if password == '1234567890':
        data = Registration.query.all()
        return render_template('index.html', entries=data, show_admin=True)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
