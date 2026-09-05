"""
爬虫共享工具模块 — 反爬策略、安全请求、日志
所有爬虫共用的UA轮换、延迟、重试机制
"""
import logging
import random
import time
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# ============ 反爬配置 ============

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
]

REQUEST_DELAY_MIN = 1.0   # 最小请求间隔（秒）
REQUEST_DELAY_MAX = 2.5   # 最大请求间隔（秒）
MAX_RETRIES = 3           # 最大重试次数
RETRY_BACKOFF = 2.0       # 重试退避倍数
REQUEST_TIMEOUT = 30      # 请求超时（秒）


def get_random_ua() -> str:
    """随机获取User-Agent"""
    return random.choice(USER_AGENTS)


def safe_request(url: str, timeout: int = REQUEST_TIMEOUT, label: str = "",
                 encoding: str = None) -> Optional[requests.Response]:
    """
    带UA轮换、随机延迟、指数退避重试的安全HTTP请求。

    Args:
        url: 请求URL
        timeout: 超时时间（秒）
        label: 日志标签（如 "[recruitment/国考省考]"）
        encoding: 强制编码（如 'gbk', 'utf-8'），None 则自动检测

    Returns:
        Response 对象，失败返回 None
    """
    prefix = f"[{label}] " if label else ""

    for attempt in range(MAX_RETRIES):
        try:
            # 随机延迟（反爬）
            delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
            time.sleep(delay)

            headers = {
                "User-Agent": get_random_ua(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Cache-Control": "max-age=0",
            }
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            # 编码优先级: 指定编码 > apparent_encoding > meta标签检测 > utf-8
            if encoding:
                resp.encoding = encoding
            elif resp.apparent_encoding and resp.apparent_encoding.lower() not in ('iso-8859-1', 'windows-1252'):
                resp.encoding = resp.apparent_encoding
            else:
                # 从 HTML meta 标签检测
                import re as _re
                m = _re.search(rb'<meta[^>]+charset=["\']?([a-zA-Z0-9\-]+)', resp.content[:2048])
                if m:
                    resp.encoding = m.group(1).decode('ascii')
                else:
                    resp.encoding = "utf-8"
            return resp

        except requests.exceptions.Timeout:
            logger.warning(f"{prefix}请求超时 (尝试 {attempt+1}/{MAX_RETRIES})")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"{prefix}连接错误: {e} (尝试 {attempt+1}/{MAX_RETRIES})")
        except requests.exceptions.HTTPError as e:
            logger.warning(f"{prefix}HTTP错误: {e} (尝试 {attempt+1}/{MAX_RETRIES})")
        except Exception as e:
            logger.warning(f"{prefix}请求异常: {type(e).__name__}: {e} (尝试 {attempt+1}/{MAX_RETRIES})")

        if attempt < MAX_RETRIES - 1:
            backoff = RETRY_BACKOFF * (attempt + 1)
            time.sleep(backoff)

    logger.error(f"{prefix}请求最终失败: {url}")
    return None
