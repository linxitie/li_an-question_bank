#!/usr/bin/env python3
"""
VTJ 版本同步脚本
用于在修改 .vtj/vue/*.vue 后自动同步 .vtj/files/*.json 的 __VERSION__
以及确保 useProvider({version}) 与 JSON 版本号一致
"""

import json
import re
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
VTJ_VUE_DIR = PROJECT_ROOT / '.vtj' / 'vue'
VTJ_FILES_DIR = PROJECT_ROOT / '.vtj' / 'files'


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


def sync_single_file(vue_file: str) -> bool:
    """同步单个文件的版本号"""
    vue_path = VTJ_VUE_DIR / vue_file
    if not vue_path.exists():
        print(f"⚠️  Vue 文件不存在: {vue_path}")
        return False
    
    # 对应的 JSON 文件
    json_path = VTJ_FILES_DIR / f"{vue_path.stem}.json"
    if not json_path.exists():
        print(f"⚠️  JSON 文件不存在: {json_path}")
        return False
    
    vue_version = extract_vue_version(vue_path)
    json_version = extract_json_version(json_path)
    
    if not vue_version:
        print(f"⚠️  无法从 Vue 提取版本: {vue_path}")
        return False
    
    if vue_version != json_version:
        print(f"🔄 版本不一致: {vue_path.stem}")
        print(f"   Vue:  {vue_version}")
        print(f"   JSON: {json_version}")
        
        # 自动同步 JSON 版本号
        if update_json_version(json_path, vue_version):
            print(f"   ✅ 已同步 JSON 版本号")
            return True
        else:
            return False
    else:
        print(f"✅ 版本一致: {vue_path.stem}")
        return True


def sync_all() -> bool:
    """同步所有 VTJ 文件的版本号"""
    print("🔍 检查 VTJ 版本一致性...")
    
    if not VTJ_VUE_DIR.exists():
        print(f"❌ Vue 目录不存在: {VTJ_VUE_DIR}")
        return False
    
    if not VTJ_FILES_DIR.exists():
        print(f"❌ Files 目录不存在: {VTJ_FILES_DIR}")
        return False
    
    vue_files = list(VTJ_VUE_DIR.glob('*.vue'))
    if not vue_files:
        print("⚠️  没有找到 .vue 文件")
        return True
    
    success = True
    for vue_file in vue_files:
        if not sync_single_file(vue_file.name):
            success = False
    
    if success:
        print("\n✅ 所有 VTJ 版本一致")
    else:
        print("\n❌ 部分文件版本同步失败")
    
    return success


def check_only() -> bool:
    """仅检查不修改（用于 CI）"""
    print("🔍 CI 检查 VTJ 版本一致性...")
    
    if not VTJ_VUE_DIR.exists():
        print(f"❌ Vue 目录不存在: {VTJ_VUE_DIR}")
        return False
    
    vue_files = list(VTJ_VUE_DIR.glob('*.vue'))
    errors = []
    
    for vue_file in vue_files:
        json_path = VTJ_FILES_DIR / f"{vue_file.stem}.json"
        if not json_path.exists():
            continue
        
        vue_version = extract_vue_version(vue_file)
        json_version = extract_json_version(json_path)
        
        if vue_version and json_version and vue_version != json_version:
            errors.append(f"{vue_file.name}: Vue={vue_version}, JSON={json_version}")
    
    if errors:
        print("❌ VTJ版本不一致:")
        for e in errors:
            print(f"  {e}")
        print("\n请运行: python scripts/vtj_version_sync.py")
        return False
    
    print("✅ 所有VTJ版本一致")
    return True


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # 同步指定文件
        for f in sys.argv[1:]:
            sync_single_file(f)
    else:
        # 同步所有文件
        if not sync_all():
            sys.exit(1)