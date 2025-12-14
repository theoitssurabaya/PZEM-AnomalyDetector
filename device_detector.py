from flask import Flask, request, jsonify
import joblib
import pandas as pd
from datetime import datetime
import paho.mqtt.client as mqtt

# ================================
# MQTT CONFIG (NC RELAY STANDARD)
# ================================
MQTT_BROKER = "192.168.200.150"
MQTT_PORT = 1883
RELAY_TOPIC = "relay/cut"

CMD_RELAY_ON  = "ON"    # NC relay → listrik menyala
CMD_RELAY_CUT = "CUT"   # NC relay → listrik mati

mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

# ================================
# LOAD ML COMPONENTS
# ================================
model = joblib.load("knn_model.pkl")
scaler = joblib.load("scaler.pkl")
label_encoder = joblib.load("labels.pkl")

FEATURES = ["power", "powerFactor", "energy"]

# ================================
# STATE VARIABLES (CRITICAL)
# ================================
anomaly_counter = 0
relay_latched = False   # TRUE = relay sudah CUT & terkunci

ANOMALY_THRESHOLD = 0.8
ANOMALY_CONFIRMATION = 2

# ================================
# FLASK APP
# ================================
app = Flask(__name__)

@app.route("/predict", methods=["POST"])
def predict():
    global anomaly_counter, relay_latched

    data = request.json
    power = float(data["power"])
    powerFactor = float(data["powerFactor"])
    energy = float(data["energy"])

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # =====================================================
    # FAIL-SAFE: RELAY SUDAH LATCHED → ABAIKAN SEMUA INPUT
    # =====================================================
    if relay_latched:
        print(f"[{ts}] RELAY LATCHED | Ignoring input until manual reset")

        return jsonify({
            "status": "latched",
            "relay": "cut",
            "note": "manual reset required"
        })

    # ================================
    # IDLE DETECTION (NON-RESET)
    # ================================
    if power < 3 and powerFactor < 0.1:
        anomaly_counter = 0

        mqtt_client.publish(RELAY_TOPIC, CMD_RELAY_ON)
        print(f"[{ts}] IDLE | No device connected | RELAY ON")

        return jsonify({
            "device": "No device connected",
            "status": "idle",
            "relay": "on"
        })

    # ================================
    # FEATURE VECTOR
    # ================================
    X = pd.DataFrame([{
        "power": power,
        "powerFactor": powerFactor,
        "energy": energy
    }], columns=FEATURES)

    X_scaled = scaler.transform(X)

    # ================================
    # ANOMALY DETECTION
    # ================================
    distances, _ = model.kneighbors(X_scaled, n_neighbors=2)
    distance = float(distances[0][1])

    if distance > ANOMALY_THRESHOLD:
        anomaly_counter += 1

        print(f"[{ts}] ANOMALY {anomaly_counter}/{ANOMALY_CONFIRMATION} | D={distance:.4f}")

        if anomaly_counter >= ANOMALY_CONFIRMATION:
            relay_latched = True
            mqtt_client.publish(RELAY_TOPIC, CMD_RELAY_CUT)

            print(f"[{ts}] ANOMALY CONFIRMED | RELAY CUT & LATCHED")

            return jsonify({
                "status": "anomaly",
                "distance": round(distance, 4),
                "relay": "cut",
                "latched": True
            })

        return jsonify({
            "status": "anomaly_pending",
            "count": anomaly_counter,
            "distance": round(distance, 4)
        })

    # ================================
    # NORMAL CONDITION
    # ================================
    anomaly_counter = 0

    pred = model.predict(X_scaled)[0]
    label = label_encoder.inverse_transform([pred])[0]
    confidence = model.predict_proba(X_scaled).max()

    mqtt_client.publish(RELAY_TOPIC, CMD_RELAY_ON)

    print(f"[{ts}] NORMAL | {label} | D={distance:.4f}")

    return jsonify({
        "device": label,
        "confidence": round(confidence, 3),
        "distance": round(distance, 4),
        "status": "active",
        "relay": "on"
    })


# ================================
# OPTIONAL: MANUAL RESET ENDPOINT
# ================================
@app.route("/reset", methods=["POST"])
def reset():
    global anomaly_counter, relay_latched

    anomaly_counter = 0
    relay_latched = False
    mqtt_client.publish(RELAY_TOPIC, CMD_RELAY_ON)

    print("MANUAL RESET | RELAY ON")

    return jsonify({
        "status": "reset",
        "relay": "on"
    })


if __name__ == "__main__":
    print("ML Device Detector (NC Relay + HARD LATCH SAFETY) running on port 5000...")
    app.run(host="0.0.0.0", port=5000)