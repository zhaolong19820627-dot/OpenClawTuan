#!/usr/bin/env python3
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote, quote
import os
import json
import gzip

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE, "data", "kb.json")
ROOT = "/mnt/tuan"
HOST = os.environ.get("TUANKB_HOST", "0.0.0.0")
PORT = int(os.environ.get("TUANKB_PORT", "18893"))

_KB_CACHE = {"mtime": 0, "data": {}}


def load_kb():
    try:
        mtime = os.path.getmtime(DATA_FILE)
        if mtime != _KB_CACHE["mtime"]:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                _KB_CACHE["data"] = json.load(f)
            _KB_CACHE["mtime"] = mtime
        return _KB_CACHE["data"]
    except Exception:
        return {"documents": []}


def score_doc(q: str, d: dict):
    q = q.lower().strip()
    if not q:
        return 0
    title = str(d.get("title", "")).lower()
    project = str(d.get("project_name", "")).lower()
    category = str(d.get("category", "")).lower()
    industry = str(d.get("industry_type", "")).lower()
    p = str(d.get("file_path", "")).lower()

    s = 0
    if q in title:
        s += 8
    if q in project:
        s += 7
    if q in p:
        s += 4
    if q in category:
        s += 2
    if q in industry:
        s += 2

    tokens = [t for t in q.replace("_", " ").replace("-", " ").split() if t]
    for t in tokens:
        if t in title:
            s += 2
        if t in project:
            s += 2
        if t in p:
            s += 1
    return s


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE, **kwargs)

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)

        # 首次打开优化：对 kb.json 开启 gzip + cache
        if u.path == "/data/kb.json":
            try:
                with open(DATA_FILE, "rb") as f:
                    raw = f.read()
                ae = (self.headers.get("Accept-Encoding") or "").lower()
                if "gzip" in ae:
                    body = gzip.compress(raw, compresslevel=6)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Encoding", "gzip")
                    self.send_header("Cache-Control", "public, max-age=120")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "public, max-age=120")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            except Exception:
                self.send_error(404, "kb.json not found")
                return

        if u.path in ("/api/search", "/api/dingtalk_search"):
            q = parse_qs(u.query).get("q", [""])[0].strip()
            kb = load_kb()
            docs = kb.get("documents")
            if docs is None:
                docs = []
                for _, arr in (kb.get("by_category") or {}).items():
                    docs.extend(arr)
            ranked = []
            for d in docs:
                s = score_doc(q, d)
                if s > 0:
                    item = dict(d)
                    item["score"] = s
                    item["download_url"] = f"/download?path={d.get('file_path','')}"
                    ranked.append(item)
            ranked.sort(key=lambda x: (x.get("score", 0), x.get("updated_at", "")), reverse=True)
            top = ranked[:5]
            if u.path == "/api/dingtalk_search":
                lines = [f"图安检索：{q}"]
                if not top:
                    lines.append("未找到相关文件")
                else:
                    for i, x in enumerate(top, 1):
                        lines.append(f"{i}. {x.get('title','')} | 项目：{x.get('project_name','-')} | 下载：http://{HOST}:{PORT}/download?path={x.get('file_path','')}")
                self._json({"query": q, "count": len(ranked), "top": top, "reply_text": "\n".join(lines)})
                return
            self._json({"query": q, "count": len(ranked), "top": top})
            return

        if u.path in ("/download", "/preview"):
            raw = parse_qs(u.query).get("path", [""])[0]
            p = os.path.realpath(unquote(raw))
            if not p.startswith(os.path.realpath(ROOT)) or not os.path.isfile(p):
                self.send_error(404, "file not found")
                return

            fn = os.path.basename(p)
            ext = os.path.splitext(fn)[1].lower()
            ctype = "application/octet-stream"
            if ext == ".pdf":
                ctype = "application/pdf"
            elif ext in (".mp4", ".mov", ".mkv", ".avi", ".wmv", ".flv"):
                ctype = "video/mp4"

            self.send_response(200)
            self.send_header("Content-Type", ctype)
            disposition = "inline" if u.path == "/preview" else "attachment"
            self.send_header("Content-Disposition", f"{disposition}; filename*=UTF-8''{quote(fn)}")
            self.send_header("Content-Length", str(os.path.getsize(p)))
            self.end_headers()
            with open(p, "rb") as f:
                while True:
                    chunk = f.read(1024 * 64)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            return

        return super().do_GET()


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"TuanKB serving on http://{HOST}:{PORT} base={BASE}")
    server.serve_forever()
