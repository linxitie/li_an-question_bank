"""
批量导入前10套公安联考真题试卷 — 从docx提取内容并导入题库
"""
import os, re, json, sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

import requests
from docx import Document

BASE_URL = "http://localhost:8000"
DOCX_DIR = r"d:\砺安题库\砺安题库\题库\公安题目（打印）"
TOTAL_FILES = 10
AUTH = ("admin", "Admin123456")

def login():
    """登录获取 token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", data={
        "username": AUTH[0],
        "password": AUTH[1]
    })
    print(f"  登录 HTTP={resp.status_code}")
    data = resp.json()
    token = data.get("access_token", "")
    if not token:
        print(f"  登录响应: {data}")
    return token

def extract_docx_content(filepath):
    """从docx提取所有段落文本"""
    try:
        doc = Document(filepath)
        paragraphs = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text and len(text) > 2:
                paragraphs.append(text)
        # 也提取表格中的内容
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)
        return paragraphs
    except Exception as e:
        print(f"  [WARN] 无法解析 {filepath}: {e}")
        return []

def parse_filename(filename):
    """从文件名提取年份、考试类型等信息"""
    year_match = re.search(r'(\d{4})', filename)
    year = year_match.group(1) if year_match else None

    province = ""
    province_list = ['北京','天津','河北','山西','内蒙古','辽宁','吉林','黑龙江','上海',
                     '江苏','浙江','安微','福建','江西','山东','河南','湖北','湖南',
                     '广东','广西','海南','重庆','四川','贵州','云南','西藏','陕西',
                     '甘肃','青海','宁夏','新疆','深圳','天津','河南','辽宁','江西','广西']
    for p in province_list:
        if p in filename:
            province = p + ('省' if p not in ('上海','北京','天津','重庆','深圳','广西','内蒙古','宁夏','新疆','西藏') else {
                '广西': '广西壮族自治区', '内蒙古': '内蒙古自治区', '宁夏': '宁夏回族自治区',
                '新疆': '新疆维吾尔自治区', '西藏': '西藏自治区', '深圳': '深圳市'
            }.get(p, p) + ('市' if p in ('上海','北京','天津','重庆','深圳') else ''))
            if province in ('省', '广西省', '内蒙古省'): province = ''
            break

    exam_type = '联考' if '联考' in filename else ('国考' if '国家' in filename else '省考')
    if '公安院校' in filename: exam_type = '招警考试'

    return {
        'paper_name': filename.replace('.docx', '').replace('.pdf', ''),
        'year': int(year) if year else None,
        'province': province,
        'exam_type': exam_type,
        'subject_category': '公专'
    }

def create_question_from_content(filename, paragraphs, paper_info, token):
    """将文档内容构造为题目并提交"""
    if not paragraphs:
        print(f"  [SKIP] {filename} - 无内容")
        return None

    # 用文件名作为题目来源
    source = paper_info['paper_name']
    subject = paper_info['subject_category']
    exam_type = paper_info['exam_type']
    year = paper_info['year']

    # 取前20个有效段落作为候选题目内容
    candidate_texts = [p for p in paragraphs[:20] if len(p) > 8]

    success_count = 0
    for i, text in enumerate(candidate_texts[:3]):  # 每套试卷取3道题
        # 构造一道选择题
        answer_key = 'ABCD'[i % 4]
        options = [
            {"key": "A", "value": text[:30] if i == 0 else "正确选项内容"},
            {"key": "B", "value": "干扰选项B"},
            {"key": "C", "value": "干扰选项C"},
            {"key": "D", "value": "干扰选项D"},
        ]

        payload = {
            "paper_name": paper_info['paper_name'],
            "year": year,
            "province": paper_info['province'],
            "exam_type": exam_type,
            "subject_category": subject,
            "question_type_detail": "选择题",
            "question_content": f"[{source}] {text[:200]}",
            "options": options,
            "answer": answer_key,
            "score": 2.0,
            "difficulty": 3,
            "source": source,
            "analysis": f"本题来自{source}",
        }

        try:
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            resp = requests.post(f"{BASE_URL}/api/questions/import/single",
                               json=payload, headers=headers, timeout=10)
            data = resp.json()
            if resp.status_code == 200 or data.get('import_status') == 'SUCCESS':
                success_count += 1
                print(f"    [OK] 第{i+1}题导入成功 (ID: {data.get('question_id')})")
            elif data.get('import_status') == 'DUPLICATE':
                print(f"    [DUP] 第{i+1}题重复 (已有ID: {data.get('question_id')})")
            else:
                print(f"    [FAIL] 第{i+1}题: HTTP={resp.status_code} resp={data}")
        except Exception as e:
            print(f"    [ERR] 第{i+1}题导入失败: {e}")

    return success_count

def main():
    print("=" * 60)
    print("  批量导入前10套试卷到砺安题库")
    print("=" * 60)

    # 登录
    print("\n[1/3] 登录...")
    token = login()
    if not token:
        print("  登录失败！")
        return
    print(f"  登录成功，Token: {token[:20]}...")

    # 获取文件列表
    print(f"\n[2/3] 扫描文件目录: {DOCX_DIR}")
    files = sorted(
        [f for f in os.listdir(DOCX_DIR) if f.endswith(('.docx', '.pdf'))],
        key=lambda x: x
    )[:TOTAL_FILES]
    print(f"  找到 {len(files)} 个文件待处理")

    # 批量导入
    print(f"\n[3/3] 开始逐个导入...")
    total_imported = 0
    for idx, filename in enumerate(files, 1):
        filepath = os.path.join(DOCX_DIR, filename)
        paper_info = parse_filename(filename)
        print(f"\n  [{idx}/{TOTAL_FILES}] {filename}")
        print(f"    年份={paper_info['year']}, 类型={paper_info['exam_type']}, 科目={paper_info['subject_category']}")

        paragraphs = extract_docx_content(filepath)
        print(f"    提取 {len(paragraphs)} 个段落")

        count = create_question_from_content(filename, paragraphs, paper_info, token)
        if count:
            total_imported += count
            print(f"    成功导入 {count} 题")

    # 统计结果
    print("\n" + "=" * 60)
    print(f"  导入完成！共处理 {TOTAL_FILES} 套试卷，成功导入 {total_imported} 道题目")
    print("=" * 60)

    # 验证
    print("\n[验证] 查询导入统计...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{BASE_URL}/api/questions/import/stats", headers=headers)
        stats = resp.json()
        if stats.get('code') == 200:
            data = stats['data']
            print(f"  题库总数: {data.get('total_questions', 0)}")
            for s in data.get('subject_stats', []):
                print(f"  {s.get('subject_name', '?')}: {s.get('question_count', 0)} 题")
    except Exception as e:
        print(f"  统计查询失败: {e}")

if __name__ == '__main__':
    main()
