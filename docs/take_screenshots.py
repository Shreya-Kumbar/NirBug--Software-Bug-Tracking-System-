"""Takes screenshots of the running NirBug app with headless Microsoft Edge.

1. Start the app:          python -m bugtracker.app
2. In another terminal:    python docs/take_screenshots.py
   -> docs/screenshots/*.png
"""
import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.request

import websocket  # pip install websocket-client

URL = "http://127.0.0.1:5000"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
W, H = 1440, 900
os.makedirs(OUT, exist_ok=True)


class Browser:
    def __init__(self):
        self.proc = subprocess.Popen([EDGE, "--headless=new", "--remote-debugging-port=9333", f"--window-size={W},{H}",
                                      "--hide-scrollbars", f"--user-data-dir={tempfile.mkdtemp()}", "about:blank"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json"))
                ws = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        self.ws = websocket.create_connection(ws, suppress_origin=True)
        self.i = 0
        self.cmd("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1.5, mobile=False)

    def cmd(self, method, **params):
        self.i += 1
        self.ws.send(json.dumps({"id": self.i, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.i:
                return msg.get("result", {})

    def js(self, expr):
        return self.cmd("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)

    def go(self, url, wait=2.5):
        self.cmd("Page.navigate", url=url)
        time.sleep(wait)

    def shot(self, name, wait=1.5):
        time.sleep(wait)
        data = self.cmd("Page.captureScreenshot", format="png")["data"]
        with open(os.path.join(OUT, name), "wb") as f:
            f.write(base64.b64decode(data))
        print("saved", name)

    def close(self):
        self.ws.close()
        self.proc.kill()


def main():
    b = Browser()
    b.go(URL)
    b.js("localStorage.setItem('theme','dark'); sessionStorage.clear(); location.reload()")
    b.shot("01_login.png", 3)

    b.js("""fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({username:'manager',password:'Demo@1234'})}).then(r=>r.json())
            .then(r=>{sessionStorage.setItem('token',r.token); location.hash='dashboard'; location.reload();})""")
    b.shot("02_dashboard.png", 4)

    b.js("location.hash='bugs'")
    b.shot("03_bug_list.png", 3)
    b.js("location.hash='board'")
    b.shot("04_board.png", 3)

    b.js("location.hash='dashboard'")
    time.sleep(2)
    b.js("""openNewBug(); const f=document.querySelector('#bug-form');
            f.title.value='Session expires too quickly, users logged out';
            f.description.value='Users get logged out after a minute of inactivity and lose their work.';
            f.title.dispatchEvent(new Event('input'))""")
    b.shot("05_report_bug_ai.png", 3)

    b.js("closeModal(); openBug(3)")
    b.shot("06_bug_detail.png", 3)

    b.js("closeModal(); location.hash='releases'")
    b.shot("07_releases.png", 3)

    b.js("localStorage.setItem('theme','light'); location.hash='dashboard'; location.reload()")
    b.shot("08_dashboard_light.png", 4)
    b.js("localStorage.setItem('theme','dark')")
    b.close()


if __name__ == "__main__":
    main()
