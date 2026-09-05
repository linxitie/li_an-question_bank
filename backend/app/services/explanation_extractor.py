"""
答案解析提取服务: 支持多种格式提取
"""
import re
from typing import Optional, List, Dict, Union

# 解析格式模式
EXPLANATION_PATTERNS = [
    # 标准格式：解析：xxx / 答案解析：xxx
    r'解析[：:]\s*(.+?)(?=\n\n|\n(?:第|\d+[\.、])|\Z)',
    r'答案解析[：:]\s*(.+?)(?=\n\n|\n(?:第|\d+[\.、])|\Z)',
    r'详细解析[：:]\s*(.+?)(?=\n\n|\n(?:第|\d+[\.、])|\Z)',
    
    # 方括号格式：【解析】xxx / 【答案解析】xxx
    r'【解析】\s*(.+?)(?=\n\n|\n(?:第|\d+[\.、])|\Z)',
    r'【答案解析】\s*(.+?)(?=\n\n|\n(?:第|\d+[\.、])|\Z)',
    r'【详解】\s*(.+?)(?=\n\n|\n(?:第|\d+[\.、])|\Z)',
    
    # 括号格式：(解析)xxx
    r'\(解析\)\s*(.+?)(?=\n\n|\n(?:第|\d+[\.、])|\Z)',
    
    # 冒号后跟多行
    r'解析[:：]\s*\n(.+?)(?=\n\n|\n(?:第|\d+[\.、])|\Z)',
    r'答案解析[:：]\s*\n(.+?)(?=\n\n|\n(?:第|\d+[\.、])|\Z)',
]

# 答案模式（用于定位解析位置）
ANSWER_PATTERNS = [
    r'答案[：:]\s*[A-D](?:[,，\s]*[A-D])*',
    r'答案[：:]\s*(?:正确|错误|对|错)',
    r'参考答案[：:]\s*.+',
    r'正确答案[：:]\s*.+',
]

# 题号模式
QUESTION_NUMBER_PATTERNS = [
    r'第\s*\d+\s*题',
    r'^\s*\d+[\.、]\s',
    r'【\s*\d+\s*】',
    r'\(\s*\d+\s*\)',
]

def extract_explanation(content: str) -> str:
    """
    从题目内容中提取答案解析
    
    Args:
        content: 题目完整内容
        
    Returns:
        提取的解析文本，未找到返回空字符串
    """
    if not content:
        return ""
    
    # 尝试各种解析格式
    for pattern in EXPLANATION_PATTERNS:
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        if matches:
            # 取最长的匹配（最可能是完整解析）
            explanation = max(matches, key=len).strip()
            # 清理多余空白
            explanation = re.sub(r'\n\s*\n', '\n\n', explanation)
            explanation = re.sub(r'[ \t]+', ' ', explanation)
            return explanation.strip()
    
    return ""


