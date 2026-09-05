"""
试卷检测服务: 标题解析、科目识别
"""
import re
from typing import Tuple

# 科目关键词库
SUBJECT_KEYWORDS = {
    "公安专业考试": ["公安", "警察", "执法", "警务", "公安机关", "人民警察",
                     "公安专业", "公安基础", "警务实务", "公安专业知识",
                     "治安管理", "刑事侦查", "行政执法", "基本警务能力"],
    "行政职业能力测验": ["行测", "行政职业", "能力测验", "判断推理", "数量关系",
                       "言语理解", "资料分析", "常识判断", "逻辑填空", "片段阅读"],
    "申论": ["申论", "写作", "论述", "归纳概括", "综合分析", "提出对策",
            "应用文写作", "议论文写作", "申论写作"],
    "公共基础知识": ["公基", "公共基础", "基础知识", "马原", "毛特", "思想道德", "法律基础"],
    "面试": ["面试", "结构化", "无领导小组", "情景模拟", "结构化面试"],
}

# 标题中常见的无效前缀/后缀
TITLE_NOISE_PATTERNS = [
    r'^UTB[a-f0-9]{16}\s*',  # 系统ID
    r'^第\s*\d+\s*[题套卷]\s*[：:]\s*',  # 第X题/第X套卷：
    r'^[\d\.\s]*',  # 开头的数字和点
    r'\s*[（(]\s*(含答案|含解析|带答案|带解析)\s*[）)]\s*$',  # 结尾的(含答案)
    r'\s*(试卷|试题|真题|模拟题|练习题)\s*$',  # 结尾的试卷/试题
]

def clean_exam_title(title: str) -> str:
    """清洗试卷标题，移除系统ID和无关前后缀"""
    if not title:
        return ""
    
    cleaned = title.strip()
    
    # 移除系统ID
    cleaned = re.sub(r'UTB[a-f0-9]{16}', '', cleaned)
    
    # 移除常见噪音模式
    for pattern in TITLE_NOISE_PATTERNS:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # 合并多余空格
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # 如果清洗后为空，返回原标题（去除ID后）
    if not cleaned:
        cleaned = re.sub(r'UTB[a-f0-9]{16}', '', title).strip()
    
    return cleaned


def extract_exam_name(title: str) -> str:
    """从标题中提取试卷名称"""
    cleaned = clean_exam_title(title)
    
    # 尝试提取核心名称：年份 + 考试名称 + 类型
    # 例如: "2024年公安专业考试真题" -> "2024年公安专业考试"
    patterns = [
        r'(\d{4}年.+?[考试测验真题])',  # 2024年xxx考试
        r'(\d{4}年.+?[专业科目])',       # 2024年xxx专业
        r'([^：:]+?[考试测验])',         # xxx考试/测验
        r'([^：:]+?专业考试)',           # xxx专业考试
    ]
    
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if match:
            return match.group(1).strip()
    
    return cleaned


def identify_subject(title: str, content: str = "") -> Tuple[str, float]:
    """
    识别试卷科目
    Returns: (subject_name, confidence)
    """
    if not title and not content:
        return "未知科目", 0.0
    
    scores = {}
    title_lower = title.lower()
    content_lower = content[:500].lower() if content else ""
    
    for subject, keywords in SUBJECT_KEYWORDS.items():
        # 标题匹配 (权重 0.7)
        title_score = sum(1 for kw in keywords if kw in title_lower)
        # 内容匹配 (权重 0.3)
        content_score = sum(1 for kw in keywords if kw in content_lower)
        
        total_score = title_score * 0.7 + content_score * 0.3
        scores[subject] = total_score
    
    if not scores or max(scores.values()) == 0:
        return "未知科目", 0.0
    
    best_subject = max(scores.keys(), key=lambda k: scores[k])
    max_score = scores[best_subject]
    
    # 置信度归一化 (假设最高可能得分为 3)
    confidence = min(max_score / 3.0, 1.0)
    
    return best_subject, round(confidence, 2)


def detect_exam_info(title: str, content: str = "") -> dict:
    """
    综合检测试卷信息
    Returns: {
        "name": str,
        "subject": str,
        "confidence": float,
        "original_title": str
    }
    """
    return {
        "name": extract_exam_name(title),
        "subject": identify_subject(title, content)[0],
        "confidence": identify_subject(title, content)[1],
        "original_title": title
    }