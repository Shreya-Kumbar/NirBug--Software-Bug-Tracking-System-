"""Takes screenshots of the running NirBug app with headless Microsoft Edge.

1. Start the app:          python -m bugtracker.app
2. In another terminal:    python docs/take_screenshots.py
   -> docs/screenshots/*.png
"""
import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

import websocket  # pip install websocket-client

URL = os.environ.get("NIRBUG_URL", "http://127.0.0.1:5000")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
W, H = 1440, 900
os.makedirs(OUT, exist_ok=True)


# Local requests must never go through a system/college proxy
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def check_app_running():
    try:
        DIRECT.open(URL + "/api/health", timeout=5)
    except Exception:
        sys.exit(f"NirBug is not running at {URL}.\nStart it first in another terminal:  python -m bugtracker.app")


class Browser:
    def __init__(self):
        if not os.path.exists(EDGE):
            sys.exit(f"Microsoft Edge not found at {EDGE}")
        port = free_port()   # a fresh free port every run (avoids clashes with an old Edge)
        self.proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={port}", f"--window-size={W},{H}",
                                      "--hide-scrollbars", "--no-first-run", "--no-default-browser-check", "--proxy-bypass-list=127.0.0.1;localhost;<-loopback>",
                                      f"--user-data-dir={tempfile.mkdtemp()}", "about:blank"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws = None
        for _ in range(150):   # wait up to ~30 s for Edge to start
            try:
                tabs = json.load(DIRECT.open(f"http://127.0.0.1:{port}/json", timeout=2))
                ws = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        if not ws:
            self.proc.kill()
            sys.exit("Headless Edge did not start in 30 s. Close any stuck 'msedge' processes in Task Manager and try again.")
        self.ws = websocket.create_connection(ws, suppress_origin=True, http_no_proxy=["127.0.0.1", "localhost"])
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

    def styled(self) -> bool:
        """True when Tailwind, Chart.js and the icons (loaded from CDNs) are all available."""
        r = self.js("!!(window.tailwind && window.Chart && window.lucide)")
        return bool(r.get("result", {}).get("value"))

    def shot(self, name, wait=1.5):
        time.sleep(wait)
        for _ in range(20):
            if self.styled():
                break
            time.sleep(0.5)
        else:
            self.close()
            sys.exit("The page loaded WITHOUT its styles (Tailwind / Chart.js / icons come from the internet).\n"
                     "Check your internet connection, then run the script again. No broken screenshot was saved.")
        data = self.cmd("Page.captureScreenshot", format="png")["data"]
        with open(os.path.join(OUT, name), "wb") as f:
            f.write(base64.b64decode(data))
        print("saved", name)

    def close(self):
        self.ws.close()
        self.proc.kill()


def main():
    check_app_running()
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

    # role workspaces: (user, page, file)
    for user, page, name in [("dev_alice", "work", "09_developer_my_work.png"), ("tester", "qa", "10_tester_qa_queue.png"),
                             ("manager", "triage", "11_manager_triage.png"), ("reporter", "reports", "12_reporter_my_reports.png"),
                             ("admin", "team", "13_admin_users_roles.png")]:
        b.js(f"""fetch('/api/auth/login',{{method:'POST',headers:{{'Content-Type':'application/json'}},
                body:JSON.stringify({{username:'{user}',password:'Demo@1234'}})}}).then(r=>r.json())
                .then(r=>{{sessionStorage.setItem('token',r.token); location.hash='{page}'; location.reload();}})""")
        b.shot(name, 4)
    b.close()


if __name__ == "__main__":
    main()
