import sys
import os
import json
import subprocess
import http.server
import socketserver
import psutil

PORT = 8000
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(PROJECT_ROOT, "web")
PY_EXE = r"C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe"
if not os.path.exists(PY_EXE):
    PY_EXE = sys.executable


class CustomHandler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_HEAD(self):
        if self.path in ("/api/launch", "/api/launch/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            return
        super().do_HEAD()

    def do_GET(self):
        if self.path in ("/api/launch", "/api/launch/"):
            self._handle_launch()
            return
        super().do_GET()

    def do_POST(self):
        if self.path in ("/api/launch", "/api/launch/"):
            self._handle_launch()
            return
        super().do_POST()

    def _handle_launch(self):
        running = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline') or []
                if any('main.py' in str(arg) for arg in cmdline):
                    running = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if running:
            res = {
                "success": True,
                "alreadyRunning": True,
                "message": "HADJ NO-TOUCH AI est déjà actif et en cours d'exécution sur votre PC."
            }
        else:
            try:
                main_path = os.path.join(PROJECT_ROOT, "main.py")
                if sys.platform == "win32":
                    subprocess.Popen(f'start "" "{PY_EXE}" "{main_path}"', shell=True, cwd=PROJECT_ROOT)
                else:
                    subprocess.Popen([PY_EXE, main_path], cwd=PROJECT_ROOT)
                res = {
                    "success": True,
                    "alreadyRunning": False,
                    "message": "Lancement de HADJ NO-TOUCH AI en cours..."
                }
            except Exception as e:
                res = {"success": False, "error": str(e)}

        body = json.dumps(res, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def run_server():
    os.chdir(WEB_DIR)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), CustomHandler) as httpd:
        print(f"[HADJ Web Server] Serving web interface & launcher at http://127.0.0.1:{PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    run_server()
