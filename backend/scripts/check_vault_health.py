# 知识库健康度检查（模块7 · P6 / 2-1 审核环节）
# 指标：断链数（必须 0）、孤儿页（无入链）、生成区合规、页面总量
# 退出码：断链 > 0 -> 1，便于接进门禁
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VAULT = ROOT / "docs" / "knowledge-vault" / "联考知识库"
LINK = re.compile(r"\[\[([^\]|#]+)")


def norm(p: Path) -> str:
    return p.relative_to(VAULT).as_posix()


def main() -> int:
    if not VAULT.exists():
        print(f"[SKIP] 知识库不存在: {VAULT}")
        return 0
    pages = sorted(VAULT.rglob("*.md"))
    page_set = {norm(p)[:-3] for p in pages}  # 去掉 .md

    inbound = {k: 0 for k in page_set}
    broken = []
    missing_generated = 0

    for p in pages:
        text = p.read_text(encoding="utf-8")
        head = "\n".join(text.splitlines()[:15])  # 只看 frontmatter，避免正文示例误判
        if "generated: true" in head and "GENERATED:BEGIN" not in text:
            missing_generated += 1
        for raw in LINK.findall(text):
            # 表格里的 wikilink 写成 [[路径\|别名]]，尾部反斜杠是表格转义，需要剥掉
            target = raw.strip().lstrip("/").rstrip("\\")
            if not target:
                continue
            if target in page_set:
                inbound[target] += 1
                continue
            hit = any(k.endswith("/" + target) or k == target for k in page_set)
            if hit:
                continue
            broken.append(f"{norm(p)} -> {target}")

    orphans = [k for k, v in inbound.items() if v == 0 and not k.endswith("README")]

    print(f"[PAGES] {len(pages)} 个页面")
    print(f"[BROKEN] {len(broken)} 条断链")
    for b in broken[:10]:
        print("   " + b)
    print(f"[ORPHAN] {len(orphans)} 个无入链页面")
    for o in orphans[:10]:
        print("   " + o)
    print(f"[GENERATED] 缺失生成区标记的页面: {missing_generated}")
    print("[HEALTH] " + ("PASS" if not broken else "FAIL"))
    return 0 if not broken else 1


if __name__ == "__main__":
    raise SystemExit(main())
