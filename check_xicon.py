"""检查所有 .vue 文件中 XIcon 的使用和导入情况"""
import os
import glob

files = glob.glob(r'd:\砺安题库\砺安题库\.vtj\vue\*.vue')
print(f"共检查 {len(files)} 个 .vue 文件\n")
print(f"{'文件名':<40s} {'template有XIcon':<15s} {'导入了@vtj/ui':<15s} {'注册了XIcon':<12s} {'状态'}")
print("-" * 100)

for f in sorted(files):
    try:
        with open(f, encoding='utf-8') as fp:
            content = fp.read()

        basename = os.path.basename(f)
        template_part = content.split('<script')[0] if '<script' in content else content
        script_part = content.split('<script')[1] if '<script' in content else ''

        has_xicon_in_template = 'XIcon' in template_part or 'x-icon' in template_part.lower()
        has_vtj_ui_import = '@vtj/ui' in content
        has_xicon_registered = 'XIcon' in script_part and ('components' in script_part)

        if has_xicon_in_template:
            if not has_vtj_ui_import:
                status = "!!! 缺少 @vtj/ui 导入 !!!"
            elif not has_xicon_registered:
                status = "!!! XIcon 未在 components 注册 !!!"
            else:
                status = "OK"
            print(f"{basename:<40s} {str(has_xicon_in_template):<15s} {str(has_vtj_ui_import):<15s} {str(has_xicon_registered):<12s} {status}")
    except Exception as e:
        print(f"{basename:<40s} ERROR: {e}")
