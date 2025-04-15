from flask import Flask, request, jsonify, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import requests
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///registrations.db'
db = SQLAlchemy(app)

SHEET_BEST_URL = 'https://api.sheetbest.com/sheets/5579b6ce-f97d-484c-9f62-f670ed64e5ff'
last_sync_time = datetime.min

class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    area = db.Column(db.Integer, nullable=False)
    church = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    group_id = db.Column(db.String(50), nullable=False)

def sync_to_sheet():
    global last_sync_time
    if datetime.now() - last_sync_time >= timedelta(minutes=9):
        all_data = Registration.query.all()
        data = [
            {
                'Area': r.area,
                'Church': r.church,
                'Name': r.name,
                'Group ID': r.group_id
            } for r in all_data
        ]
        try:
            requests.post(SHEET_BEST_URL, json=data)
            last_sync_time = datetime.now()
        except Exception as e:
            print("Sync to Google Sheets failed:", e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    data = request.json
    area = data.get('area')
    church = data.get('church')
    names = data.get('names')

    if not (1 <= int(area) <= 7):
        return jsonify({'status': 'error', 'message': 'Invalid area number. Must be 1 to 7.'})

    if not church:
        return jsonify({'status': 'error', 'message': 'Church name is required.'})

    if not names:
        return jsonify({'status': 'error', 'message': 'At least one name is required.'})

    group_id = datetime.now().strftime('%Y%m%d%H%M%S')

    for name in names:
        if Registration.query.filter_by(name=name).first():
            return jsonify({'status': 'error', 'message': f'Duplicate name entry: {name}'})
        db.session.add(Registration(area=area, church=church, name=name, group_id=group_id))

    db.session.commit()
    sync_to_sheet()
    return jsonify({'status': 'success', 'group_id': group_id})

@app.route('/status')
def status():
    group_id = request.args.get('id')
    registrations = Registration.query.filter_by(group_id=group_id).all()
    return render_template('status.html', registrations=registrations, group_id=group_id)

@app.route('/admin')
def admin():
    registrations = Registration.query.all()
    return render_template('admin.html', registrations=registrations)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
