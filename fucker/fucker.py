import os
import time
import random
import requests


TARGET = os.environ.get("TARGET", "http://web:5000")
MYNAME = os.environ.get("NAME", "UNKown")
time.sleep(3)  # Wait for server to boot

while True:
    try:
        print(f"Sending '{MYNAME=}' to {TARGET}")
        requests.post(TARGET, data={"word": MYNAME})
    except Exception as e:
        print(f"Client failed: {e}")
    finally:
        dither = 4 + (4 * random.random())
        time.sleep(dither)