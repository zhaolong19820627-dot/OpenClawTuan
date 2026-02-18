#!/usr/bin/env python3
import os
import re
import json
from datetime import datetime
from collections import defaultdict

ROOT = "/mnt/tuan"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "kb.json")

CATEGORY_ORDER = ["汇报PPT", "解决方案文档", "招标文档", "投标文档", "报价文档", "合同文档", "标准规范", "视频", "图安资质", "其他"]

VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"}
EXCEL_EXT = {".xls", ".xlsx"}
DOC_EXT = {".doc", ".docx", ".pdf", ".ppt", ".pptx"}

PRIMARY_TAGS = {
    "AI赋能": ["AI视频分析一体机", "应急大模型", "化工园区AI赋能", "应急领域AI赋能", "其他"],
    "安全生产": ["HSE", "安全生产标准化", "重大危险源", "双重预防", "特殊作业", "人员定位", "承包商", "教育培训", "6+5", "其他"],
    "智慧园区": ["化工园区", "经开区", "其他"],
    "应急管理": ["应急指挥", "应急演练", "应急推演", "其他"],
    "车路协同": ["智慧高速", "智慧隧道", "智慧桥梁", "智慧服务区", "智慧收费站", "智慧停车场", "无人驾驶训练场", "其他"],
    "其他行业": [],
}

SUBTAG_KEYWORDS = {
    "AI赋能": {
        "AI视频分析一体机": ["ai视频", "视频分析一体机", "智能视频"],
        "应急大模型": ["应急大模型", "大模型", "llm", "aigc"],
        "化工园区AI赋能": ["化工园区ai", "化工 ai", "危化 ai"],
        "应急领域AI赋能": ["应急 ai", "应急领域ai", "应急智能"],
    },
    "安全生产": {
        "HSE": ["hse"],
        "安全生产标准化": ["安全生产标准化"],
        "重大危险源": ["重大危险源"],
        "双重预防": ["双重预防"],
        "特殊作业": ["特殊作业", "动火", "受限空间"],
        "人员定位": ["人员定位"],
        "承包商": ["承包商"],
        "教育培训": ["教育培训", "培训"],
        "6+5": ["6+5"],
    },
    "智慧园区": {
        "化工园区": ["化工园区"],
        "经开区": ["经开区", "开发区"],
    },
    "应急管理": {
        "应急指挥": ["应急指挥"],
        "应急演练": ["应急演练"],
        "应急推演": ["应急推演"],
    },
    "车路协同": {
        "智慧高速": ["智慧高速"],
        "智慧隧道": ["智慧隧道"],
        "智慧桥梁": ["智慧桥梁"],
        "智慧服务区": ["智慧服务区"],
        "智慧收费站": ["智慧收费站"],
        "智慧停车场": ["智慧停车场"],
        "无人驾驶训练场": ["无人驾驶训练场", "无人驾驶训练厂"],
    },
}

AI_FILE_KEYWORDS = ["ai", "人工智能", "aigc", "大模型", "llm"]
SKIP_DIRS = {".git", ".stfolder", ".stversions"}
FALLBACK_TS = datetime(2025, 12, 30, 0, 0, 0)

QUAL_FOLDER_HINT = "/mnt/tuan/0图安世纪-标准解决方案/01 图安世纪资质"
QUAL_SECOND_LEVEL = ["公司介绍（含产品介绍）", "相关证书", "专利", "著作权", "测试报告", "合同业绩", "人员资质", "其他"]


def normalize_name(name: str) -> str:
    base = os.path.splitext(name)[0].lower()
    base = re.sub(r"[\(（\[]?(v|ver|版本)?\s*\d+(\.\d+)*[\)）\]]?", "", base)
    base = re.sub(r"\d{4}[-_/年]?\d{1,2}[-_/月]?\d{1,2}[日]?", "", base)
    base = re.sub(r"(终版|最终版|定稿|副本|copy|new)", "", base)
    base = re.sub(r"[^\w\u4e00-\u9fff]", "", base)
    return base.strip()


def detect_category(path: str, ext: str, name: str) -> str:
    s = f"{path} {name}".lower()
    if QUAL_FOLDER_HINT.lower() in path.lower() or "图安世纪资质" in s:
        return "图安资质"
    if "招标" in s:
        return "招标文档"
    if "投标" in s:
        return "投标文档"
    if "合同" in s:
        return "合同文档"
    # 报价文档仅限 excel
    if ext in EXCEL_EXT and any(k in s for k in ["报价", "预算", "清单", "分项"]):
        return "报价文档"
    if "标准" in s or "规范" in s or "指南" in s:
        return "标准规范"
    if ext in {".ppt", ".pptx"}:
        return "汇报PPT"
    if ext in VIDEO_EXT:
        return "视频"
    if ext in DOC_EXT:
        return "解决方案文档"
    if ext in EXCEL_EXT:
        return "其他"
    return "其他"


