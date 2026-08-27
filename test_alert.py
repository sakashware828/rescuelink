"""
RescueLink — Instant Test Alert Dispatcher
--------------------------------------------
Sends a high-priority emergency test alert directly to the backend
over HTTP (or MQTT if configured) to test dashboard and responder notifications.

Usage:
  py test_alert.py
"""

import json
import urllib.request
import urllib.error

API_URL = "http://localhost:8000/api/alerts"

alert_payload = {
    "device_id": "001",
    "trigger_type": "SOS_MANUAL",
    "latitude": 19.0760,
    "longitude": 72.8777,
    "speed": 0.0,
    "battery": 82,
    "message": "Manual emergency SOS panic button pressed by user."
}

def main():
    print(f"Sending emergency test alert to {API_URL}...")
    
    try:
        data_bytes = json.dumps(alert_payload).encode("utf-8")
        req = urllib.request.Request(
            API_URL,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
            print("\n[SUCCESS] Emergency alert successfully dispatched!")
            print(json.dumps(result, indent=2))
            print("\nCheck live updates on Dashboard at: http://localhost:8000/dashboard")
    except urllib.error.URLError as e:
        print(f"\n[ERROR] Could not connect to {API_URL}: {e}")
        print("Please ensure your FastAPI backend is running with:")
        print("  py -m uvicorn app.main:app --reload")

if __name__ == "__main__":
    main()