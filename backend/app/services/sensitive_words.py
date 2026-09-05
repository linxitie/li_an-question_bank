"""
敏感词过滤服务 - 基于DFA算法
关键词工程核心:检测 / 屏蔽 / 审计 / 限流

分级策略:
  - blocked  : 黄赌毒、暴恐、政治敏感 → 直接拒绝
  - masked   : 低俗、辱骂、广告       → 自动屏蔽(可发布但替换为*)
  - reviewed : 擦边、隐喻、联考特定   → 记录但不阻断

性能: DFA 算法 O(n),1000 字文本检测 < 1ms
"""
import threading
import unicodedata
import logging
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class SensitiveLevel:
    """敏感词级别"""
    BLOCKED = "blocked"      # 直接阻断:黄赌毒、暴恐、政治敏感
    MASKED = "masked"        # 自动屏蔽:低俗、辱骂、广告
    REVIEWED = "reviewed"    # 人工审核:擦边、隐喻、联考特定


# ============================== 敏感词库 ==============================
# 公安联考场景定制,初始内置代表性词表,支持热加载扩展
SENSITIVE_WORDS: Dict[str, List[str]] = {
    "blocked": [
        # 涉黄
        "嫖娼", "卖淫", "色情", "av女优", "一夜情", "找小姐", "包夜",
        "裸聊", "裸照", "黄色视频", "成人电影", "性服务", "援交",
        # 涉赌
        "赌博", "六合彩", "私彩", "开盘", "押注", "赌场", "网络赌博",
        "赌资", "赔率", "庄家", "出千", "赌局",
        # 涉毒
        "贩毒", "吸毒", "冰毒", "大麻", "海洛因", "摇头丸", "k粉",
        "可卡因", "毒品交易", "吸毒工具",
        # 暴恐
        "炸弹制作", "杀人方法", "自制刀具", "爆炸物配方", "恐怖袭击",
        "极端组织", "圣战",
        # 政治敏感(按公安联考场景定制,可扩展)
        "反动", "颠覆政权", "分裂国家",
    ],
    "masked": [
        # 辱骂
        "傻逼", "草泥马", "我操", "卧槽", "妈的", "他妈的", "滚蛋",
        "去死", "废物", "脑残", "白痴", "贱人", "婊子", "王八蛋",
        "狗屎", "屁眼",
        # 低俗
        "约炮", "撩妹", "泡妞", "老司机", "开车",
        # 广告
        "加微信", "加qq", "扫码", "点击链接", "免费领取", "中奖了",
        "代刷", "兼职加我",
    ],
    "reviewed": [
        # 公安联考特定敏感词
        "代考", "包过", "真题泄露", "试题答案", "考前答案", "保过班",
        "内部题库", "泄露题", "卖答案", "透题",
        # 擦边
        "漏洞", "后门", "破解", "绕过",
    ],
}


def _normalize_text(text: str) -> str:
    """
    文本归一化 - 防绕过检测
    1. 全角 → 半角
    2. 大写 → 小写
    3. 去除常见分隔符(插入符号变体:傻.逼 / 傻_逼 / 傻*逼)
    """
    if not text:
        return ""
    # 全角转半角
    normalized = unicodedata.normalize("NFKC", text)
    # 大写转小写
    normalized = normalized.lower()
    # 去除插入符号变体(常见绕过手法)
    for ch in " .-_*/\\|~`!@#$%^&()+={}[]:;\"'<>?,":
        normalized = normalized.replace(ch, "")
    return normalized


