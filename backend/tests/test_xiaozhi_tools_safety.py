# 小智工具层安全单测：calc 的表达式求值必须是白名单，绝不允许任意代码执行
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.xiaozhi_agent import _safe_eval  # noqa: E402


def test_basic_arithmetic():
    assert _safe_eval("1+2*3") == 7
    assert _safe_eval("(65+58)/2") == 61.5
    assert _safe_eval("2**10") == 1024
    assert _safe_eval("7//2") == 3
    assert _safe_eval("7%3") == 1
    assert _safe_eval("-5+2") == -3


def test_division_by_zero_raises():
    with pytest.raises(ZeroDivisionError):
        _safe_eval("1/0")


@pytest.mark.parametrize(
    "expr",
    [
        "__import__('os').system('echo hi')",   # 任意导入
        "open('/etc/passwd').read()",           # 文件读取
        "eval('1+1')",                          # 嵌套求值
        "().__class__",                         # 属性穿透
        "lambda: 1",                            # lambda
        "x + 1",                                # 未定义名字
        "[1,2,3]",                              # 非数值字面量
    ],
)
def test_rejects_non_arithmetic(expr):
    with pytest.raises(Exception):
        _safe_eval(expr)


def test_rejects_string_literal():
    # 字符串常量不是数值，必须拒绝
    with pytest.raises(Exception):
        _safe_eval("'a' * 1000")
