from flask import Flask, request, jsonify, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests
import uuid
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

SHEETBEST_URL = 'https://api.sheetbest.com/sheets/5579b6ce-f97d-484c-9f62-f670ed64e5ff'
ADMIN_PASSWORD = '1234567890'
last_update_time = datetime.min

# Define the model
class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.String(20))
    name = db.Column(db.String(100), unique=True)
    area = db.Column(db.Integer)
    church = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Route: Home page
@app.route('/')
def index():
    return render_template('index.html')

# Route: Status page
@app.route('/status')
def status():
    group_id = request.args.get('id')
    if not group_id:
        return "Missing ID", 400
    group = Registration.query.filter_by(group_id=group_id).all()
    if not group:
        return "Group ID not found", 404
    return render_template('status.html', group=group)

# Route: Admin page
@app.route('/admin')
def admin():
    password = request.args.get('password')
    if password != ADMIN_PASSWORD:
        return "Unauthorized", 401

    global last_update_time
    now = datetime.utcnow()
    diff = (now - last_update_time).total_seconds()

    if diff >= 540:  # 9 minutes
        sync_to_google_sheets()
        last_update_time = now

    data = Registration.query.order_by(Registration.timestamp.desc()).all()
    return render_template('admin.html', data=data)

# Route: Submit form data
@app.route('/submit', methods=['POST'])
def submit():
    data = request.get_json()
    area = data.get('area')
    church = data.get('church')
    names = data.get('names')

    if not area or not (1 <= int(area) <= 7):
        return jsonify({'status': 'error', 'message': 'Please input Area number 1 to 7 only'}), 400

    if not church or church.strip() == '':
        return jsonify({'status': 'error', 'message': 'Please provide your Church information to proceed'}), 400

    group_id = str(uuid.uuid4())[:8]
    for name in names:
        existing = Registration.query.filter_by(name=name).first()
        if existing:
            return jsonify({'status': 'error', 'message': 'Duplicate Name Entry'}), 400
        new_entry = Registration(name=name, group_id=group_id, area=area, church=church)
        db.session.add(new_entry)

    db.session.commit()
    return jsonify({'status': 'success', 'group_id': group_id})

# Function: Sync to Google Sheets
def sync_to_google_sheets():
    data = Registration.query.all()
    payload = [{
        'Name': d.name,
        'Area': d.area,
        'Church': d.church,
        'Group ID': d.group_id,
        'Timestamp': d.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    } for d in data]

    try:
        response = requests.post(SHEETBEST_URL, json=payload)
        response.raise_for_status()
        print("Synced to Google Sheets")
    except Exception as e:
        print(f"Error syncing to Google Sheets: {e}")

# Initialize the database
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=10000)