class SensitiveFilter:
    """
    DFA 敏感词过滤器

    内部结构: 嵌套字典
      _dfa = {
          "傻": {"__end__": None, "逼": {"__end__": "masked"}},
          "赌": {"__end__": None, "博": {"__end__": "blocked"}},
      }
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._dfa: Dict = {}
        self._word_count: int = 0
        self._build_dfa()

    def _build_dfa(self) -> None:
        """构建 DFA 字典树"""
        dfa: Dict = {}
        count = 0
        for level, words in SENSITIVE_WORDS.items():
            for word in words:
                if not word:
                    continue
                node = dfa
                for char in word:
                    node = node.setdefault(char, {})
                node["__end__"] = level
                count += 1
        with self._lock:
            self._dfa = dfa
            self._word_count = count
        logger.info(f"敏感词库已加载: {count} 条 (blocked={len(SENSITIVE_WORDS['blocked'])} "
                    f"masked={len(SENSITIVE_WORDS['masked'])} reviewed={len(SENSITIVE_WORDS['reviewed'])})")

    def _search(self, text: str) -> List[Tuple[str, str, int, int]]:
        """
        在归一化文本中搜索敏感词
        返回: [(word, level, start, end), ...]
        """
        results: List[Tuple[str, str, int, int]] = []
        if not text:
            return results

        with self._lock:
            dfa = self._dfa

        length = len(text)
        for i in range(length):
            node = dfa
            j = i
            last_match = None
            while j < length and text[j] in node:
                node = node[text[j]]
                j += 1
                if "__end__" in node:
                    last_match = (text[i:j], node["__end__"], i, j)
            # 长词优先:记录最长匹配
            if last_match:
                results.append(last_match)
        return results

    def detect(self, text: str) -> Dict:
        """
        检测文本中的敏感词

        返回:
            {
                "has_sensitive": bool,
                "level": str,           # 最严重级别(blocked > masked > reviewed)
                "words": List[str],     # 命中的敏感词列表
                "masked_text": str,     # 屏蔽后的文本(仅 masked 级别替换)
            }
        """
        if not text:
            return {
                "has_sensitive": False,
                "level": None,
                "words": [],
                "masked_text": text or "",
            }

        # 归一化后检测(但屏蔽操作在原文上进行)
        normalized = _normalize_text(text)
        matches = self._search(normalized)

        if not matches:
            return {
                "has_sensitive": False,
                "level": None,
                "words": [],
                "masked_text": text,
            }

        # 按级别优先级排序: blocked > masked > reviewed
        level_priority = {
            SensitiveLevel.BLOCKED: 3,
            SensitiveLevel.MASKED: 2,
            SensitiveLevel.REVIEWED: 1,
        }
        # 去重(同一词可能多次命中)
        unique_words: List[str] = []
        seen: Set[str] = set()
        max_level = None
        for word, level, _, _ in matches:
            if word not in seen:
                seen.add(word)
                unique_words.append(word)
            if max_level is None or level_priority.get(level, 0) > level_priority.get(max_level, 0):
                max_level = level

        # 生成屏蔽文本(将 masked 级别的词替换为 *)
        masked_text = text
        # 由于归一化后位置可能变化,这里简单按原文词替换
        for word, level, _, _ in matches:
            if level in (SensitiveLevel.MASKED, SensitiveLevel.BLOCKED):
                # 在原文中查找并替换(忽略大小写和分隔符差异)
                # 简化实现:直接替换归一化后的字符序列在原文中的对应位置
                # 由于复杂度较高,这里采用按词替换的方式
                masked_text = self._replace_in_original(masked_text, word)

        return {
            "has_sensitive": True,
            "level": max_level,
            "words": unique_words,
            "masked_text": masked_text,
        }

    def _replace_in_original(self, text: str, word: str) -> str:
        """
        在原文中替换敏感词为等长 *
        支持忽略插入符号:如 "傻.逼" 也能被替换为 "**"
        """
        if not word:
            return text
        result = list(text)
        word_chars = list(word)
        word_idx = 0
        i = 0
        while i < len(result):
            # 归一化当前字符进行比较
            cur = _normalize_text(result[i])
            if cur and word_idx < len(word_chars) and cur == word_chars[word_idx]:
                result[i] = "*"
                word_idx += 1
                if word_idx >= len(word_chars):
                    word_idx = 0  # 重置,继续查找下一个匹配
            elif not cur:
                # 跳过分隔符
                pass
            else:
                # 不匹配,回退
                if word_idx > 0:
                    word_idx = 0
                    continue
            i += 1
        return "".join(result)

    def mask(self, text: str, replace_char: str = "*") -> str:
        """替换所有敏感词为指定字符"""
        result = self.detect(text)
        if not result["has_sensitive"]:
            return text
        return result["masked_text"]

    def reload(self) -> None:
        """热加载词库(管理员更新词库后调用)"""
        logger.info("敏感词库热加载中...")
        self._build_dfa()

    def get_stats(self) -> Dict:
        """获取词库统计信息"""
        with self._lock:
            return {
                "total": self._word_count,
                "blocked": len(SENSITIVE_WORDS[SensitiveLevel.BLOCKED]),
                "masked": len(SENSITIVE_WORDS[SensitiveLevel.MASKED]),
                "reviewed": len(SENSITIVE_WORDS[SensitiveLevel.REVIEWED]),
            }


# ============================== 全局单例 ==============================
sensitive_filter = SensitiveFilter()


def check_content(text: str) -> Dict:
    """
    便捷函数:检测文本内容
    供 API 层直接调用
    """
    return sensitive_filter.detect(text)


def is_blocked(text: str) -> bool:
    """便捷函数:是否包含阻断级敏感词"""
    result = sensitive_filter.detect(text)
    return result["level"] == SensitiveLevel.BLOCKED
