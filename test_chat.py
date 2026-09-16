import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import urllib.request
import json

req = urllib.request.Request(
    'http://localhost:8000/chat',
    data=json.dumps({'message': 'Laptop for AI development under 80000', 'thread_id': 'test-session'}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

try:
    res = urllib.request.urlopen(req)
    data = json.loads(res.read().decode('utf-8'))
    print("Status:", res.status)
    print("Response text:", data.get("response")[:200])
    print("Products count:", len(data.get("products", [])))
    for p in data.get("products", []):
        print(f" - {p['name']} | {p['price']} | {p['match_score']}%")
except Exception as e:
    print("Error:", e)
