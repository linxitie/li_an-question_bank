# 预建「答案解析」缓存：一次性全册扫描 84 对，产物 backend/data/tmp_answers.json
import glob, json, os, re
import pdfplumber

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ANS = re.compile(r"^\s*(\d{1,3})[.、]\s*正确答案[:：]\s*([A-D])")

out = {}
files = sorted(glob.glob(os.path.join(ROOT, "题库", "**", "*答案解析.pdf"), recursive=True))
for i, f in enumerate(files, 1):
    key = os.path.basename(f).replace("答案解析.pdf", "").strip()
    m = {}
    try:
        with pdfplumber.open(f) as pdf:
            for page in pdf.pages:
                for ln in (page.extract_text() or "").splitlines():
                    mo = ANS.match(ln)
                    if mo and int(mo.group(1)) not in m:
                        m[int(mo.group(1))] = mo.group(2)
    except Exception as e:
        print("ERR", key[:24], str(e)[:40])
    out[key] = m
    if i % 20 == 0:
        print(f"[{i}/{len(files)}]")

path = os.path.join(ROOT, "backend", "data", "tmp_answers.json")
print("OUT", path)
json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False)
print("DONE", len(out), "册 →", path)
