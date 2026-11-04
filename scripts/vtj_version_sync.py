#!/usr/bin/env python3
"""
VTJ 版本同步脚本
用于在修改 .vtj/vue/*.vue 后自动同步 .vtj/files/*.json 的 __VERSION__
以及确保 useProvider({version}) 与 JSON 版本号一致

分类口径（2026-11-02 起）
------------------------
`.vtj/vue/` 下有两类文件，本脚本只对「设计器页面」负责：

1. **设计器页面**：`<script>` 里有 `useProvider({ id, version })`，且 `.vtj/files/<同名>.json`
   里有 `__VERSION__` —— 二者必须相等，不一致就同步/报错。
2. **非设计器页面**（手写页、纯组件、或只有一边存在）：
   - 有 `.vue` 但没有同名 `.json`（如 `TeacherNavHeader.vue`、`smart_recommend.vue`）
   - 有 `.json` 但 `.vue` 里没有 `useProvider`（如 4 个 `teacher_*` 手写页）
   这类文件没有「设计器版本」可对齐，**跳过并计数**，不算失败；需要严格模式时加 `--strict`。

用法
----
    python scripts/vtj_version_sync.py                 # 同步模式：把 JSON 版本对齐到 Vue（默认）
    python scripts/vtj_version_sync.py --check         # 检查模式：只比对不写入，不一致则 exit 1（CI 用）
    python scripts/vtj_version_sync.py --strict        # 非设计器页面也视为失败（人工排查用）
    python scripts/vtj_version_sync.py home_page.vue   # 只同步指定文件
"""

import json
import re
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
VTJ_VUE_DIR = PROJECT_ROOT / '.vtj' / 'vue'
VTJ_FILES_DIR = PROJECT_ROOT / '.vtj' / 'files'

SKIP_NO_JSON = 'skip-no-json'
SKIP_NO_PROVIDER = 'skip-no-provider'


def extract_vue_version(vue_path: Path) -> str | None:
    """从 .vue 文件提取 useProvider 的 version 参数"""
    try:
        content = vue_path.read_text(encoding='utf-8')

        # 匹配 useProvider({ id: 'xxx', version: '1234567890123' }) 格式
        patterns = [
            r"useProvider\(\{\s*id\s*:\s*['\"][^'\"]+['\"],\s*version\s*:\s*['\"](\d+)['\"]",
            r"useProvider\(\{\s*version\s*:\s*['\"](\d+)['\"]",
            r"useProvider\(.*?version\s*:\s*['\"](\d+)['\"]",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1)

        return None
    except Exception as e:
        print(f"⚠️  读取 Vue 文件失败 {vue_path}: {e}")
        return None


def extract_json_version(json_path: Path) -> str | None:
    """从 JSON 文件提取 __VERSION__"""
    try:
        data = json.loads(json_path.read_text(encoding='utf-8'))
        return str(data.get('__VERSION__', ''))
    except Exception as e:
        print(f"⚠️  读取 JSON 文件失败 {json_path}: {e}")
        return None


def update_json_version(json_path: Path, new_version: str) -> bool:
    """更新 JSON 文件的 __VERSION__"""
    try:
        data = json.loads(json_path.read_text(encoding='utf-8'))
        data['__VERSION__'] = new_version
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        return True
    except Exception as e:
        print(f"❌ 更新 JSON 版本失败 {json_path}: {e}")
        return False


def classify(vue_path: Path) -> tuple[str, str | None, str | None]:
    """判断文件类别并取出两侧版本号。

    返回 (kind, vue_version, json_version)，kind ∈ {'ok', SKIP_NO_JSON, SKIP_NO_PROVIDER}。
    """
    json_path = VTJ_FILES_DIR / f"{vue_path.stem}.json"
    if not json_path.exists():
        return SKIP_NO_JSON, None, None

    vue_version = extract_vue_version(vue_path)
    if not vue_version:
        return SKIP_NO_PROVIDER, None, extract_json_version(json_path)

    return 'ok', vue_version, extract_json_version(json_path)


