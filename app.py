from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///data.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# -------------------------------
# Database Model
# -------------------------------
class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.String(50))
    name = db.Column(db.String(100))
    area = db.Column(db.Integer)
    church = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# -------------------------------
# Create DB on startup
# -------------------------------
@app.before_first_request
def create_tables():
    db.create_all()

# -------------------------------
# Routes
# -------------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/submit", methods=["POST"])
def submit():
    try:
        data = request.get_json()
        print("📥 Received JSON data:", data)

        area = str(data.get("area", "")).strip()
        church = str(data.get("church", "")).strip()
        names = data.get("names", [])

        if not area.isdigit() or not (1 <= int(area) <= 7):
            return jsonify({"status": "error", "message": "Invalid area number"}), 400
        if not church:
            return jsonify({"status": "error", "message": "Church name is required"}), 400
        if not names or not all(name.strip() for name in names):
            return jsonify({"status": "error", "message": "At least one name is required"}), 400

        group_id = datetime.now().strftime("%Y%m%d%H%M%S")

        for name in names:
            if name.strip():
                reg = Registration(
                    name=name.strip(),
                    area=int(area),
                    church=church,
                    group_id=group_id,
                    timestamp=datetime.now()
                )
                db.session.add(reg)

        db.session.commit()

        return jsonify({"status": "success", "group_id": group_id})

    except Exception as e:
        print("🚨 Error in /submit:", e)
        return jsonify({"status": "error", "message": "Error! Could not submit. Please try again."}), 500

@app.route("/status")
def status():
    group_id = request.args.get("id")
    registrations = Registration.query.filter_by(group_id=group_id).all()
    return render_template("status.html", registrations=registrations, group_id=group_id)

@app.route("/admin")
def admin():
    password = request.args.get("password")
    if password != "1234567890":
        return "Access Denied", 403
    registrations = Registration.query.order_by(Registration.timestamp.desc()).all()
    return render_template("admin.html", registrations=registrations)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
