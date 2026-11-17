# -*- coding: utf-8 -*-
"""短信通道适配器（v9 M4）。

设计取舍
--------
用户在方案里要求「电脑端收件箱提醒 + 短信提醒」，但短信必须经过运营商模板报备，
第三方 SDK（阿里云/腾讯云）账号与签名由用户本人开通。所以这里不内嵌任何厂商 SDK，
只做**一个稳定的出口**：把「发给谁、发什么」整理成标准 payload，POST 给已对接的网关；
需要换厂商时只改网关侧，不动业务代码。

三条纪律
--------
1. 默认关闭（NOTIFY_SMS_ENABLED=False）：没报备模板时绝不外发，避免产生费用与投诉。
2. 永不抛错：提醒是旁路，短信失败不能影响站内信写入或定时任务。
3. 有配额：每人每天 NOTIFY_SMS_DAILY_MAX 条，超出只在日志留痕。
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import urllib.request
from typing import Any, Dict, Optional

from ...core.config import settings

logger = logging.getLogger(__name__)

# 进程内按天计数：重启后归零可接受（短信本身是幂等提醒，重复一条不致命）
_counter: Dict[str, Dict[str, int]] = {}


def _today_key() -> str:
    return dt.date.today().isoformat()


def _consume_quota(user_id: int) -> bool:
    day = _today_key()
    bucket = _counter.setdefault(day, {})
    key = str(user_id)
    used = bucket.get(key, 0)
    if used >= int(settings.NOTIFY_SMS_DAILY_MAX):
        return False
    bucket[key] = used + 1
    # 跨天清理，避免字典无限增长
    for stale in [d for d in _counter if d != day]:
        _counter.pop(stale, None)
    return True


def _normalize_phone(raw: Optional[str]) -> Optional[str]:
    """把库里的手机号归一成 11 位；非法直接视为无手机号，不发。"""
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if len(digits) == 13 and digits.startswith("86"):
        digits = digits[2:]
    if len(digits) != 11 or not digits.startswith("1"):
        return None
    return digits


def send(phone: Optional[str], title: str, content: str, *, user_id: Optional[int] = None) -> Dict[str, Any]:
    """发一条短信。返回结果字典，任何失败都在返回值里，不抛异常。"""
    if not settings.NOTIFY_SMS_ENABLED:
        return {"sent": False, "reason": "disabled"}
    target = _normalize_phone(phone)
    if not target:
        return {"sent": False, "reason": "no_phone"}
    if user_id and not _consume_quota(int(user_id)):
        return {"sent": False, "reason": "daily_limit"}

    text = (title or "").strip()
    body = (content or "").strip()
    if body:
        text = (text + "：" + body) if text else body
    text = text[:120]

    transport = (settings.NOTIFY_SMS_TRANSPORT or "webhook").lower()
    if transport == "log":
        logger.info("[sms:log] to=%s text=%s", target[-4:], text)
        return {"sent": True, "transport": "log"}

    url = (settings.NOTIFY_SMS_WEBHOOK_URL or "").strip()
    if not url:
        return {"sent": False, "reason": "no_webhook"}
    payload = {
        "phone": target,
        "sign": settings.NOTIFY_SMS_SIGN,
        "text": text,
        "user_id": user_id,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            **({"Authorization": "Bearer " + settings.NOTIFY_SMS_WEBHOOK_TOKEN}
               if settings.NOTIFY_SMS_WEBHOOK_TOKEN else {}),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            ok = 200 <= int(getattr(resp, "status", 0)) < 300
            return {"sent": ok, "transport": "webhook", "status": int(getattr(resp, "status", 0))}
    except Exception as e:  # noqa: BLE001 - 旁路通道，失败只记录
        logger.warning("短信发送失败 to=%s: %s", target[-4:], e)
        return {"sent": False, "reason": "transport_error", "error": str(e)[:120]}
