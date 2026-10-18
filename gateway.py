import serial
import psycopg2
import time

# ---- Database connection ----
DB_HOST = "10.118.183.135"
DB_PORT = "5432"
DB_NAME = "forestmonitering"
DB_USER = "postgres"
DB_PASSWORD = "Immani1335@"

SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 9600

conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                         user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)

def check_and_create_alert(node_id, temperature, co2_level):
    if temperature is not None and temperature >= 45:
        cur.execute(
            "INSERT INTO alerts (node_id, alert_type, message, status) VALUES (%s,%s,%s,%s)",
            (node_id, "Fire Risk", f"High temperature detected: {temperature} C", "pending")
        )
    elif temperature is not None and temperature >= 38:
        cur.execute(
            "INSERT INTO alerts (node_id, alert_type, message, status) VALUES (%s,%s,%s,%s)",
            (node_id, "High Temperature", f"Temperature elevated: {temperature} C", "pending")
        )
    if co2_level is not None and co2_level >= 1000:
        cur.execute(
            "INSERT INTO alerts (node_id, alert_type, message, status) VALUES (%s,%s,%s,%s)",
            (node_id, "Smoke/Air Quality", f"High CO2 level: {co2_level} ppm", "pending")
        )

def parse_single(part):
    fields = part.strip().split(",")
    node_num = int(fields[0].replace("N", ""))
    temp = float(fields[1])
    hum = float(fields[2])
    co2 = float(fields[3])
    return node_num, temp, hum, co2

def insert_reading(node_num, temp, hum, co2):
    cur.execute(
        "INSERT INTO sensor_readings (node_id, temperature, humidity, co2_level) VALUES (%s,%s,%s,%s)",
        (node_num, temp, hum, co2)
    )
    check_and_create_alert(node_num, temp, co2)
    conn.commit()
    print(f"Inserted -> Node{node_num}: temp={temp}, hum={hum}, co2={co2}")

print("Gateway script started. Listening on", SERIAL_PORT)

while True:
    line = ser.readline().decode("utf-8", errors="ignore").strip()
    if not line:
        continue
    try:
        if "|" in line:
            n1_part, n2_part = line.split("|")
            insert_reading(*parse_single(n1_part))
            insert_reading(*parse_single(n2_part))
        elif line.startswith("N1,") or line.startswith("N2,"):
            insert_reading(*parse_single(line))
        else:
            print("Ignored line:", line)
    except Exception as e:
        print("Parse error:", e, "| line:", line)