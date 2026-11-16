# 模块4/7 新增接口的纯函数单测（不依赖数据库与网络）
#
# 覆盖：
#   - 遗忘曲线 SM-2 简化排程 _next_interval
#   - 学习周报的周窗口 _week_range 与点评 _comment
#   - 方案快照序列化 _serialize
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.v1.growth.review import _next_interval            # noqa: E402
from app.api.v1.growth.weekly_report import _comment, _week_range  # noqa: E402
from app.api.v1.growth.plan_snapshot import _serialize         # noqa: E402


class _Goal:
    """最小 StudyGoal 替身，只提供 _serialize 用到的字段。"""

    def __init__(self, title, done=0, subject_mode=0, meta=None):
        self.title = title
        self.is_completed = done
        self.subject_mode = subject_mode
        self.plan_meta = meta


def test_review_again_resets_interval_and_lowers_ease():
    interval, ease, reps = _next_interval("again", interval=15, ease=2.5, reps=3)
    assert interval == 1
    assert ease == 2.3
    assert reps == 0


def test_review_ease_floor_is_1_3():
    interval, ease, _ = _next_interval("again", interval=1, ease=1.3, reps=0)
    assert interval == 1
    assert ease == 1.3


def test_review_good_progression():
    # 第 1 次答对 -> 1 天；第 2 次 -> 3 天；第 3 次起按 ease 放大
    assert _next_interval("good", interval=1, ease=2.5, reps=0)[0] == 1
    assert _next_interval("good", interval=1, ease=2.5, reps=1)[0] == 3
    interval, ease, reps = _next_interval("good", interval=3, ease=2.5, reps=2)
    assert interval == 8          # round(3 * 2.5) = 8
    assert reps == 3
    assert ease == 2.5


def test_review_easy_grows_faster_and_caps_ease():
    interval, ease, _ = _next_interval("easy", interval=3, ease=2.5, reps=1)
    assert interval == round(3 * 2.5 * 1.3)
    assert ease == 2.65
    # ease 上限 3.0
    assert _next_interval("easy", interval=1, ease=3.0, reps=1)[1] <= 3.0


def test_week_range_is_seven_days_and_ordered():
    start, end = _week_range(0)
    assert end > start
    assert (end - start) == timedelta(days=7)
    assert end <= datetime.now()


def test_week_range_previous_week_ends_earlier():
    s0, e0 = _week_range(0)
    s1, e1 = _week_range(1)
    assert e1 <= s0


def test_comment_without_data_is_honest():
    text = _comment(focus_minutes=0, completion=0, wrong_new=0, tasks_total=0)
    assert "还没有记录" in text


def test_comment_high_execution():
    text = _comment(focus_minutes=400, completion=90, wrong_new=2, tasks_total=10)
    assert "执行力" in text


def test_serialize_reads_plan_meta_and_tasks():
    goals = [
        _Goal("任务A", done=1, subject_mode=1, meta='{"summary": "汇总", "phases": [{"name": "基础"}], "tips": "x"}'),
        _Goal("任务B", done=0, subject_mode=0),
    ]
    data = _serialize(goals)
    assert data["summary"] == "汇总"
    assert data["phases"][0]["name"] == "基础"
    assert len(data["tasks"]) == 2
    assert data["tasks"][0]["done"] == 1


def test_serialize_handles_bad_meta_json():
    data = _serialize([_Goal("任务A", meta="not-json")])
    assert data["summary"] == ""
    assert data["tasks"][0]["title"] == "任务A"
