---
type: content_guard_task
task_id: 56
judgment_id: 56
status: pending
priority: 50
created_at: 2026-11-14T08:41:00
---

# 判定 56 待复核

- 场景：forum_comment / 来源 117
- 等级：reviewed，置信度：0.645
- 脱敏摘要：[[file:/uploads/forum/202611/2be13f3e2e834914806f1fd031894d8e.png|屏幕截图 2026-05-28 161138.png]] [[file:/uploads/forum/202611/4a33746377384927bbe5234b79e898c6.png|屏幕截图 2026-05-30 104536.png]] hdfbrehas…
- 命中：sb

## 证据链
~~~json
[
  {
    "step": "normalize",
    "detail": "NFKC 全半角归一 + 小写 + 去零宽/分隔符",
    "input_length": 580,
    "compact_length": 472
  },
  {
    "step": "dfa_match",
    "hits": [
      {
        "term_id": 178,
        "term": "sb",
        "level": "reviewed",
        "category": "脏话粗口",
        "variant_kind": null
      }
    ]
  },
  {
    "step": "policy_map",
    "clauses": []
  },
  {
    "step": "arbitration",
    "rule": "取最高等级；同等级按政策 priority 排序；置信度不足转人工",
    "level": "reviewed",
    "confidence": 0.645,
    "engine_version": 4,
    "engine_source": "db"
  },
  {
    "step": "decision",
    "decision": "review",
    "reason": "reviewed 级词条只研判不自动处置"
  }
]
~~~

## 复核（勾选一项）
- [ ] 确认违规
- [ ] 误判
- 备注：
