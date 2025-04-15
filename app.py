from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Registration model
class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.String(20))
    name = db.Column(db.String(100))
    area = db.Column(db.Integer)
    church = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Create DB tables at startup
with app.app_context():
    db.create_all()

# Serve the single page app
@app.route("/")
@app.route("/status")
@app.route("/admin")
def serve_index():
    return send_from_directory("static", "index.html")

# Serve static files (e.g. logo.png)
@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

# Submit registration
@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()
    names = data.get("names", [])
    area = data.get("area")
    church = data.get("church")

    if not names or not area or not church:
        return jsonify({"status": "error", "message": "Missing data"}), 400

    group_id = datetime.now().strftime("%Y%m%d%H%M%S")

    try:
        for name in names:
            reg = Registration(group_id=group_id, name=name, area=int(area), church=church)
            db.session.add(reg)
        db.session.commit()
        return jsonify({"status": "success", "group_id": group_id})
    except Exception as e:
        print(f"Error saving registration: {e}")
        return jsonify({"status": "error", "message": "Could not save registration."}), 500

# API for loading registrations by group_id (for /status view)
@app.route("/api/status")
def get_status():
    group_id = request.args.get("id")
    if not group_id:
        return jsonify({"status": "error", "message": "Missing group ID"}), 400

    registrations = Registration.query.filter_by(group_id=group_id).all()
    result = [{"name": r.name, "area": r.area, "church": r.church} for r in registrations]
    return jsonify({"status": "success", "group_id": group_id, "registrations": result})

# API for admin data (protected by password)
@app.route("/api/admin")
def get_admin_data():
    password = request.args.get("password")
    if password != "1234567890":
        return jsonify({"status": "error", "message": "Access Denied"}), 403

    registrations = Registration.query.order_by(Registration.timestamp.desc()).all()
    result = [{
        "name": r.name,
        "area": r.area,
        "church": r.church,
        "group_id": r.group_id,
        "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    } for r in registrations]

    return jsonify({"status": "success", "registrations": result})

# Run the app locally
if __name__ == "__main__":
    app.run(debug=True)
