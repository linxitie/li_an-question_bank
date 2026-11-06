"""回溯打码（安全版）：用运行时引擎的命中区间打码，只改命中的字，跳过 HTML 标签内部。

2026-11-06 修正：旧版遍历全词表做 str.replace，会把「就是」这类泛词、甚至整句测试文本
一起打掉（实测「楼主就是个智障」→「*******」）。现在与线上一致，用 span 级打码。
"""
import re
import sys

sys.path.insert(0, r"D:\AAA项目文件\砺安题库\li_an-question_bank\backend")

from app.core.database import SessionLocal  # noqa: E402
from app.models.models import ForumComment, ForumPost  # noqa: E402
from app.services.content_guard import engine as cg_engine  # noqa: E402

APPLY = "--apply" in sys.argv
TAG = re.compile(r"<[^>]+>")

db = SessionLocal()
guard = cg_engine.get_engine(db)


def mask_outside_tags(text: str) -> str:
    """按 <tag> 切块，只对文本块做 span 级打码，标签原样保留。"""
    parts: list[str] = []
    last = 0
    for match in TAG.finditer(text):
        parts.append(text[last:match.start()])
        parts.append(match.group(0))
        last = match.end()
    parts.append(text[last:])
    out: list[str] = []
    for idx, chunk in enumerate(parts):
        if idx % 2 == 1:  # 奇数位是标签，原样保留
            out.append(chunk)
            continue
        detected = guard.detect(chunk)
        out.append(detected.get("masked_text") or chunk)
    return "".join(out)


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
print(f"{'[演练]' if not APPLY else '[已写入]'} 扫描 {scanned} 处，命中违规词 {changed} 处")
for s in samples:
    print("  ", s)