def detect_tags(path: str, name: str):
    n = name.lower()
    full = f"{name} {path}".lower()

    # AI赋能：仅文件名包含明显关键词
    if any(k in n for k in AI_FILE_KEYWORDS):
        primary = "AI赋能"
        sub_map = SUBTAG_KEYWORDS.get(primary, {})
        for sub, kws in sub_map.items():
            if any(k.lower() in full for k in kws):
                return primary, sub
        return primary, "其他"

    for primary in ["安全生产", "智慧园区", "应急管理", "车路协同"]:
        sub_map = SUBTAG_KEYWORDS.get(primary, {})
        for sub, kws in sub_map.items():
            if any(k.lower() in full for k in kws):
                return primary, sub
        # 一级命中兜底
        if any(primary.lower() in full for _ in [0]):
            return primary, "其他"

    # 规则补充
    if any(k in full for k in ["安全生产", "隐患", "双重预防", "重大危险源"]):
        return "安全生产", "其他"
    if any(k in full for k in ["智慧园区", "园区", "数字孪生", "化工园区", "经开区"]):
        sub = "化工园区" if "化工园区" in full else ("经开区" if "经开区" in full or "开发区" in full else "其他")
        return "智慧园区", sub
    if any(k in full for k in ["应急指挥", "应急演练", "应急推演", "应急"]):
        sub = "应急指挥" if "应急指挥" in full else ("应急演练" if "应急演练" in full else ("应急推演" if "应急推演" in full else "其他"))
        return "应急管理", sub
    if any(k in full for k in ["车路协同", "智慧高速", "智慧隧道", "智慧桥梁", "智慧服务区", "智慧收费站", "智慧停车场", "无人驾驶训练场", "无人驾驶训练厂", "v2x"]):
        for sub in PRIMARY_TAGS["车路协同"]:
            if sub != "其他" and sub.lower() in full:
                return "车路协同", sub
        return "车路协同", "其他"

    return "其他行业", ""


def detect_qualification_group(path: str, name: str) -> str:
    s = f"{path} {name}".lower()
    if any(k in s for k in ["公司介绍", "产品介绍", "产品手册", "宣传册"]):
        return "公司介绍（含产品介绍）"
    if any(k in s for k in ["证书", "认证", "资信", "荣誉"]):
        return "相关证书"
    if "专利" in s:
        return "专利"
    if any(k in s for k in ["著作权", "软著", "软件著作权"]):
        return "著作权"
    if any(k in s for k in ["测试报告", "检测报告", "检验报告", "测评报告"]):
        return "测试报告"
    if any(k in s for k in ["合同业绩", "业绩", "案例合同", "项目合同"]):
        return "合同业绩"
    if any(k in s for k in ["人员资质", "人员证书", "工程师", "职称", "建造师"]):
        return "人员资质"
    return "其他"


def project_name(path: str, name: str, category: str) -> str:
    if category == "图安资质":
        return detect_qualification_group(path, name)

    b = os.path.splitext(name)[0]
    b = re.sub(r"^[【\[].*?[】\]]", "", b).strip()
    zh = "".join(re.findall(r"[\u4e00-\u9fff]+", b))
    if len(zh) >= 2:
        return zh
    parent = os.path.basename(os.path.dirname(path))
    zh_parent = "".join(re.findall(r"[\u4e00-\u9fff]+", parent))
    if len(zh_parent) >= 2:
        return zh_parent
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
            if fn.startswith('.'):
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
        latest_entries.append((arr[0], arr[1:]))

    docs = []
    for latest, history in latest_entries:
        path = latest["path"]
        name = latest["name"]
        ext = latest["ext"]
        cat = detect_category(path, ext, name)
        dt, ts_fallback = safe_dt_from_ts(latest["mtime"])
        primary, secondary = detect_tags(path, name)
        docs.append({
            "title": name,
            "category": cat,
            "project_name": project_name(path, name, cat),
            "industry_type": primary,
            "industry_primary": primary,
            "industry_secondary": secondary,
            "time": dt.strftime("%Y-%m-%d"),
            "presale_name": "",
            "updated_at": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp_fallback": ts_fallback,
            "history_versions": [h["path"] for h in history],
            "file_path": path,
            "size": latest["size"],
            "ext": ext,
        })

    cat_map = {c: [] for c in CATEGORY_ORDER}
    for d in docs:
        cat_map[d["category"]].append(d)

    for c in cat_map:
        cat_map[c].sort(key=lambda x: x["updated_at"], reverse=True)

    out = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "root": ROOT,
        "total_raw_files": len(all_files),
        "total_indexed_latest": len(docs),
        "categories": [{"name": c, "count": len(cat_map.get(c, []))} for c in CATEGORY_ORDER],
        "tag_tree": PRIMARY_TAGS,
        # 仅保留 by_category，避免 documents + by_category 双份冗余造成首屏加载慢
        "by_category": cat_map,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    print(f"generated: {OUT}")
    print(f"raw={len(all_files)} indexed_latest={len(docs)}")


if __name__ == "__main__":
    build()
