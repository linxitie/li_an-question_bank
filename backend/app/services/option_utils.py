"""
选项数据规范化工具模块
统一处理所有API端点的options字段，解决以下问题：
1. 双编码JSON字符串（99条历史数据）
2. 选项缺失（不足A/B/C/D四项）
3. 选项乱序
4. IMAGE:占位符未转换

设计目标：
- 输入任意格式 → 输出标准化 [{key, value}] 格式
- 所有API端点统一调用，一处修复全局生效
- 性能：简单数据O(n)，双编码数据需额外json.loads
"""
import json
import logging
import re
from typing import List, Dict, Any, Union, Optional

logger = logging.getLogger(__name__)

# IMAGE:占位符正则 — 支持 uuid_x_y / x_y 两种格式
_IMG_RE = re.compile(r'\[?IMAGE:([a-f0-9]+_\d+_\d+|\d+_\d+)\]?', re.IGNORECASE)

# 标准选项标签
_STANDARD_LABELS = ['A', 'B', 'C', 'D', 'E', 'F']


def render_image_placeholder(text: str, owner: str = 'questions') -> str:
    """将 IMAGE:X_Y / IMAGE:uuid_X_Y 占位符转为 img 标签（已由 image_service 预检）

    Args:
        text: 含占位符的文本
        owner: 图片所属目录，'questions'（默认）或 'question-groups'
    """
    if not text or not isinstance(text, str):
        return str(text) if text else ''

    def _replace(m):
        marker = m.group(1)
        # 统一使用扁平路径作为初始 src，由 image_service.sanitize_* 做存在性预检和兜底
        return f'<img src="/static/{owner}/{marker}.png" class="q-img" loading="lazy" />'

    return _IMG_RE.sub(_replace, text)


def is_subjective_question(question, qtype=None) -> bool:
    """以 question_type.is_objective=0 为唯一判据；不使用 options 是否为空猜测。"""
    qt = qtype if qtype is not None else getattr(question, "type", None)
    return bool(qt is not None and getattr(qt, "is_objective", 1) == 0)


def normalize_options(
    raw_options: Any,
    question_content: str = '',
    pad_to: int = 4,
    render_images: bool = True,
) -> List[Dict[str, str]]:
    """
    将任意格式的options规范化为 [{key: "A", value: "..."}] 格式。

    Args:
        raw_options: 原始options数据（可能是list/dict/str/None）
        question_content: 题目内容（用于从题干提取缺失选项）
        pad_to: 最少选项数（默认4，即A/B/C/D）
        render_images: 是否将IMAGE占位符转为img标签

    Returns:
        标准化后的选项列表，每个元素为 {key, value}，按key排序
    """
    # Step 0: 空值处理
    if raw_options is None:
        return _build_default_options(pad_to)

    # Step 1: 类型检测与解析
    opts = _parse_to_list(raw_options)

    if not opts:
        return _build_default_options(pad_to)

    # Step 2: 逐元素规范化
    normalized = []
    seen_keys = set()

    for item in opts:
        result = _normalize_item(item, render_images)
        if result:
            key = result['key']
            if key in seen_keys:
                continue  # 去重
            seen_keys.add(key)
            normalized.append(result)

    # Step 3: 补全缺失的标准标签
    existing_labels = {o['key'] for o in normalized}
    for label in _STANDARD_LABELS[:pad_to]:
        if label not in existing_labels:
            # 尝试从题干提取
            extracted = _extract_option_from_content(question_content, label)
            if extracted:
                if render_images:
                    extracted = render_image_placeholder(extracted)
                normalized.append({'key': label, 'value': extracted})
            else:
                normalized.append({'key': label, 'value': '(待补充)'})

    # Step 4: 仅保留标准标签（过滤非法key），按key排序
    filtered = [o for o in normalized if o['key'] in _STANDARD_LABELS[:max(pad_to, 6)]]
    filtered.sort(key=lambda x: x['key'])

    return filtered[:max(pad_to, 6)]


def _parse_to_list(raw: Any) -> List[Any]:
    """
    将原始数据解析为列表。
    处理三种情况：原生list、JSON字符串、双编码JSON字符串
    """
    if isinstance(raw, list):
        return raw

    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped or stripped == '[]':
            return []

        # 尝试递归解析（最多3层，处理双/三编码）
        parsed = stripped
        for depth in range(3):
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, str):
                try:
                    parsed = json.loads(parsed)
                except (json.JSONDecodeError, TypeError):
                    # 解析失败，尝试将整个字符串作为单个选项
                    return [{'key': 'A', 'value': stripped}]
        if isinstance(parsed, list):
            return parsed
        # 最终回退
        return [{'key': 'A', 'value': str(parsed)}]

    # 其他类型 → 转为字符串
    return [{'key': 'A', 'value': str(raw)}]


def _normalize_item(item: Any, render_images: bool) -> Optional[Dict[str, str]]:
    """
    将单个选项元素规范化为 {key, value}。
    支持：dict(with key/value/text)、string
    """
    if isinstance(item, dict):
        key = str(item.get('key', '')).strip().upper()
        # 提取value：优先value字段，其次text字段
        value = item.get('value')
        if value is None or (isinstance(value, str) and not value.strip()):
            value = item.get('text', '')
        if value is None:
            value = ''

        # 如果value本身是dict或list（极端情况），转为JSON字符串
        if isinstance(value, (dict, list)):
            try:
                value = json.dumps(value, ensure_ascii=False)
            except (TypeError, ValueError):
                value = str(value)

        value = str(value)
        if render_images:
            value = render_image_placeholder(value)

        # 只有key是有效标签(A-F)才保留
        if key in _STANDARD_LABELS:
            return {'key': key, 'value': value}
        elif key:
            # 有key但不是标准标签，用第一个字符作为key
            first_char = key[0] if key else '?'
            if first_char in _STANDARD_LABELS:
                return {'key': first_char, 'value': value}
        return None

    if isinstance(item, str):
        # 纯字符串：尝试解析为 "{key}. {value}" 格式
        match = re.match(r'^([A-F])[\.\、\s]\s*(.+)', item.strip(), re.IGNORECASE)
        if match:
            key = match.group(1).upper()
            value = match.group(2).strip()
            if render_images:
                value = render_image_placeholder(value)
            return {'key': key, 'value': value}
        # 无法解析，用索引自动分配key（调用方处理）
        return {'key': '', 'value': item}

    # 其他类型
    return {'key': '', 'value': str(item)}


_STANDARD_LABELS_STR = 'ABCDEF'


def _build_default_options(pad_to: int = 4) -> List[Dict[str, str]]:
    """构建默认空选项"""
    return [{'key': label, 'value': '(待补充)'} for label in _STANDARD_LABELS[:pad_to]]


def _extract_option_from_content(content: str, label: str) -> str:
    """从题干文本中提取指定标签的选项内容"""
    if not content:
        return ''
    # 匹配模式: A. xxx 或 A、xxx 或 (A) xxx
    patterns = [
        rf'{re.escape(label)}[\.\、\）\)]\s*(.+?)(?=[{_STANDARD_LABELS_STR}][\.\、\）\)]|\Z)',
        rf'(?<!\w){re.escape(label)}\s+(.+?)(?=\s*[{_STANDARD_LABELS_STR}]\s|\Z)',
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1).strip()
            # 截取到下一个标签或50字符
            return text[:100]
    return ''
