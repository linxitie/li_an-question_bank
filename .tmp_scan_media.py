# -*- coding: utf-8 -*-
import json, os, re, subprocess, sys

ROOT = r"E:\砺安题库相关资料\名师讲解视频"
MEDIA_EXT = {".mp4", ".m4a", ".mp3", ".flv", ".mkv", ".mov", ".wav"}

def probe(p):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration,size,bit_rate:stream=codec_type,codec_name,width,height",
             "-of", "json", p],
            capture_output=True, text=True, timeout=60)
        d = json.loads(out.stdout or "{}")
        fmt = d.get("format", {})
        dur = float(fmt.get("duration") or 0)
        vs = [s for s in d.get("streams", []) if s.get("codec_type") == "video"]
        w = vs[0].get("width") if vs else None
        h = vs[0].get("height") if vs else None
        return round(dur, 1), w, h
    except Exception as e:
        return None, None, None

def series_of(rel):
    d = os.path.dirname(rel)
    name = os.path.basename(rel)
    if d == "":
        if name.startswith("2022版公安专业科目-八大主题讲座"): return ("BN-2022-8", "白宁", "gongzhuan", "2022版公安专业科目·八大主题讲座")
        if name.startswith("2025公安联考白宁公专全程课"): return ("BN-2025-QC", "白宁", "gongzhuan", "2025公安联考公专全程课")
        if name.startswith("2025白宁公专八大讲座"): return ("BN-2025-8", "白宁", "gongzhuan", "2025白宁公专八大讲座")
        if name.startswith("2027白宁公专八大讲座"): return ("BN-2027-8", "白宁", "gongzhuan", "2027白宁公专八大讲座")
        if name.endswith(".zip"): return ("ARCHIVE", "桐哥", "gongzhuan", "桐哥讲公专（压缩包）")
        return ("MISC", "未知", "unknown", "未分类")
    if "刘文超" in d: return ("LWC-ZLFX", "刘文超", "xingce", "资料分析《行测》系统课（全国通用）")
    if "桐哥" in d: return ("TG-GZ-2027", "桐哥", "gongzhuan", "2027公安专业知识基础课（公安宝典配套）")
    return ("MISC", "未知", "unknown", "未分类")

def ep_of(name):
    m = re.search(r"\bp(\d{2})\b", name)
    return int(m.group(1)) if m else None

def title_of(name):
    m = re.search(r"\bp\d{2}\s+(.*?)(?:\s*\[[^\]]*\])?(?:\.\w+)+$", name)
    if m: return m.group(1).strip()
    return re.sub(r"\.[A-Za-z0-9.]+$", "", name)

items = []
for dirpath, _dirs, files in os.walk(ROOT):
    for f in files:
        p = os.path.join(dirpath, f)
        rel = os.path.relpath(p, ROOT)
        ext = os.path.splitext(f)[1].lower()
        size = os.path.getsize(p)
        sid, teacher, subject, sname = series_of(rel)
        bv = re.search(r"(BV[0-9A-Za-z]{10})", f)
        dur = None; w = None; h = None
        if ext in MEDIA_EXT and ".temp." not in f:
            dur, w, h = probe(p)
        items.append({
            "rel": rel.replace("\\", "/"),
            "name": f,
            "ext": ext,
            "size": size,
            "bytes_mb": round(size / 1048576, 1),
            "duration_sec": dur,
            "width": w, "height": h,
            "bvid": bv.group(1) if bv else None,
            "ep": ep_of(f),
            "title": title_of(f),
            "series_id": sid, "teacher": teacher, "subject": subject, "series_name": sname,
        })

items.sort(key=lambda x: (x["series_id"], x["ep"] if x["ep"] is not None else 999, x["rel"]))
tot_mb = sum(i["bytes_mb"] for i in items)
out = {"root": ROOT, "count": len(items), "total_mb": round(tot_mb, 1), "items": items}
dst = r"D:\砺安题库\砺安题库\backend\data\tmp_media_inventory.json"
os.makedirs(os.path.dirname(dst), exist_ok=True)
with open(dst, "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)

from collections import defaultdict
agg = defaultdict(lambda: [0, 0.0, 0.0])
for i in items:
    a = agg[(i["series_id"], i["series_name"])]
    a[0] += 1
    a[1] += i["bytes_mb"]
    a[2] += (i["duration_sec"] or 0)
print("total files:", len(items), "total MB:", round(tot_mb, 1))
for k, v in sorted(agg.items()):
    print("%-14s | %-46s | %2d files | %8.1f MB | %6.1f min" % (k[0], k[1][:46], v[0], v[1], v[2] / 60))
bad = [i["rel"] for i in items if i["duration_sec"] is None]
print("no-duration:", len(bad))
for b in bad[:10]: print("  ", b)
