"""
Benchmark: generate_field_layout for a 100 x 200 m field.
Run with: python test_large_field.py
The Flask server must be running on port 5000.
"""
import json
import time
import urllib.request

ENDPOINT = "http://localhost:5000/generate_field_layout"

PAYLOAD = {
    # All 40 plants used in the small-field smoke test
    "selected_plant_ids": [
        104, 107, 1, 4, 5, 6, 7, 8, 9, 10,
        11, 12, 13, 14, 15, 16, 18, 21, 20, 26,
        28, 2, 24, 27, 32, 31, 29, 25, 17, 3,
        19, 22, 23, 30, 33, 34, 35, 36, 106,
    ],
    "field_length": 200,   # east–west metres
    "field_width":  100,   # north–south metres
    "pv_production":  10,
    "battery_size":    5,
    "system_height":   3,
    "latitude":       32,
}

body = json.dumps(PAYLOAD).encode()
req  = urllib.request.Request(
    ENDPOINT,
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)

print(f"POST {ENDPOINT}  (field {PAYLOAD['field_length']}×{PAYLOAD['field_width']} m) …")
t0 = time.perf_counter()
with urllib.request.urlopen(req, timeout=300) as resp:
    raw = resp.read()
t1 = time.perf_counter()

data = json.loads(raw)
n_features = len(data.get("features", []))
n_plants   = sum(1 for f in data.get("features", [])
                 if f["properties"].get("type") == "plant_instance")
print(f"Response: {len(raw)//1024} KB  {n_features} features  {n_plants} plant instances")
print(f"Total wall-clock time: {t1-t0:.2f}s")
