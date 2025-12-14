from flask import Flask, request, jsonify
import joblib
import pandas as pd
from datetime import datetime

model = joblib.load("knn_model.pkl")
scaler = joblib.load("scaler.pkl")
label_encoder = joblib.load("labels.pkl")

FEATURES = ["power", "powerFactor", "energy"]

app = Flask(__name__)

@app.route("/predict", methods=["POST"])
def predict():
    data = request.json

    power = float(data["power"])
    powerFactor = float(data["powerFactor"])
    energy = float(data["energy"])

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ================================
    # IDLE DETECTION
    # ================================
    if power < 3 and powerFactor < 0.1:
        print(f"[{ts}] IDLE | No device connected")
        return jsonify({
            "device": "No device connected",
            "status": "idle"
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

    ANOMALY_THRESHOLD = 0.8

    if distance > ANOMALY_THRESHOLD:
        print(f"[{ts}] ⚠ ANOMALY | D={distance:.4f}")
        return jsonify({
            "device": "Anomaly detected",
            "distance": round(distance, 4),
            "status": "anomaly"
        })

    # ================================
    # NORMAL CLASSIFICATION
    # ================================
    pred = model.predict(X_scaled)[0]
    label = label_encoder.inverse_transform([pred])[0]
    confidence = model.predict_proba(X_scaled).max()

    print(f"[{ts}] NORMAL | {label} | D={distance:.4f}")

    return jsonify({
        "device": label,
        "confidence": round(confidence, 3),
        "distance": round(distance, 4),
        "status": "active"
    })


if __name__ == "__main__":
    print("ML Device Detector running on port 5000...")
    app.run(host="0.0.0.0", port=5000)
