#!/usr/bin/env python3
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = os.environ.get("TUANKB_HOST", "0.0.0.0")
PORT = int(os.environ.get("TUANKB_PORT", "18893"))

os.chdir(BASE)
httpd = ThreadingHTTPServer((HOST, PORT), SimpleHTTPRequestHandler)
print(f"TuanKB serving on http://{HOST}:{PORT} base={BASE}")
httpd.serve_forever()
