#include <Arduino.h>
#include <PZEM004Tv30.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <HTTPClient.h>

// ================= HARDWARE CONFIG =================
#define RXD2 16
#define TXD2 17
#define RELAY_PIN 18

// RELAY LOGIC (Normally Closed, Active-LOW)
#define RELAY_ON_LEVEL   LOW    // POWER CONNECTED
#define RELAY_CUT_LEVEL  HIGH   // POWER CUT

HardwareSerial PZEMSerial(2);
PZEM004Tv30 pzem(&PZEMSerial, RXD2, TXD2);

// ================= WIFI CONFIG =================
const char* ssid     = "b401_wifi";
const char* password = "b401juara1";

// ================= MQTT CONFIG =================
const char* mqtt_server    = "192.168.200.150";
const uint16_t mqtt_port   = 1883;
const char* mqtt_client_id = "ESP32-PZEM-01";

// Publish topics
const char* topic_voltage   = "pzem/voltage";
const char* topic_current   = "pzem/current";
const char* topic_power     = "pzem/power";
const char* topic_energy    = "pzem/energy";
const char* topic_frequency = "pzem/frequency";
const char* topic_pf        = "pzem/pf";

// Subscribe topic (ML → ESP32)
const char* topic_relay_cmd = "relay/cut";

// ================= PYTHON SERVER CONFIG =================
const char* python_server = "http://192.168.200.150:5000/reset";

// ================= GLOBAL OBJECTS =================
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

// ================= GLOBAL DATA =================
float voltage = 0.0;
float current = 0.0;
float power = 0.0;
float energy = 0.0;
float frequency = 0.0;
float pf = 0.0;

SemaphoreHandle_t dataMutex;

unsigned long lastMsg = 0;
const long interval = 2000;

bool relayCut = false;

// ================= WIFI =================
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.printf("Connecting to WiFi '%s'...\n", ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }

  Serial.printf("\nWiFi connected. IP: %s\n",
                WiFi.localIP().toString().c_str());
}

// ================= RESET PYTHON SERVER =================
void resetPythonServer() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected. Cannot reset Python server.");
    return;
  }

  HTTPClient http;
  http.begin(python_server);
  http.addHeader("Content-Type", "application/json");
  
  Serial.println("\nSending RESET command to Python server...");
  
  int httpResponseCode = http.POST("{}");
  
  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.printf("Python server reset SUCCESS! Response code: %d\n", httpResponseCode);
    Serial.printf("Response: %s\n", response.c_str());
  } else {
    Serial.printf("Python server reset FAILED! Error code: %d\n", httpResponseCode);
    Serial.printf("Error: %s\n", http.errorToString(httpResponseCode).c_str());
  }
  
  http.end();
}

// ================= MQTT CALLBACK =================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  // Pastikan payload null-terminated
  payload[length] = '\0';
  String msg = String((char*)payload);
  Serial.printf("\n[MQTT RX] Topic: %s, Message: %s\n", topic, msg.c_str());

  if (String(topic) == topic_relay_cmd) {

    if (msg == "CUT") {
      relayCut = true;
      digitalWrite(RELAY_PIN, RELAY_CUT_LEVEL);
      // DEBUG ANOMALI
      Serial.println("ANOMALY DETECTED: RELAY CUT POWER");
    }
    else if (msg == "ON") {
      relayCut = false;
      digitalWrite(RELAY_PIN, RELAY_ON_LEVEL);
      // DEBUG NORMAL
      Serial.println("RELAY ON: POWER RESTORED (NORMAL)");
    }
  }
}

// ================= MQTT MAINTAIN =================
void mqttMaintain() {
  if (!mqttClient.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (mqttClient.connect(mqtt_client_id)) {
      mqttClient.subscribe(topic_relay_cmd);
      Serial.println("MQTT connected & subscribed to relay commands.");
    } else {
      Serial.printf("failed, rc=%d. Retrying in 5 seconds...\n", mqttClient.state());
      delay(5000);
    }
  }
  mqttClient.loop();
}

// ================= TASK: READ PZEM =================
void Task_ReadPZEM(void* pvParameters) {
  for (;;) {
    float v = pzem.voltage();
    float c = pzem.current();
    float p = pzem.power();
    float e = pzem.energy();
    float f = pzem.frequency();
    float pf_local = pzem.pf();

    if (xSemaphoreTake(dataMutex, pdMS_TO_TICKS(50))) {
      // Hanya update jika pembacaan valid (bukan NaN)
      if (!isnan(v)) voltage = v;
      if (!isnan(c)) current = c;
      if (!isnan(p)) power = p;
      if (!isnan(e)) energy = e;
      if (!isnan(f)) frequency = f;
      if (!isnan(pf_local)) pf = pf_local;
      xSemaphoreGive(dataMutex);
    }

    // DEBUG PZEM Reading Status
    if (isnan(v) || isnan(c) || isnan(p)) {
        Serial.println("[PZEM] WARNING: PZEM reading failed (NaN).");
    }
    
    vTaskDelay(pdMS_TO_TICKS(1000)); // Baca setiap 1 detik
  }
}

