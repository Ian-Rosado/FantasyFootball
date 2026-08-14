#!/usr/bin/env python3
# Gridiron Grind - local draft sync server.
# Serves the Draft Day Tool AND relays the live draft from the browser bookmark to the tool.
# Started automatically by Start_Draft_Tool.bat. Keep the window open during your draft.
import http.server, socketserver, json, os
PORT = 8000
DIR = os.path.dirname(os.path.abspath(__file__))
latest = {"data": None}

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=DIR, **k)
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()
    def do_POST(self):
        if self.path.rstrip('/').endswith('/draft'):
            n = int(self.headers.get('Content-Length', 0)); body = self.rfile.read(n)
            try:
                latest["data"] = json.loads(body.decode('utf-8')); ok = True
            except Exception:
                ok = False
            self.send_response(200 if ok else 400); self._cors()
            self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(b'{"ok":true}' if ok else b'{"ok":false}')
        else:
            self.send_response(404); self.end_headers()
    def do_GET(self):
        if self.path.rstrip('/').endswith('/draft'):
            self.send_response(200); self._cors()
            self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps(latest["data"]).encode('utf-8'))
        else:
            super().do_GET()
    def log_message(self, *a):
        pass

class Srv(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

if __name__ == '__main__':
    print('=' * 58)
    print(' Gridiron Grind draft server is RUNNING.')
    print(' Tool:  http://localhost:%d/Draft_Day_Tool.html' % PORT)
    print(' Keep this window OPEN during your draft. Close it when done.')
    print('=' * 58)
    Srv(('127.0.0.1', PORT), H).serve_forever()
