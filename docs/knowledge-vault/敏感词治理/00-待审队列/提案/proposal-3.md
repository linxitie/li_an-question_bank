---
type: content_guard_proposal
proposal_id: 3
kind: add_variant
status: pending
proposer: redteam
created_at: 2026-11-10T03:30:00
---

# 提案 3：红队发现绕过写法：开盘 → 開盘

## 变更内容
~~~json
{
  "term_id": 17,
  "variant": "開盘",
  "kind": "traditional",
  "term": "开盘"
}
~~~

## 证据
~~~json
[
  {
    "source": "redteam",
    "sample_id": 25,
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
