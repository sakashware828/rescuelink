import json
import time
import paho.mqtt.client as mqtt

# Configuration
MQTT_HOST = "localhost"  # Change to "127.0.0.1" if needed
MQTT_PORT = 1883
MQTT_TOPIC = "rescuelink/alerts"

# Sample emergency alert payload matching your route coordinates
alert_payload = {
    "device_id": "001",
    "status": "EMERGENCY",
    "latitude": 19.0760,
    "longitude": 72.8777,
    "speed": 0,
    "battery": 85,
    "message": "Manual SOS trigger test"
}

# Connect and publish
client = mqtt.Client()

try:
    print(f"Connecting to MQTT broker at {MQTT_HOST}:{MQTT_PORT}...")
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    
    # Publish payload
    json_data = json.dumps(alert_payload)
    client.publish(MQTT_TOPIC, json_data)
    print(f"Success! Test alert sent to topic '{MQTT_TOPIC}':")
    print(json_data)
    
    client.disconnect()
except Exception as e:
    print(f"Failed to connect or send alert: {e}")