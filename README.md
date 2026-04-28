# PZEM-Based Electrical Device Identification and Anomaly Detection System

## Abstract
This project presents an electrical device identification and anomaly detection system based on power consumption characteristics measured using a PZEM-004T power monitoring module. The system integrates an ESP32 microcontroller, Node-RED for data orchestration, and a machine learning backend implemented in Python using the K-Nearest Neighbors (KNN) algorithm. Real-time power data are classified to identify connected electrical devices and to detect anomalous consumption patterns that do not conform to previously learned device profiles.

---

## System Architecture
The overall system architecture consists of four primary components:

1. **Data Acquisition Layer**
   - ESP32 microcontroller
   - PZEM-004T power monitoring module
   - Measured parameters: power (W), power factor, and energy (kWh)

2. **Data Orchestration Layer**
   - Node-RED (as MQTT)
   - Prometheus
   - Grafana for visualization
   - Real-time data preprocessing and routing

3. **Machine Learning Layer**
   - Python-based KNN classification model
   - Feature scaling using StandardScaler
   - Supervised learning for device identification
   - Distance-based anomaly detection

4. **Application Layer**
   - Flask REST API
   - Real-time inference endpoint
   - JSON-based communication with Node-RED

---

## Wiring Diagram
| Component | GPIO Pin | Description |
| :--- | :--- | :--- |
| **Relay Module** | GPIO 18 | Power cut-off control (Anomaly detection) |
| **PZEM-004T TX** | GPIO 16 (RX2) | Serial data reception from sensor |
| **PZEM-004T RX** | GPIO 17 (TX2) | Serial data transmission to sensor |
| **Power Supply** | 5V / 3.3V | ESP32 and Relay power source |

---

## Features
- Electrical device classification based on power usage patterns
- Detection of idle (no device connected) states
- Distance-based anomaly detection for unknown or abnormal devices
- Real-time inference via REST API
- Modular design suitable for IoT and embedded monitoring systems

---

## Dataset Description
The training dataset consists of time-series measurements collected from a PZEM-004T sensor for multiple electrical devices, including but not limited to:
- Mobile phone chargers
- Laptop chargers

### Selected Features
The following features are used for model training and inference:
- `power` (W)
- `powerFactor`
- `energy` (kWh)

Each data sample is labeled according to the connected device type.

---

## Machine Learning Methodology

### Classification Algorithm
The system employs the **K-Nearest Neighbors (KNN)** algorithm due to its simplicity, interpretability, and effectiveness for low-dimensional, well-clustered sensor data.

- Distance metric: Euclidean
- Neighbor weighting: Distance-based
- Feature normalization: StandardScaler
- Number of neighbors: Tuned empirically

### Anomaly Detection
Anomaly detection is implemented using the distance between an incoming sample and its nearest neighbors in the feature space. Samples exceeding a predefined distance threshold—derived from the statistical distribution of training data distances—are classified as anomalies.

---

## API Specification

### Endpoint
`POST /predict`

### Request Payload (JSON)
```json
{
  "power": 65.3,
  "powerFactor": 0.92,
  "energy": 0.0125
}
