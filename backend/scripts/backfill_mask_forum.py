"""回溯打码（安全版）：只替换中文词条，且跳过 HTML 标签内部，避免破坏样式与英文单词。"""
import re
import sys

sys.path.insert(0, r"D:\AAA项目文件\砺安题库\li_an-question_bank\backend")

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.models import ForumComment, ForumPost  # noqa: E402
from app.services import policy_compiler as pc  # noqa: E402

APPLY = "--apply" in sys.argv
CJK = re.compile(r"^[\u4e00-\u9fa5]{2,}$")

terms = set()
for name, words in (pc.load_lexicons(str(settings.MODERATION_VAULT_DIR)) or {}).items():
    if name in ("ambiguous_v1", "general_zh_v1"):
        continue
    terms.update(w for w in words if CJK.match(w))
terms = sorted(terms, key=len, reverse=True)

TAG = re.compile(r"<[^>]+>")


def mask_outside_tags(text: str) -> str:
    parts = []
    last = 0
    for m in TAG.finditer(text):
        parts.append(("text", text[last:m.start()]))
        parts.append(("tag", m.group(0)))
        last = m.end()
    parts.append(("text", text[last:]))
    out = []
    for kind, chunk in parts:
        if kind == "tag":
            out.append(chunk)
            continue
        for term in terms:
            if term in chunk:
                chunk = chunk.replace(term, "*" * len(term))
        out.append(chunk)
    return "".join(out)


db = SessionLocal()
scanned = changed = 0
samples = []
for model, field in ((ForumPost, "title"), (ForumPost, "content"), (ForumComment, "content")):
    for row in db.query(model).all():
        text = getattr(row, field) or ""
        if not text:
            continue
        scanned += 1
        new = mask_outside_tags(text)
        if new != text:
            changed += 1
            if len(samples) < 5:
                samples.append((model.__name__, field, new[:60]))
            if APPLY:
                setattr(row, field, new)
if APPLY:
    db.commit()
db.close()
print(f"{'[演练]' if not APPLY else '[已写入]'} 扫描 {scanned} 处，命中中文违规词 {changed} 处")
for s in samples:
    print("  ", s)