def sync_single_file(vue_file: str, strict: bool = False) -> bool:
    """同步单个文件的版本号（同步模式）

    校验口径（与 check_only 对齐，避免手写页误报阻断 CI）：
    1. 存在配套 DSL JSON 且 Vue 能提取到 version：做一致性校验/自动同步；
    2. 无配套 JSON（纯手写页面）：跳过，不阻断；
    3. 有 JSON 但 Vue 无 useProvider version（历史页面）：跳过，不阻断。
    """
    vue_path = VTJ_VUE_DIR / vue_file
    if not vue_path.exists():
        print(f"⚠️  Vue 文件不存在: {vue_path}")
        return False
    kind, vue_version, json_version = classify(vue_path)
    if kind == SKIP_NO_JSON:
        # 纯手写页面没有 DSL 文件，不属于版本一致性管理范围，跳过不阻断
        print(f"⏭  跳过（无对应 JSON，非设计器页面）: {vue_path.stem}")
        return not strict
    if kind == SKIP_NO_PROVIDER:
        # 历史页面未声明 useProvider version，跳过不阻断
        print(f"⏭  跳过（Vue 无 useProvider 版本，非设计器页面）: {vue_path.stem}")
        return not strict

    if vue_version != json_version:
        print(f"🔄 版本不一致: {vue_path.stem}")
        print(f"   Vue:  {vue_version}")
        print(f"   JSON: {json_version}")
        if update_json_version(VTJ_FILES_DIR / f"{vue_path.stem}.json", vue_version):
            print(f"   ✅ 已同步 JSON 版本号")
            return True
        return False

    print(f"✅ 版本一致: {vue_path.stem}")
    return True


def run_all(check_only: bool = False, strict: bool = False) -> bool:
    """遍历 .vtj/vue 下全部 .vue，比对（必要时同步）版本号"""
    mode = '检查' if check_only else '同步'
    print(f"🔍 VTJ 版本一致性（{mode}模式）...")

    if not VTJ_VUE_DIR.exists():
        print(f"❌ Vue 目录不存在: {VTJ_VUE_DIR}")
        return False

    if not VTJ_FILES_DIR.exists():
        print(f"❌ Files 目录不存在: {VTJ_FILES_DIR}")
        return False

    vue_files = sorted(VTJ_VUE_DIR.glob('*.vue'))
    if not vue_files:
        print("⚠️  没有找到 .vue 文件")
        return True

    ok = synced = skipped = 0
    failures: list[str] = []
    skipped_names: list[str] = []

    for vue_path in vue_files:
        kind, vue_version, json_version = classify(vue_path)
        if kind == SKIP_NO_JSON:
            skipped += 1
            skipped_names.append(f"{vue_path.stem}（无 JSON）")
            print(f"⏭  跳过（无对应 JSON）: {vue_path.stem}")
            continue
        if kind == SKIP_NO_PROVIDER:
            skipped += 1
            skipped_names.append(f"{vue_path.stem}（无 useProvider）")
            print(f"⏭  跳过（Vue 无 useProvider 版本）: {vue_path.stem}")
            continue

        if vue_version == json_version:
            ok += 1
            print(f"✅ 版本一致: {vue_path.stem}")
            continue

        if check_only:
            failures.append(f"{vue_path.stem}: Vue={vue_version}, JSON={json_version}")
            print(f"❌ 版本不一致: {vue_path.stem}（Vue={vue_version} JSON={json_version}）")
            continue

        print(f"🔄 版本不一致: {vue_path.stem}")
        print(f"   Vue:  {vue_version}")
        print(f"   JSON: {json_version}")
        if update_json_version(VTJ_FILES_DIR / f"{vue_path.stem}.json", vue_version):
            synced += 1
            print("   ✅ 已同步 JSON 版本号")
        else:
            failures.append(f"{vue_path.stem}: 写入失败")

    print("")
    print(f"📊 设计器页面 {ok} 个一致、{synced} 个已同步、{len(failures)} 个失败；"
          f"非设计器页面跳过 {skipped} 个")

    if skipped_names and (strict or check_only):
        print("   跳过明细：" + "、".join(skipped_names))

    if failures:
        print("❌ 存在版本不一致，请运行: python scripts/vtj_version_sync.py")
        return False

    if strict and skipped:
        print("❌ --strict：文件名/页面上存在非设计器页面，需人工确认")
        return False

    print("✅ VTJ 设计器页面版本一致")
    return True


def main(argv: list[str]) -> int:
    check_only = '--check' in argv
    strict = '--strict' in argv
    files = [a for a in argv if not a.startswith('--')]

    if files:
        success = True
        for f in files:
            if not sync_single_file(f, strict=strict):
                success = False
        return 0 if success else 1

    return 0 if run_all(check_only=check_only, strict=strict) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
