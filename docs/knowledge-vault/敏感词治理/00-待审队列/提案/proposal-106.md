---
type: content_guard_proposal
proposal_id: 106
kind: add_variant
status: pending
proposer: redteam
created_at: 2026-11-18T13:52:45
---

# 提案 106：红队发现绕过写法：他妈的 → 他媽的

## 变更内容
~~~json
{
  "term_id": 51,
  "variant": "他媽的",
  "kind": "traditional",
  "term": "他妈的"
}
~~~

## 证据
~~~json
[
  {
    "source": "redteam",
    "sample_id": 98,
    "kind": "traditional"
  },
  {
    "detected": false,
    "engine_version": 4
  }
]
~~~

## 审阅（勾选一项后执行受控导入）
- [ ] 通过
- [ ] 拒绝
- 备注：
