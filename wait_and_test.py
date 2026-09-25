import requests
import time
import re

url = "https://ai-hackathon-sept-2026.onrender.com/register/"
session = requests.Session()

def test():
    resp = session.get(url)
    csrf_token = resp.cookies.get('csrftoken')
    inputs = re.findall(r'<input[^>]*name="([^"]+)"', resp.text)
    data = {
        "csrfmiddlewaretoken": csrf_token,
        "username": "test_wait_user1",
        "email": "test_wait_user1@test.com",
        "role": "Patient"
    }
    for inp in inputs:
        if "password" in inp.lower() or "pass" in inp.lower():
            data[inp] = "TestPass@123!"
            
    post_resp = session.post(url, data=data, headers={"Referer": url})
    return post_resp

for _ in range(20):
    res = test()
    if res.status_code == 200 and "Traceback" in res.text:
        print("Got Traceback from our try-except:")
        print(res.text[:2000])
        break
    elif res.status_code == 302 or (res.status_code == 200 and "Dashboard" in res.text):
        print("Success! Registration worked.")
        print("URL:", res.url)
        break
    else:
        print(f"Status {res.status_code}, wait 15s...")
        time.sleep(15)

