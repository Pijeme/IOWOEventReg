from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import threading
import requests

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///registrations.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Create tables
with app.app_context():
    db.create_all()

# Model for registrations
class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.String(20))
    name = db.Column(db.String(100))
    area = db.Column(db.String(10))
    church = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Google Sheet sync setup
SHEET_URL = 'https://api.sheetbest.com/sheets/5579b6ce-f97d-484c-9f62-f670ed64e5ff'
last_synced = datetime.utcnow() - timedelta(minutes=9)

def sync_to_google_sheets():
    global last_synced
    now = datetime.utcnow()
    if now - last_synced >= timedelta(minutes=9):
        data = []
        with app.app_context():
            registrations = Registration.query.all()
            for reg in registrations:
                data.append({
                    'Timestamp': reg.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'Group ID': reg.group_id,
                    'Name': reg.name,
                    'Area': reg.area,
                    'Church': reg.church
                })
        try:
            requests.post(SHEET_URL, json=data)
            last_synced = now
        except Exception as e:
            print("Error syncing to Google Sheets:", e)

# Background thread to sync every 9 minutes
def schedule_sync():
    while True:
        sync_to_google_sheets()
        threading.Event().wait(540)  # 9 minutes

threading.Thread(target=schedule_sync, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    data = request.get_json()
    area = data.get('area')
    church = data.get('church')
    names = data.get('names')

    # Validation
    try:
        area_num = int(area)
        if area_num < 1 or area_num > 7:
            return jsonify({'status': 'error', 'message': 'Please input Area number 1 to 7 only'}), 400
    except:
        return jsonify({'status': 'error', 'message': 'Area must be a number between 1 and 7'}), 400

    if not church or not church.strip():
        return jsonify({'status': 'error', 'message': 'Please provide your Church information to proceed'}), 400

    if not names or not any(n.strip() for n in names):
        return jsonify({'status': 'error', 'message': 'Please enter at least one name'}), 400

    group_id = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"

    with app.app_context():
        for name in names:
            name = name.strip()
            if name:
                existing = Registration.query.filter_by(name=name).first()
                if existing:
                    return jsonify({'status': 'error', 'message': 'Error! Duplicate Name Entry.'}), 400
                reg = Registration(name=name, area=area, church=church, group_id=group_id)
                db.session.add(reg)
        db.session.commit()

    sync_to_google_sheets()
    return jsonify({'status': 'success', 'group_id': group_id})

@app.route('/status')
def status():
    group_id = request.args.get('id')
    with app.app_context():
        people = Registration.query.filter_by(group_id=group_id).all()
    return render_template('status.html', people=people, group_id=group_id)

@app.route('/admin')
def admin():
    with app.app_context():
        registrations = Registration.query.all()
    return render_template('admin.html', registrations=registrations)

if __name__ == '__main__':
    app.run(debug=True)