// ================= TASK: MQTT PUBLISH =================
void Task_MQTTPublish(void* pvParameters) {
  mqttClient.setServer(mqtt_server, mqtt_port);
  mqttClient.setCallback(mqttCallback);

  for (;;) {
    connectWiFi();
    mqttMaintain();

    if (millis() - lastMsg > interval) {
      lastMsg = millis();

      float v, c, p, e, f, pf_local;
      char payload[16];

      // Ambil data PZEM dengan Mutex
      if (xSemaphoreTake(dataMutex, pdMS_TO_TICKS(50))) {
        v = voltage;
        c = current;
        p = power;
        e = energy;
        f = frequency;
        pf_local = pf;
        xSemaphoreGive(dataMutex);
      }

      // DEBUG PUBLISH
      Serial.println("--- MQTT PUBLISH ---");
      
      // Voltage
      dtostrf(v, 4, 2, payload);
      mqttClient.publish(topic_voltage, payload);
      Serial.printf("VOLTAGE (%s): %s V\n", topic_voltage, payload);

      // Current
      dtostrf(c, 4, 3, payload);
      mqttClient.publish(topic_current, payload);
      Serial.printf("CURRENT (%s): %s A\n", topic_current, payload);

      // Power
      dtostrf(p, 4, 2, payload);
      mqttClient.publish(topic_power, payload);
      Serial.printf("POWER (%s): %s W\n", topic_power, payload);

      // Energy
      dtostrf(e, 4, 3, payload);
      mqttClient.publish(topic_energy, payload);
      Serial.printf("ENERGY (%s): %s kWh\n", topic_energy, payload);

      // Frequency
      dtostrf(f, 4, 2, payload);
      mqttClient.publish(topic_frequency, payload);
      Serial.printf("FREQUENCY (%s): %s Hz\n", topic_frequency, payload);

      // Power Factor
      dtostrf(pf_local, 4, 2, payload);
      mqttClient.publish(topic_pf, payload);
      Serial.printf("PF (%s): %s\n", topic_pf, payload);
      
      // RELAY STATUS DEBUG
      Serial.printf("[RELAY] Current State: %s\n", relayCut ? "CUT (Anomaly)" : "ON (Normal)");
    }

    vTaskDelay(pdMS_TO_TICKS(100));
  }
}

// ================= SETUP =================
void setup() {
  Serial.begin(115200);
  delay(1000); // Tunggu serial siap

  Serial.println("║  ESP32 PZEM ANOMALY CONTROL WITH AUTO-RESET  ║");
  Serial.printf("MQTT Server: %s\n", mqtt_server);
  Serial.printf("Relay Command Topic: %s\n", topic_relay_cmd);
  Serial.printf("Python Server: %s\n", python_server);

  // FAIL-SAFE RELAY SETUP (NC)
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, RELAY_ON_LEVEL);  // POWER ON by default
  Serial.printf("Relay Pin %d initialized to POWER ON (Level: %s)\n", 
                RELAY_PIN, RELAY_ON_LEVEL == LOW ? "LOW" : "HIGH");

  connectWiFi();
  
  //RESET PYTHON SERVER SAAT ESP32 STARTUP/RESET
  Serial.println("ESP32 RESET DETECTED - UNLOCKING PYTHON SERVER");
  resetPythonServer();
  delay(1000);  // Beri waktu untuk proses reset

  PZEMSerial.begin(9600, SERIAL_8N1, RXD2, TXD2);
  Serial.printf("PZEM on Serial 2 (RX:%d, TX:%d) initialized.\n", RXD2, TXD2);

  dataMutex = xSemaphoreCreateMutex();
  Serial.println("FreeRTOS Mutex created.");

  xTaskCreatePinnedToCore(Task_ReadPZEM, "ReadPZEM", 4096, NULL, 2, NULL, 1);
  xTaskCreatePinnedToCore(Task_MQTTPublish, "MQTTPub", 4096, NULL, 1, NULL, 0);
  Serial.println("FreeRTOS Tasks created.");
  Serial.println("\nSYSTEM READY - Monitoring started...\n");
}

// ================= LOOP =================
void loop() {
  vTaskDelay(pdMS_TO_TICKS(10));
}