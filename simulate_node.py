"""
RescueLink — Simulated Device (HTTP version)
------------------------------------------------
Replaces the MQTT-based simulate_node.py, which required a Mosquitto broker
that isn't actually deployed anywhere in this project. This version posts
straight to your running FastAPI backend over HTTP instead — no Docker,
no broker, one less thing to break during your demo today.

Install: pip install requests --break-system-packages
Run (with your backend already running locally): python simulate_node.py
"""

import requests
import time

API_URL = "http://localhost:8000/api/alerts"  # change if testing against Render

route_coordinates = [
    (19.0760, 72.8777),
    (19.0745, 72.8730),
    (19.0730, 72.8680),
    (19.0710, 72.8620),
]

device_id = "ESP32_NODE_SIM"  # must match a device_id you registered via /api/register

for i, (lat, lng) in enumerate(route_coordinates):
    payload = {
        "device_id": device_id,
        "trigger_type": "auto_fall" if i >= 2 else "manual",
        "latitude": lat,
        "longitude": lng,
    }
    try:
        res = requests.post(API_URL, json=payload, timeout=5)
        print(f"[{i+1}/{len(route_coordinates)}] Sent alert at {lat},{lng} — status {res.status_code}")
    except Exception as e:
        print(f"Failed to send alert: {e}")
    time.sleep(2)

print("Simulation complete.")