def extract_explanation_from_structured(content: str, question_num: Optional[int] = None) -> str:
    """
    从结构化文档中提取特定题号的解析
    适用于答案在文档末尾统一列出的情况
    
    Args:
        content: 完整文档内容
        question_num: 题目编号（可选）
        
    Returns:
        解析文本
    """
    if not content:
        return ""
    
    # 如果指定题号，尝试定位该题的解析
    if question_num:
        # 查找 "第X题 解析" 或 "X. 解析" 等模式
        patterns = [
            rf'第\s*{question_num}\s*题\s*[：:]\s*(.+?)(?=\n\s*第\s*\d+\s*题|\n\n|\Z)',
            rf'^\s*{question_num}[\.、]\s*解析[：:]\s*(.+?)(?=\n\s*\d+[\.、]|\n\n|\Z)',
            rf'{question_num}[\.、]\s*(.+?)(?=\n\s*\d+[\.、]|\n\n|\Z)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL | re.MULTILINE | re.IGNORECASE)
            if match:
                return clean_explanation(match.group(1))
    
    # 否则使用通用提取
    return extract_explanation(content)


def extract_all_explanations(content: str) -> Dict[int, str]:
    """
    从文档中提取所有题目的解析，返回 {题号: 解析} 字典
    
    Args:
        content: 完整文档内容
        
    Returns:
        题号到解析的映射
    """
    explanations = {}
    
    # 模式：题号 + 解析内容
    # 例如：1. 解析：xxx / 1、解析：xxx / 第1题 解析：xxx
    pattern = r'(?:第\s*(\d+)\s*题|^\s*(\d+)[\.、])\s*(?:解析|答案解析|详解)[：:]\s*(.+?)(?=\n\s*(?:第\s*\d+\s*题|\d+[\.、])\s*(?:解析|答案解析|详解)|$)'
    
    matches = re.findall(pattern, content, re.DOTALL | re.MULTILINE | re.IGNORECASE)
    
    for match in matches:
        num_str = match[0] or match[1]
        if num_str:
            try:
                q_num = int(num_str)
                explanation = clean_explanation(match[2])
                if explanation:
                    explanations[q_num] = explanation
            except ValueError:
                continue
    
    return explanations


def clean_explanation(text: str) -> str:
    """清洗解析文本"""
    if not text:
        return ""
    
    # 移除多余空白
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    
    # 移除可能的题号前缀
    text = re.sub(r'^\s*\d+[\.、]\s*', '', text)
    text = re.sub(r'^第\s*\d+\s*题\s*[：:]\s*', '', text)
    
    return text.strip()


def extract_answer(content: str) -> str:
    """
    从内容中提取答案
    
    Args:
        content: 题目内容
        
    Returns:
        答案文本
    """
    if not content:
        return ""
    
    for pattern in ANSWER_PATTERNS:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(0).replace('答案：', '').replace('答案:', '').replace('参考答案：', '').replace('参考答案:', '').replace('正确答案：', '').replace('正确答案:', '').strip()
    
    return ""


def has_explanation(content: str) -> bool:
    """检查内容是否包含解析"""
    return bool(extract_explanation(content))


def generate_simple_explanation(question_content: str, answer: str, question_type: str) -> str:
    """
    为缺失解析的题目生成简单解析模板
    
    Args:
        question_content: 题目内容
        answer: 正确答案
        question_type: 题型
        
    Returns:
        简单解析模板
    """
    templates = {
        "单选题": f"本题考查相关知识点。正确答案为 {answer}。通过分析题干可知...",
        "多选题": f"本题考查相关知识点。正确答案为 {answer}。需逐项分析各选项...",
        "判断题": f"本题表述{'正确' if answer in ['正确','对','T','True','true'] else '错误'}。",
        "论述题": "本题要求论述相关观点。答题时应结合理论与实际...",
        "填空题": f"正确答案为 {answer}。",
        "简答题": "简要作答要点...",
        "案例分析题": "结合案例材料，运用相关理论分析...",
    }
    
    return templates.get(question_type, f"本题正确答案为 {answer}。解析待补充。")


def batch_extract_explanations(questions: List[Dict]) -> List[Dict]:
    """
    批量提取题目解析
    
    Args:
        questions: 题目列表，每项包含 content, question_content 等字段
        
    Returns:
        添加了 explanation 字段的题目列表
    """
    results = []
    for q in questions:
        content = q.get("content") or q.get("question_content", "")
        existing_explanation = q.get("answer_analysis") or q.get("explanation", "")
        
        if existing_explanation:
            # 已有解析，清洗后保留
            explanation = clean_explanation(existing_explanation)
        else:
            # 尝试从内容中提取
            explanation = extract_explanation(content)
            
            if not explanation:
                # 生成简单模板
                answer = extract_answer(content)
                q_type = q.get("type_name") or q.get("question_type", "单选题")
                explanation = generate_simple_explanation(content, answer, q_type)
        
        q_copy = q.copy()
        q_copy["explanation"] = explanation
        q_copy["has_original_explanation"] = bool(existing_explanation)
        results.append(q_copy)
    
    return results