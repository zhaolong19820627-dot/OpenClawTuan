#!/usr/bin/env python3
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote, quote
import os
import json
import gzip
import re
import cgi
import tempfile
import subprocess
import zipfile
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE, "data", "kb.json")
ROOT = "/mnt/tuan"
HOST = os.environ.get("TUANKB_HOST", "0.0.0.0")
PORT = int(os.environ.get("TUANKB_PORT", "18893"))

_KB_CACHE = {"mtime": 0, "data": {}}
REPORT_DIR = os.path.join(BASE, "data", "reports")
os.makedirs(REPORT_DIR, exist_ok=True)


def _pick_cn_font():
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


_FONT_NAME = "Helvetica"
_CN_FONT = _pick_cn_font()
if _CN_FONT:
    try:
        pdfmetrics.registerFont(TTFont("TuanCN", _CN_FONT))
        _FONT_NAME = "TuanCN"
    except Exception:
        _CN_FONT = None

# 兜底：使用 ReportLab 内置中文 CID 字体（避免中文乱码）
if _FONT_NAME == "Helvetica":
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        _FONT_NAME = "STSong-Light"
    except Exception:
        pass


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


def _extract_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".pdf":
            p = subprocess.run(["pdftotext", "-layout", path, "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
            if p.returncode == 0 and p.stdout.strip():
                return p.stdout
        if ext == ".docx":
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
                xml = re.sub(r"</w:p>|</w:tr>|</w:tbl>", "\n", xml)
                xml = re.sub(r"<w:tab[^>]*>", "\t", xml)
                xml = re.sub(r"<[^>]+>", " ", xml)
                return _normalize_text_for_extract(xml)
    except Exception:
        pass

    try:
        p = subprocess.run(["strings", "-n", "4", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
        return p.stdout[:250000]
    except Exception:
        return ""


def _normalize_text_for_extract(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[\t\f\v]+", " ", text)
    text = re.sub(r"\u3000", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _find_lines(text: str, keywords, max_items=4, max_len=90):
    lines = [x.strip() for x in re.split(r"[\r\n]+", text) if x.strip()]
    out = []
    seen = set()
    for ln in lines:
        s = ln.lower()
        if any(k.lower() in s for k in keywords):
            one = re.sub(r"\s+", " ", ln)
            one = one[:max_len]
            if one not in seen:
                out.append(one)
                seen.add(one)
        if len(out) >= max_items:
            break
    return "；".join(out) if out else "未明显命中，建议人工复核原文。"


def _analyze_bid_text(text: str):
    text = _normalize_text_for_extract(text)
    return {
        "供应商分析": {
            "资质要求": _find_lines(text, ["资质", "资格", "营业执照", "认证", "证书"]),
            "业绩要求": _find_lines(text, ["业绩", "类似项目", "合同金额", "案例"]),
            "团队要求": _find_lines(text, ["项目经理", "团队", "人员", "工程师", "驻场"]),
            "业绩要求（补充）": _find_lines(text, ["业绩证明", "合同复印件", "验收", "中标通知书"]),
            "信誉要求": _find_lines(text, ["信誉", "信用", "不良记录", "处罚", "黑名单"]),
            "其他要求": _find_lines(text, ["其他要求", "特别说明", "补充", "否决", "一票否决"]),
        },
        "评分分析": {
            "商务评分": _find_lines(text, ["商务评分", "商务部分", "商务分"]),
            "技术评分": _find_lines(text, ["技术评分", "技术部分", "技术分"]),
            "价格评分": _find_lines(text, ["价格评分", "报价得分", "价格分"]),
            "废标条款分析": _find_lines(text, ["废标", "否决", "无效投标", "取消资格"]),
        },
        "标书编制分析": {
            "标书编制整体目录分析": _find_lines(text, ["目录", "章", "节", "投标文件组成"]),
            "商务标书编制分析（大纲目录）": _find_lines(text, ["商务标", "商务文件", "资格审查", "商务响应"]),
            "技术标书编制分析（大纲目录）": _find_lines(text, ["技术标", "技术方案", "实施方案", "服务方案"]),
            "价格部分编制分析": _find_lines(text, ["报价", "价格", "分项报价", "报价表"]),
            "承诺函分析": _find_lines(text, ["承诺函", "承诺", "声明函"]),
            "其他部分分析": _find_lines(text, ["附录", "附件", "补充", "备注"]),
        }
    }


def _analysis_to_pdf(file_name: str, analysis: dict) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = os.path.join(REPORT_DIR, f"bid-analysis-{ts}.pdf")

    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=26, rightMargin=26, topMargin=28, bottomMargin=24)
    styles = getSampleStyleSheet()
    font = _FONT_NAME
    h_style = ParagraphStyle("h", parent=styles["Heading2"], fontName=font, fontSize=13, leading=16)
    n_style = ParagraphStyle("n", parent=styles["Normal"], fontName=font, fontSize=9.5, leading=13)

    story = [
        Paragraph("图安标书分析报告", ParagraphStyle("title", parent=styles["Title"], fontName=font, fontSize=16)),
        Spacer(1, 6),
        Paragraph(f"文件：{file_name}", n_style),
        Spacer(1, 10),
    ]

    for lvl1, sec in analysis.items():
        story.append(Paragraph(f"{lvl1}", h_style))
        data = [["分析项", "分析结果"]]
        for lvl2, txt in (sec or {}).items():
            data.append([Paragraph(str(lvl2), n_style), Paragraph(str(txt).replace("\n", "<br/>"), n_style)])

        t = Table(data, colWidths=[130, 390], repeatRows=1)
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbe5f1")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fc")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 10))

    doc.build(story)
    return out


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
            allowed_roots = [os.path.realpath(ROOT), os.path.realpath(REPORT_DIR)]
            if not any(p.startswith(ar) for ar in allowed_roots) or not os.path.isfile(p):
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

    def do_POST(self):
        u = urlparse(self.path)
        if u.path in ("/api/bid/analyze", "/api/bid/analyze_pdf"):
            ctype, _ = cgi.parse_header(self.headers.get("Content-Type", ""))
            if ctype != "multipart/form-data":
                self._json({"ok": False, "error": "请使用 multipart/form-data 上传文件"}, code=400)
                return

            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type")},
            )
            file_item = form["file"] if "file" in form else None
            if file_item is None or not getattr(file_item, "filename", ""):
                self._json({"ok": False, "error": "未检测到上传文件"}, code=400)
                return

            filename = os.path.basename(file_item.filename)
            ext = os.path.splitext(filename)[1].lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tf:
                tf.write(file_item.file.read())
                temp_path = tf.name

            try:
                text = _extract_text(temp_path)
                analysis = _analyze_bid_text(text)
                if u.path == "/api/bid/analyze_pdf":
                    pdf_path = _analysis_to_pdf(filename, analysis)
                    self._json({
                        "ok": True,
                        "file_name": filename,
                        "file_type": ext,
                        "analysis": analysis,
                        "pdf_path": pdf_path,
                        "pdf_download_url": f"/download?path={pdf_path}",
                    })
                    return

                self._json({
                    "ok": True,
                    "file_name": filename,
                    "file_type": ext,
                    "analysis": analysis,
                })
            finally:
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            return

        self._json({"ok": False, "error": "not found"}, code=404)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"TuanKB serving on http://{HOST}:{PORT} base={BASE}")
    server.serve_forever()
