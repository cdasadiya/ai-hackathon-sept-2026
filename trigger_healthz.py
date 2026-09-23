import requests
import time

url = "https://hospital-blood-report-analyzer.onrender.com/healthz/"

for _ in range(20):
    try:
        resp = requests.get(url, timeout=10)
        print(f"Status: {resp.status_code}, Body: {resp.text[:500]}")
        if resp.status_code == 200 and "Migrations applied successfully" in resp.text:
            print("Migrations applied! We are good to go.")
            break
    except Exception as e:
        print("Request failed:", e)
    
    print("Waiting 15 seconds...")
    time.sleep(15)
