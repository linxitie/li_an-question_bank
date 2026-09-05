"""智能分类服务 — 根据文件类型、内容长度、标题关键词自动判断资料类型"""
import re
from typing import Optional


class MaterialClassifier:
    """资料智能分类器"""

    # 文件扩展名 → 大类映射
    FILE_TYPE_MAP = {
        '.mp4': 'video', '.mov': 'video', '.avi': 'video', '.webm': 'video',
        '.jpg': 'image', '.jpeg': 'image', '.png': 'image', '.gif': 'image',
        '.webp': 'image', '.svg': 'image',
        '.pdf': 'document', '.docx': 'document', '.txt': 'document',
        '.xlsx': 'spreadsheet', '.csv': 'spreadsheet',
        '.zip': 'archive', '.rar': 'archive',
    }

    # 视频时长阈值（秒）
    VIDEO_SHORT_THRESHOLD = 15 * 60   # 15 分钟

    # 文档字数阈值
    DOC_SHORT_THRESHOLD = 500

    # 关键词正则
    RE_INTRO = re.compile(r'入门|导学|基础|考什么|新手|零基础')
    RE_ADVANCED = re.compile(r'进阶|高分|技巧|深度|解析|冲刺')
    RE_CARD = re.compile(r'卡片|知识|要点|口诀|速记')
    RE_CHART = re.compile(r'思维导图|流程图|结构图|图谱')

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def classify(
        self,
        file_ext: str,
        content: Optional[str] = None,
        duration: Optional[int] = None,
        title: Optional[str] = None,
    ) -> dict:
        """
        智能分类资料。

        Returns:
            {"type": str, "confidence": float, "reason": str}
        """
        file_type = self.FILE_TYPE_MAP.get(file_ext.lower())

        if file_type == 'video':
            return self._classify_video(duration, title)
        if file_type == 'image':
            return self._classify_image(title)
        if file_type == 'document':
            return self._classify_document(content, title)
        if file_type == 'spreadsheet':
            return self._classify_spreadsheet(title)

        # 未知格式 → 文章兜底
        return {'type': 'article', 'confidence': 0.5, 'reason': '未知格式，默认文章'}

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    def _classify_video(self, duration: Optional[int], title: Optional[str]) -> dict:
        short = duration is not None and duration <= self.VIDEO_SHORT_THRESHOLD
        long_ = duration is not None and duration > self.VIDEO_SHORT_THRESHOLD

        if short and title and self.RE_INTRO.search(title):
            return {'type': 'video_intro', 'confidence': 0.92, 'reason': '短视频+入门关键词'}
        if short:
            return {'type': 'video_intro', 'confidence': 0.80, 'reason': '短视频(≤15min)'}

        if long_ and title and self.RE_ADVANCED.search(title):
            return {'type': 'video_advanced', 'confidence': 0.92, 'reason': '长视频+进阶关键词'}
        if long_:
            return {'type': 'video_advanced', 'confidence': 0.80, 'reason': '长视频(>15min)'}

        # 无时长信息 → 根据标题猜
        if title and self.RE_INTRO.search(title):
            return {'type': 'video_intro', 'confidence': 0.70, 'reason': '视频+入门关键词(无时长)'}
        if title and self.RE_ADVANCED.search(title):
            return {'type': 'video_advanced', 'confidence': 0.70, 'reason': '视频+进阶关键词(无时长)'}

        return {'type': 'video_intro', 'confidence': 0.60, 'reason': '视频默认入门'}

    def _classify_image(self, title: Optional[str]) -> dict:
        if title and self.RE_CHART.search(title):
            return {'type': 'image', 'confidence': 0.85, 'reason': '图片+图表关键词'}
        return {'type': 'image', 'confidence': 0.70, 'reason': '图片文件'}

    def _classify_document(self, content: Optional[str], title: Optional[str]) -> dict:
        content_len = len(content) if content else 0

        if content_len < self.DOC_SHORT_THRESHOLD:
            if title and self.RE_CARD.search(title):
                return {'type': 'card', 'confidence': 0.88, 'reason': '短文档+卡片关键词'}
            return {'type': 'card', 'confidence': 0.70, 'reason': f'短文档({content_len}字)'}

        return {'type': 'article', 'confidence': 0.82, 'reason': f'长文档({content_len}字)'}

    def _classify_spreadsheet(self, title: Optional[str]) -> dict:
        if title and self.RE_CARD.search(title):
            return {'type': 'card', 'confidence': 0.80, 'reason': '表格+卡片关键词'}
        return {'type': 'article', 'confidence': 0.72, 'reason': '表格文件→文章'}


# 全局单例
classifier = MaterialClassifier()
