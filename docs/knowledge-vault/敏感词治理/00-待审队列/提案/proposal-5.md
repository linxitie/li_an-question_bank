---
type: content_guard_proposal
proposal_id: 5
kind: add_variant
status: pending
proposer: redteam
created_at: 2026-11-10T03:30:00
---

# 提案 5：红队发现绕过写法：赌资 → 賭资

## 变更内容
~~~json
{
  "term_id": 21,
  "variant": "賭资",
  "kind": "traditional",
  "term": "赌资"
}
~~~

## 证据
~~~json
[
  {
    "source": "redteam",
    "sample_id": 35,
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
