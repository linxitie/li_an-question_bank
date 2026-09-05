"""检查所有 .json 文件的 __VERSION__ 字段类型"""
import json
import os
import glob

files = glob.glob(r'd:\砺安题库\砺安题库\.vtj\files\*.json')
print(f"共找到 {len(files)} 个 .json 文件\n")

for f in sorted(files):
    try:
        with open(f, encoding='utf-8') as fp:
            data = json.load(fp)
        ver = data.get('__VERSION__')
        vtype = type(ver).__name__
        flag = "OK" if isinstance(ver, str) else "!!! NUMBER TYPE !!!"
        print(f"{os.path.basename(f):40s} __VERSION__={ver!r:25s} type={vtype:10s} {flag}")
    except Exception as e:
        print(f"{os.path.basename(f):40s} ERROR: {e}")

# 同时检查 .vue 文件中的 version
print("\n\n=== .vue 文件中的 version ===")
vue_files = glob.glob(r'd:\砺安题库\砺安题库\.vtj\vue\*.vue')
for f in sorted(vue_files):
    try:
        with open(f, encoding='utf-8') as fp:
            content = fp.read()
        # 查找 useProvider 中的 version
        import re
        m = re.search(r"useProvider\(\{[^}]*version:\s*['\"]([^'\"]+)['\"]", content)
        if m:
            ver = m.group(1)
            print(f"{os.path.basename(f):40s} version='{ver}'")
        else:
            print(f"{os.path.basename(f):40s} (no useProvider version found)")
    except Exception as e:
        print(f"{os.path.basename(f):40s} ERROR: {e}")
