#!/usr/bin/env python3
import os
import re
import json
from datetime import datetime
from collections import defaultdict

ROOT = "/mnt/tuan"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "kb.json")

EXT_MAP = {
    ".ppt": "汇报PPT", ".pptx": "汇报PPT",
    ".doc": "解决方案文档", ".docx": "解决方案文档",
    ".pdf": "解决方案文档",
    ".xls": "报价文档", ".xlsx": "报价文档",
    ".mp4": "视频", ".avi": "视频", ".mov": "视频", ".mkv": "视频", ".wmv": "视频", ".flv": "视频",
}

CATEGORY_ORDER = ["汇报PPT", "解决方案文档", "招标文档", "投标文档", "报价文档", "标准规范", "视频", "其他"]

INDUSTRY_KEYWORDS = {
    "AI赋能": ["ai", "人工智能", "aigc", "大模型", "llm"],
    "安全生产": ["安全生产", "隐患", "应急", "风险管控", "双重预防"],
    "化工园区": ["化工", "危化", "危险化学品"],
    "智慧园区": ["智慧园区", "园区", "数字孪生"],
    "车路协同": ["车路协同", "车联网", "路侧", "v2x"],
}

SKIP_DIRS = {".git", ".stfolder", ".stversions"}
FALLBACK_TS = datetime(2025, 12, 30, 0, 0, 0)


def normalize_name(name: str) -> str:
    base = os.path.splitext(name)[0].lower()
    base = re.sub(r"[\(（\[]?(v|ver|版本)?\s*\d+(\.\d+)*[\)）\]]?", "", base)
    base = re.sub(r"\d{4}[-_/年]?\d{1,2}[-_/月]?\d{1,2}[日]?", "", base)
    base = re.sub(r"(终版|最终版|定稿|副本|copy|new)", "", base)
    base = re.sub(r"[^\w\u4e00-\u9fff]", "", base)
    return base.strip()


def detect_category(path: str, ext: str, name: str) -> str:
    s = f"{path} {name}".lower()
    if "招标" in s:
        return "招标文档"
    if "投标" in s:
        return "投标文档"
    if "报价" in s or "预算" in s:
        return "报价文档"
    if "标准" in s or "规范" in s or "指南" in s:
        return "标准规范"
    return EXT_MAP.get(ext, "其他")


def detect_industry(path: str, name: str) -> str:
    n = name.lower()
    full = f"{name} {path}".lower()

    # AI赋能：仅当文件名包含明显 AI 关键词才归类
    if any(k in n for k in INDUSTRY_KEYWORDS["AI赋能"]):
        return "AI赋能"

    for k, kws in INDUSTRY_KEYWORDS.items():
        if k == "AI赋能":
            continue
        if any(w.lower() in full for w in kws):
            return k

    return "其他行业"


def project_name(path: str, name: str) -> str:
    b = os.path.splitext(name)[0]
    b = re.sub(r"^[【\[].*?[】\]]", "", b).strip()
    # 保留中文主干（不再只取英文简写）
    zh = "".join(re.findall(r"[\u4e00-\u9fff]+", b))
    if len(zh) >= 2:
        return zh

    parent = os.path.basename(os.path.dirname(path))
    zh_parent = "".join(re.findall(r"[\u4e00-\u9fff]+", parent))
    if len(zh_parent) >= 2:
        return zh_parent

    # 兜底：取去版本化后的文件名
    b2 = re.split(r"[-_—（(]", b)[0].strip()
    return b2 or parent or "未命名项目"


def safe_dt_from_ts(ts: int):
    try:
        dt = datetime.fromtimestamp(int(ts))
        if dt.year < 1990 or dt.year > 2100:
            raise ValueError("timestamp out of accepted year range")
        return dt, False
    except Exception:
        return FALLBACK_TS, True


def scan_files(root: str):
    files = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            if fn.startswith("."):
                continue
            full = os.path.join(dp, fn)
            if not os.path.isfile(full):
                continue
            ext = os.path.splitext(fn)[1].lower()
            st = os.stat(full)
            files.append({
                "name": fn,
                "path": full,
                "ext": ext,
                "mtime": int(st.st_mtime),
                "size": st.st_size,
            })
    return files


def build():
    all_files = scan_files(ROOT)
    groups = defaultdict(list)
    for f in all_files:
        key = normalize_name(f["name"])
        groups[(key, f["ext"])].append(f)

    latest_entries = []
    for (_, _), arr in groups.items():
        arr.sort(key=lambda x: x["mtime"], reverse=True)
        latest = arr[0]
        history = arr[1:]
        latest_entries.append((latest, history))

    docs = []
    for latest, history in latest_entries:
        path = latest["path"]
        name = latest["name"]
        ext = latest["ext"]
        cat = detect_category(path, ext, name)
        dt, ts_fallback = safe_dt_from_ts(latest["mtime"])
        mtime = dt.strftime("%Y-%m-%d %H:%M:%S")
        docs.append({
            "title": name,
            "category": cat,
            "project_name": project_name(path, name),
            "industry_type": detect_industry(path, name),
            "time": dt.strftime("%Y-%m-%d"),
            "presale_name": "",
            "updated_at": mtime,
            "timestamp_fallback": ts_fallback,
            "history_versions": [h["path"] for h in history],
            "file_path": path,
            "size": latest["size"],
        })

    cat_map = {c: [] for c in CATEGORY_ORDER}
    cat_map["其他"] = []
    for d in docs:
        if d["category"] not in cat_map:
            cat_map["其他"].append(d)
        else:
            cat_map[d["category"]].append(d)

    for c in cat_map:
        cat_map[c].sort(key=lambda x: x["updated_at"], reverse=True)

    out = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "root": ROOT,
        "total_raw_files": len(all_files),
        "total_indexed_latest": len(docs),
        "categories": [{"name": c, "count": len(cat_map.get(c, []))} for c in CATEGORY_ORDER],
        "documents": docs,
        "by_category": cat_map,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"generated: {OUT}")
    print(f"raw={len(all_files)} indexed_latest={len(docs)}")


if __name__ == "__main__":
    build()
