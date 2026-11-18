---
type: content_guard_task
task_id: 47
judgment_id: 47
status: pending
priority: 50
created_at: 2026-11-10T14:27:36
---

# 判定 47 待复核

- 场景：forum_post / 来源 117
- 等级：reviewed，置信度：0.645
- 脱敏摘要：(无标题) <p><br>import request*<*r>from bs4 import BeautifulSoup<br>url='<a href="https://www.autohome.com.cn/news/" target="_blank" rel="noopener noreferrer">https://www.autohome.com.cn/news/</a>'<br>h…
- 命中：sb

## 证据链
~~~json
[
  {
    "step": "normalize",
    "detail": "NFKC 全半角归一 + 小写 + 去零宽/分隔符",
    "input_length": 352,
    "compact_length": 251
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
  },
  {
    "step": "link",
    "decision": "review",
    "reason": "普通外部链接，打码送审"
  }
]
~~~

## 复核（勾选一项）
- [ ] 确认违规
- [ ] 误判
- 备注：
