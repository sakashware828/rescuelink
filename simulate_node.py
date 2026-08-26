import json
import time
import paho.mqtt.client as mqtt

MQTT_HOST = "mosquitto"
MQTT_PORT = 1883
MQTT_TOPIC = "rescuelink/alerts"

route_coordinates = [
    (19.0760, 72.8777),
    (19.0745, 72.8730),
    (19.0730, 72.8680),
    (19.0710, 72.8620),
    (19.0680, 72.8550),
    (19.0640, 72.8470),
    (19.0600, 72.8400),
]

client = mqtt.Client()

try:
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    print("Connected to Mosquitto Broker! Starting live telemetry stream...")

    for i, (lat, lng) in enumerate(route_coordinates):
        payload = {
            "device_id": "ESP32_NODE_SIM",
            "latitude": lat,
            "longitude": lng,
            "sos_triggered": True,
            "fall_detected": (i >= 3),
            "victim_name": "Alex Mercer",
            "blood_group": "B+",
            "critical_allergies": "Penicillin",
        }
        client.publish(MQTT_TOPIC, json.dumps(payload))
        print(f"[{i+1}/{len(route_coordinates)}] Pinging location: {lat}, {lng}")
        time.sleep(2)

    print("Stream complete!")

except Exception as e:
    print(f"Error connecting to MQTT Broker: {e}")