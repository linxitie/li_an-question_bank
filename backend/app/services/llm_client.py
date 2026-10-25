"""
联考小智 - 大模型客户端封装

统一处理与大模型后端的通信：鉴权、超时、重试、异常分级。
请求格式按 OpenAI Chat Completions 兼容协议：
    POST {LLM_API_URL}/chat/completions
    Authorization: Bearer {LLM_API_KEY}
    { "model": ..., "messages": [{"role":..., "content":...}] }
"""
import logging
from typing import List, Dict

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)

# 三类场景的 system prompt
SCENE_SYSTEM_PROMPTS: Dict[str, str] = {
    "psychological": (
        "你是'联考小智'，一名经验丰富的公安联考备考心理辅导老师。"
        "你的任务是倾听考生的焦虑、疲惫、自我怀疑，用温和、专业、鼓励性的语言疏导情绪，"
        "帮助他们调整心态、重建信心。不要直接讲题，不要讲大道理；先共情，再给一个可执行的小建议。"
        "回答控制在 150 字以内，语气像身边靠谱的学长学姐。"
    ),
    "qa": (
        "你是'联考小智'，一名公安联考备考答疑助手。"
        "考生会问行测、申论、公安专业科目相关的知识点、题目解析、政策概念。"
        "请用准确、简洁的语言解答；不确定的地方明确说'这个知识点建议查阅官方教材'，不要编造。"
        "回答控制在 300 字以内，条理清晰。"
    ),
    "advice": (
        "你是'联考小智'，一名公安联考备考规划顾问。"
        "考生会问复习方法、时间安排、科目优先级、刷题策略、冲刺阶段怎么安排等提升建议。"
        "请给出具体、可落地的建议，结合公安联考的科目特点（行测、申论、公安专业科目）。"
        "回答控制在 250 字以内，分点作答。"
    ),
}

DEFAULT_SYSTEM_PROMPT = SCENE_SYSTEM_PROMPTS["qa"]

# 学习计划生成专用 prompt（模块4）
PLAN_SYSTEM_PROMPT = (
    "你是'联考小智'，一名公安联考备考规划师。"
    "考生会告诉你：考试日期、薄弱科目、每天可学时长、当前水平。"
    "你需要生成一份结构化的复习计划，严格输出 JSON，不要输出 JSON 以外的任何文字。"
    "格式如下：\n"
    "{\n"
    '  "summary": "一句话总览计划",\n'
    '  "phases": [\n'
    '    {"name": "基础阶段", "days": 30, "focus": "扫盲知识点，建立框架"},\n'
    '    {"name": "强化阶段", "days": 30, "focus": "分模块刷题，错题归档"}\n'
    "  ],\n"
    '  "daily_tasks": [\n'
    '    {"time": "早晨", "task": "行测-资料分析-限时20题", "duration_min": 40},\n'
    '    {"time": "下午", "task": "申论-归纳概括-1道+范文精读", "duration_min": 60}\n'
    "  ],\n"
    '  "tips": "每天留10分钟复盘，错题当天归档..."\n'
    "}\n"
    "要求：任务要具体到科目+题型+题量，不要说'复习行测'这种空话；"
    "总天数根据考试日期合理拆分；难度跟考生水平匹配。"
)


class LLMClientError(Exception):
    """大模型调用异常基类"""

    def __init__(self, message: str, code: str = "llm_error"):
        self.message = message
        self.code = code
        super().__init__(message)


async def chat(
    messages: List[Dict[str, str]],
    scene: str = "qa",
) -> str:
    """
    调用大模型，返回回复文本。

    :param messages: 完整消息列表（含 system / 历史 user+assistant / 当前 user）
    :param scene: 场景 psychological / qa / advice
    :return: 大模型回复文本
    :raises LLMClientError: 网络/超时/上游错误
    """
    system_prompt = SCENE_SYSTEM_PROMPTS.get(scene, DEFAULT_SYSTEM_PROMPT)
    payload_messages = [{"role": "system", "content": system_prompt}, *messages]

    url = settings.LLM_API_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.LLM_MODEL,
        "messages": payload_messages,
        "temperature": 0.7,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException:
        logger.warning("LLM 调用超时: url=%s", url)
        raise LLMClientError("大模型响应超时，请稍后重试", "llm_timeout")
    except httpx.ConnectError:
        logger.error("LLM 连接失败: url=%s", url)
        raise LLMClientError("无法连接到大模型服务", "llm_unreachable")
    except Exception as e:  # noqa: BLE001
        logger.exception("LLM 调用异常")
        raise LLMClientError("大模型服务暂时不可用", "llm_error") from e

    if resp.status_code != 200:
        logger.error("LLM 返回非 200: status=%s body=%s", resp.status_code, resp.text[:300])
        raise LLMClientError(f"大模型返回错误（{resp.status_code}）", "llm_bad_status")

    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as e:
        logger.error("LLM 响应解析失败: %s", resp.text[:300])
        raise LLMClientError("大模型响应格式异常", "llm_bad_response") from e


async def chat_plan(user_input: str) -> str:
    """
    生成学习计划，返回原始 JSON 文本（由路由层解析并校验）。
    user_input 是学生填的表单信息汇总。

    :raises LLMClientError: 网络/超时/上游错误
    """
    payload_messages = [
        {"role": "system", "content": PLAN_SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]
    url = settings.LLM_API_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.LLM_MODEL,
        "messages": payload_messages,
        "temperature": 0.5,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException:
        logger.warning("chat_plan 调用超时: url=%s", url)
        raise LLMClientError("学习计划生成超时，请稍后重试", "llm_timeout")
    except httpx.ConnectError:
        logger.error("chat_plan 连接失败: url=%s", url)
        raise LLMClientError("无法连接到大模型服务", "llm_unreachable")
    except Exception as e:  # noqa: BLE001
        logger.exception("chat_plan 调用异常")
        raise LLMClientError("学习计划生成失败", "llm_error") from e

    if resp.status_code != 200:
        logger.error("chat_plan 非200: status=%s body=%s", resp.status_code, resp.text[:300])
        raise LLMClientError("学习计划生成失败", "llm_bad_status")

    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as e:
        logger.error("chat_plan 响应解析失败: %s", resp.text[:300])
        raise LLMClientError("学习计划生成失败", "llm_bad_response") from e
