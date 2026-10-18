from flask import Flask, jsonify, request
import re
from flask_cors import CORS
import psycopg2

app = Flask(__name__)
CORS(app)  # allow the web app (different origin) to fetch from this API

DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "forestmonitering"
DB_USER = "postgres"
DB_PASSWORD = "Immani1335@"

def get_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                             user=DB_USER, password=DB_PASSWORD)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
def is_valid_email(email):
    return bool(EMAIL_PATTERN.match(email))

# ---------------------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------------------
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email", "")
    password = data.get("password", "")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, name, role, approved FROM users WHERE email=%s AND password=%s", (email, password))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"success": False, "message": "Invalid email or password"}), 401
    if not row[3]:
        return jsonify({"success": False, "message": "Your account is pending approval by an Administrator."}), 403

    return jsonify({"success": True, "user_id": row[0], "name": row[1], "role": row[2]})


# ---------------------------------------------------------------------------
# SELF-REGISTRATION (new user sign-up, requires Admin approval before login)
# ---------------------------------------------------------------------------
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not name or not email or not password:
        return jsonify({"success": False, "message": "Name, email, and password are required."}), 400
    if not is_valid_email(email):
        return jsonify({"success": False, "message": "Please enter a valid email address."}), 400
    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters."}), 400

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (name, email, password, role, approved) VALUES (%s,%s,%s,%s,%s)",
            (name, email, password, "User", False)
        )
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "A user with that email already exists."}), 400
    conn.close()
    return jsonify({"success": True, "message": "Account created. Waiting for Administrator approval."})

# ---------------------------------------------------------------------------
# LIVE DATA (available to both Admin and User)
# ---------------------------------------------------------------------------
@app.route("/api/latest")
def latest():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT n.node_id, n.location, n.latitude, n.longitude, n.status, r.temperature, r.humidity, r.co2_level, r.recorded_at
        FROM sensor_nodes n
        LEFT JOIN LATERAL (
            SELECT * FROM sensor_readings
            WHERE node_id = n.node_id
            ORDER BY recorded_at DESC LIMIT 1
        ) r ON true
        ORDER BY n.node_id;
    """)
    rows = cur.fetchall()
    conn.close()

    def format_coords(lat, lon):
        if lat is None or lon is None:
            return None
        lat_dir = "N" if lat >= 0 else "S"
        lon_dir = "E" if lon >= 0 else "W"
        return f"{abs(lat):.4f}° {lat_dir}, {abs(lon):.4f}° {lon_dir}"

    result = []
    for row in rows:
        coords = format_coords(row[2], row[3])
        result.append({
            "node_id": row[0],
            "location": coords if coords else row[1],
            "location_name": row[1],
            "latitude": row[2], "longitude": row[3],
            "status": row[4],
            "temperature": row[5], "humidity": row[6], "co2_level": row[7],
            "recorded_at": str(row[8]) if row[8] else None
        })
    return jsonify(result)

@app.route("/api/history/<int:node_id>")
def history(node_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT temperature, humidity, co2_level, recorded_at
        FROM sensor_readings WHERE node_id = %s
        ORDER BY recorded_at DESC LIMIT 20;
    """, (node_id,))
    rows = cur.fetchall()
    conn.close()
    rows.reverse()
    return jsonify([{
        "temperature": r[0], "humidity": r[1], "co2_level": r[2], "recorded_at": str(r[3])
    } for r in rows])

@app.route("/api/alerts")
def alerts():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.alert_type, a.message, a.status, a.created_at, n.location
        FROM alerts a JOIN sensor_nodes n ON a.node_id = n.node_id
        ORDER BY a.created_at DESC LIMIT 10;
    """)
    rows = cur.fetchall()
    conn.close()
    return jsonify([{
        "alert_type": r[0], "message": r[1], "status": r[2],
        "created_at": str(r[3]), "location": r[4]
    } for r in rows])

# ---------------------------------------------------------------------------
# ADMIN-ONLY: raw database table viewer
# (Front-end only calls these if logged-in role == "Admin")
# ---------------------------------------------------------------------------
ALLOWED_TABLES = ["users", "sensor_nodes", "sensor_readings", "alerts", "gateway"]

@app.route("/api/admin/table/<table_name>")
def admin_table(table_name):
    if table_name not in ALLOWED_TABLES:
        return jsonify({"error": "Table not allowed"}), 400

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table_name} ORDER BY 1 DESC LIMIT 100;")
    colnames = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    conn.close()

    return jsonify({
        "columns": colnames,
        "rows": [[str(v) if v is not None else None for v in row] for row in rows]
    })

# ---------------------------------------------------------------------------
# ADMIN-ONLY: resolve an alert
# ---------------------------------------------------------------------------
@app.route("/api/admin/alerts/<int:alert_id>/resolve", methods=["POST"])
def resolve_alert(alert_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE alerts SET status='resolved' WHERE alert_id=%s", (alert_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/alerts/full")
def alerts_full():
    """Includes alert_id and status, for Admin's resolve button."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.alert_id, a.alert_type, a.message, a.status, a.created_at, n.location
        FROM alerts a JOIN sensor_nodes n ON a.node_id = n.node_id
        ORDER BY a.created_at DESC LIMIT 10;
    """)
    rows = cur.fetchall()
    conn.close()
    return jsonify([{
        "alert_id": r[0], "alert_type": r[1], "message": r[2], "status": r[3],
        "created_at": str(r[4]), "location": r[5]
    } for r in rows])

# ---------------------------------------------------------------------------
# ADMIN-ONLY: user management (add / delete)
# ---------------------------------------------------------------------------
@app.route("/api/admin/users", methods=["GET"])
def list_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, name, email, role, created_at, approved FROM users ORDER BY approved ASC, user_id;")
    rows = cur.fetchall()
    conn.close()
    return jsonify([{
        "user_id": r[0], "name": r[1], "email": r[2], "role": r[3],
        "created_at": str(r[4]), "approved": r[5]
    } for r in rows])

@app.route("/api/admin/users/<int:user_id>/approve", methods=["POST"])
def approve_user(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET approved=true WHERE user_id=%s", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/admin/users", methods=["POST"])
def add_user():
    data = request.get_json()
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")
    role = data.get("role", "User")

    if not name or not email or not password:
        return jsonify({"success": False, "message": "Name, email, and password are required."}), 400
    if not is_valid_email(email):
        return jsonify({"success": False, "message": "Please enter a valid email address."}), 400
    if role not in ("Admin", "User"):
        return jsonify({"success": False, "message": "Role must be Admin or User."}), 400

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (name, email, password, role, approved) VALUES (%s,%s,%s,%s,true)",
            (name, email, password, role)
        )
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "A user with that email already exists."}), 400
    conn.close()
    return jsonify({"success": True})

@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT role FROM users WHERE user_id=%s", (user_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        return jsonify({"success": False, "message": "User not found."}), 404
    if row[0] == "Admin":
        conn.close()
        return jsonify({"success": False, "message": "Admin accounts cannot be deleted."}), 403

    cur.execute("DELETE FROM users WHERE user_id=%s", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
