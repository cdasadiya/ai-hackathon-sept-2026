import requests
import time

url = "https://hospital-blood-report-analyzer.onrender.com/logout/"

for _ in range(20):
    try:
        resp = requests.get(url, allow_redirects=False, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 302:
            print("Custom logout view is live! We are good to go.")
            break
    except Exception as e:
        print("Request failed:", e)
    
    print("Waiting 15 seconds...")
    time.sleep(15)
