---
type: content_guard_proposal
proposal_id: 9
kind: add_variant
status: pending
proposer: redteam
created_at: 2026-11-10T03:30:00
---

# 提案 9：红队发现绕过写法：妈的 → 媽的

## 变更内容
~~~json
{
  "term_id": 50,
  "variant": "媽的",
  "kind": "traditional",
  "term": "妈的"
}
~~~

## 证据
~~~json
[
  {
    "source": "redteam",
    "sample_id": 80,
    "kind": "traditional"
  },
  {
    "detected": false,
    "engine_version": 1
  }
]
~~~

## 审阅（勾选一项后执行受控导入）
- [ ] 通过
- [ ] 拒绝
- 备注：
