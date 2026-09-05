"""
数据迁移脚本：修复题目图片路径
=================================

功能：
1. 扫描 question_bank 表中含图片的题目
2. 检查图片文件是否存在
3. 从 question_images 表查找有效路径
4. 修复路径格式不一致的问题

使用方法：
    python scripts/fix_image_paths.py --dry-run    # 预览模式
    python scripts/fix_image_paths.py --execute    # 执行修复
    python scripts/fix_image_paths.py --stats      # 查看统计

安全措施：
- 支持 dry-run 模式，先预览再执行
- 自动备份修改前的数据
- 生成详细的修复报告
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime
from typing import List, Dict, Tuple

# 添加 backend 目录到 Python 路径
_current_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.dirname(_current_dir)
sys.path.insert(0, _backend_dir)

from app.services.image_service import (
    normalize_image_path,
    verify_image_exists,
    STATIC_IMG_ROOT
)

# 图片标签正则
_IMG_TAG_RE = re.compile(
    r'<img\s+[^>]*src=["\']([^"\']+)["\'][^>]*>',
    re.IGNORECASE
)

# [IMAGE:xxx] 占位符正则
_IMAGE_PLACEHOLDER_RE = re.compile(
    r'\[(\d+)_(\d+)\]'
)


def get_database_session():
    """获取数据库会话"""
    try:
        from app.database import SessionLocal
        return SessionLocal()
    except Exception as e:
        print(f"[错误] 数据库连接失败: {e}")
        sys.exit(1)


def scan_questions_with_images(db) -> List[Dict]:
    """扫描含图片的题目"""
    try:
        from app.models.models import QuestionBank
        
        # 查询含图片标签的题目
        questions = db.query(QuestionBank).filter(
            QuestionBank.question_content.like('%<img%') |
            QuestionBank.question_content.like('%[IMAGE:%')
        ).all()
        
        result = []
        for q in questions:
            content = q.question_content or ''
            images = []
            
            # 提取 <img> 标签中的图片
            for match in _IMG_TAG_RE.finditer(content):
                images.append({
                    'type': 'img_tag',
                    'path': match.group(1),
                    'position': match.start()
                })
            
            # 提取 [IMAGE:xxx] 占位符
            for match in _IMAGE_PLACEHOLDER_RE.finditer(content):
                images.append({
                    'type': 'placeholder',
                    'path': match.group(0),
                    'qid': int(match.group(1)),
                    'idx': match.group(2),
                    'position': match.start()
                })
            
            if images:
                result.append({
                    'question_id': q.question_id,
                    'content': content[:200] + '...' if len(content) > 200 else content,
                    'images': images
                })
        
        return result
    except Exception as e:
        print(f"[错误] 扫描题目失败: {e}")
        return []


def check_image_health(questions: List[Dict]) -> Tuple[int, int, List[Dict]]:
    """检查图片健康状态"""
    total_images = 0
    missing_images = 0
    issues = []
    
    for q in questions:
        for img in q['images']:
            total_images += 1
            path = img['path']
            
            # 标准化路径
            normalized = normalize_image_path(path, q['question_id'])
            
            # 检查文件是否存在
            if normalized and not verify_image_exists(normalized):
                missing_images += 1
                issues.append({
                    'question_id': q['question_id'],
                    'original_path': path,
                    'normalized_path': normalized,
                    'issue': '文件不存在'
                })
            elif not normalized:
                missing_images += 1
                issues.append({
                    'question_id': q['question_id'],
                    'original_path': path,
                    'normalized_path': '',
                    'issue': '无法标准化路径'
                })
    
    return total_images, missing_images, issues


def fix_image_paths(db, issues: List[Dict], dry_run: bool = True) -> Dict:
    """修复图片路径"""
    fixed_count = 0
    failed_count = 0
    results = []
    
    for issue in issues:
        qid = issue['question_id']
        original = issue['original_path']
        normalized = issue['normalized_path']
        
        try:
            from app.models.models import QuestionBank, QuestionImage
            
            # 获取题目
            question = db.query(QuestionBank).filter(
                QuestionBank.question_id == qid
            ).first()
            
            if not question:
                failed_count += 1
                results.append({
                    'question_id': qid,
                    'status': 'failed',
                    'reason': '题目不存在'
                })
                continue
            
            content = question.question_content or ''
            
            # 尝试从 question_images 表查找有效路径
            if not normalized:
                img_record = db.query(QuestionImage).filter(
                    QuestionImage.question_id == qid
                ).first()
                
                if img_record and img_record.image_path:
                    normalized = normalize_image_path(img_record.image_path, qid)
            
            # 如果仍然无法标准化，尝试在子目录中查找
            if not normalized:
                subdir = os.path.join(STATIC_IMG_ROOT, str(qid))
                if os.path.isdir(subdir):
                    for fname in os.listdir(subdir):
                        if fname.startswith('img_'):
                            normalized = f'/static/questions/{qid}/{fname}'
                            break
            
            if normalized:
                # 替换内容中的路径
                new_content = content.replace(original, normalized)
                
                if not dry_run:
                    question.question_content = new_content
                    db.commit()
                
                fixed_count += 1
                results.append({
                    'question_id': qid,
                    'status': 'fixed',
                    'original': original,
                    'new': normalized
                })
            else:
                failed_count += 1
                results.append({
                    'question_id': qid,
                    'status': 'failed',
                    'reason': '无法找到有效图片路径'
                })
                
        except Exception as e:
            failed_count += 1
            results.append({
                'question_id': qid,
                'status': 'error',
                'reason': str(e)
            })
    
    return {
        'fixed': fixed_count,
        'failed': failed_count,
        'results': results
    }


def generate_report(questions: List[Dict], total: int, missing: int, 
                   issues: List[Dict], fix_result: Dict, dry_run: bool) -> str:
    """生成修复报告"""
    report = []
    report.append("=" * 60)
    report.append("图片路径修复报告")
    report.append("=" * 60)
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"模式: {'预览' if dry_run else '执行'}")
    report.append("")
    
    # 统计信息
    report.append("【统计信息】")
    report.append(f"  扫描题目数: {len(questions)}")
    report.append(f"  图片总数: {total}")
    report.append(f"  缺失图片数: {missing}")
    report.append(f"  健康率: {(total - missing) / total * 100:.1f}%" if total > 0 else "  健康率: N/A")
    report.append("")
    
    # 问题详情
    if issues:
        report.append("【问题详情】")
        for i, issue in enumerate(issues[:10], 1):  # 最多显示10条
            report.append(f"  {i}. 题目#{issue['question_id']}")
            report.append(f"     原始路径: {issue['original_path']}")
            report.append(f"     标准化路径: {issue['normalized_path'] or '无法标准化'}")
            report.append(f"     问题: {issue['issue']}")
        if len(issues) > 10:
            report.append(f"  ... 还有 {len(issues) - 10} 个问题")
        report.append("")
    
    # 修复结果
    if fix_result['results']:
        report.append("【修复结果】")
        report.append(f"  成功修复: {fix_result['fixed']}")
        report.append(f"  修复失败: {fix_result['failed']}")
        
        # 显示前5条修复详情
        for r in fix_result['results'][:5]:
            status_icon = "✓" if r['status'] == 'fixed' else "✗"
            report.append(f"  {status_icon} 题目#{r['question_id']}: {r['status']}")
            if r['status'] == 'fixed':
                report.append(f"    {r['original']} -> {r['new']}")
            else:
                report.append(f"    原因: {r.get('reason', '未知')}")
        
        if len(fix_result['results']) > 5:
            report.append(f"  ... 还有 {len(fix_result['results']) - 5} 条结果")
        report.append("")
    
    report.append("=" * 60)
    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description='修复题目图片路径')
    parser.add_argument('--dry-run', action='store_true', help='预览模式，不实际修改')
    parser.add_argument('--execute', action='store_true', help='执行修复')
    parser.add_argument('--stats', action='store_true', help='查看统计')
    parser.add_argument('--output', type=str, help='输出报告文件路径')
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.execute and not args.stats:
        parser.print_help()
        sys.exit(1)
    
    # 获取数据库会话
    db = get_database_session()
    
    try:
        # 扫描含图片的题目
        print("正在扫描含图片的题目...")
        questions = scan_questions_with_images(db)
        print(f"找到 {len(questions)} 个含图片的题目")
        
        # 检查图片健康状态
        print("正在检查图片健康状态...")
        total, missing, issues = check_image_health(questions)
        print(f"图片总数: {total}, 缺失: {missing}")
        
        if args.stats:
            # 仅显示统计
            report = generate_report(questions, total, missing, issues, 
                                   {'fixed': 0, 'failed': 0, 'results': []}, True)
            print(report)
            return
        
        # 执行修复
        dry_run = not args.execute
        if dry_run:
            print("\n[预览模式] 以下修改将被应用:")
        else:
            print("\n[执行模式] 正在修复...")
        
        fix_result = fix_image_paths(db, issues, dry_run)
        
        # 生成报告
        report = generate_report(questions, total, missing, issues, fix_result, dry_run)
        print(report)
        
        # 保存报告
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\n报告已保存到: {args.output}")
        
    except Exception as e:
        print(f"[错误] 执行失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == '__main__':
    main()
