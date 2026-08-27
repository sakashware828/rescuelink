"""
RescueLink — Simulated Hardware Node Telemetry Transmitter
------------------------------------------------------------
Simulates an active IoT wearable node transmitting emergency alerts
and live GPS breadcrumbs to the RescueLink FastAPI backend.

Usage:
  py simulate_node.py
"""

import time
import json
import urllib.request
import urllib.error

# Backend API Endpoint
BASE_URL = "http://localhost:8000"
ALERT_URL = f"{BASE_URL}/api/alerts"
REGISTER_URL = f"{BASE_URL}/api/register"

DEVICE_ID = "ESP32_NODE_SIM"
PASSCODE = "1234"

def post_json(url: str, data: dict) -> dict:
    """Helper using standard library urllib to avoid third-party dependency issues."""
    json_bytes = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=json_bytes,
        headers={"Content-Type": "application/json", "User-Agent": "RescueLink-Simulator/1.0"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        resp_body = response.read().decode("utf-8")
        return json.loads(resp_body)


def ensure_registered_profile():
    """Register demo patient data for the simulated node so rich medical info appears on the dashboard."""
    profile_payload = {
        "device_id": DEVICE_ID,
        "passcode": PASSCODE,
        "name": "Vikram Malhotra",
        "age": 42,
        "blood_group": "B+",
        "emergency_contact": "+91 98200 12345",
        "govt_id_type": "Aadhaar",
        "govt_id_number": "XXXX-XXXX-8890",
        "medical_conditions": "Severe Penicillin Allergy, Mild Hypertension"
    }
    try:
        res = post_json(REGISTER_URL, profile_payload)
        print(f"[SETUP] Profile for node '{DEVICE_ID}' verified/saved: {res.get('message', 'OK')}")
    except Exception as e:
        print(f"[SETUP WARNING] Could not pre-register node profile: {e}")


def main():
    print("=" * 60)
    print(f"RescueLink IoT Node Simulator — Device ID: {DEVICE_ID}")
    print(f"Target Server: {BASE_URL}")
    print("=" * 60)

    # 1. Ensure profile exists in backend DB
    ensure_registered_profile()

    # Route coordinates simulating movement & incident (Mumbai area)
    route_coordinates = [
        {"lat": 19.0760, "lng": 72.8777, "type": "NORMAL_MONITORING", "speed": 12.5, "msg": "Normal transit telemetry"},
        {"lat": 19.0745, "lng": 72.8730, "type": "IRREGULAR_VITALS",  "speed": 8.0,  "msg": "Elevated heart rate spike detected"},
        {"lat": 19.0730, "lng": 72.8680, "type": "FALL_DETECTED",     "speed": 0.0,  "msg": "Sudden 3.8G impact deceleration detected"},
        {"lat": 19.0710, "lng": 72.8620, "type": "SOS_MANUAL",        "speed": 0.0,  "msg": "User manually triggered SOS button"},
    ]

    print(f"\nTransmitting {len(route_coordinates)} telemetry events (2s intervals)...\n")

    for i, pt in enumerate(route_coordinates, 1):
        alert_payload = {
            "device_id": DEVICE_ID,
            "trigger_type": pt["type"],
            "latitude": pt["lat"],
            "longitude": pt["lng"],
            "speed": pt["speed"],
            "battery": 88 - (i * 2),
            "message": pt["msg"]
        }

        try:
            resp = post_json(ALERT_URL, alert_payload)
            print(f"[{i}/{len(route_coordinates)}] Transmitted alert:")
            print(f"       Trigger: {pt['type']}")
            print(f"       Location: Lat {pt['lat']}, Lng {pt['lng']}")
            print(f"       Server Dispatch: {resp.get('status', 'OK')}\n")
        except urllib.error.URLError as e:
            print(f"[{i}/{len(route_coordinates)}] Error connecting to {ALERT_URL}: {e}")
            print("       Make sure the backend server is running (py -m uvicorn app.main:app --reload)\n")
        except Exception as e:
            print(f"[{i}/{len(route_coordinates)}] Failed: {e}\n")

        time.sleep(2)

    print("=" * 60)
    print("Simulation complete! Check your Responder Dashboard at http://localhost:8000/dashboard")
    print("=" * 60)

if __name__ == "__main__":
    main()