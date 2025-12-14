from flask import Flask, request, jsonify
import joblib
import pandas as pd
from datetime import datetime
import paho.mqtt.client as mqtt

# ================================
# MQTT CONFIG (NC RELAY STANDARD)
# ================================
MQTT_BROKER = "ip address" #Broker Ip Address
MQTT_PORT = 0000           # Broker's Port
RELAY_TOPIC = "your_topic" # Input your Node-Red in topic

CMD_RELAY_ON = "ON"     
CMD_RELAY_CUT = "CUT"  

mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

# ================================
# LOAD ML COMPONENTS
# ================================
model = joblib.load("models/knn_model.pkl")
scaler = joblib.load("models/scaler.pkl")
label_encoder = joblib.load("models/labels.pkl")

FEATURES = ["power", "powerFactor", "energy"]

# ================================
# FLASK APP
# ================================
app = Flask(__name__)

@app.route("/predict", methods=["POST"])
def predict():
    data = request.json

    power = float(data["power"])
    powerFactor = float(data["powerFactor"])
    energy = float(data["energy"])

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ================================
    # IDLE DETECTION (FAIL-SAFE)
    # ================================
    if power < 3 and powerFactor < 0.1:
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

    ANOMALY_THRESHOLD = 0.8 # based on your training phase

    if distance > ANOMALY_THRESHOLD:
        mqtt_client.publish(RELAY_TOPIC, CMD_RELAY_CUT)

        print(f"[{ts}] ⚠ ANOMALY | D={distance:.4f} | RELAY CUT")

        return jsonify({
            "device": "Anomaly detected",
            "distance": round(distance, 4),
            "status": "anomaly",
            "action": "relay_cut"
        })

    # ================================
    # NORMAL CLASSIFICATION
    # ================================
    pred = model.predict(X_scaled)[0]
    label = label_encoder.inverse_transform([pred])[0]
    confidence = model.predict_proba(X_scaled).max()

    mqtt_client.publish(RELAY_TOPIC, CMD_RELAY_ON)

    print(f"[{ts}] NORMAL | {label} | D={distance:.4f} | RELAY ON")

    return jsonify({
        "device": label,
        "confidence": round(confidence, 3),
        "distance": round(distance, 4),
        "status": "active",
        "relay": "on"
    })


if __name__ == "__main__":
    print("ML Device Detector (NC Relay Mode) running on port 5000...")
    app.run(host="0.0.0.0", port=5000)
