---
type: content_guard_proposal
proposal_id: 8
kind: add_variant
status: pending
proposer: redteam
created_at: 2026-11-10T03:30:00
---

# 提案 8：红队发现绕过写法：分裂国家 → 分裂國家

## 变更内容
~~~json
{
  "term_id": 45,
  "variant": "分裂國家",
  "kind": "traditional",
  "term": "分裂国家"
}
~~~

## 证据
~~~json
[
  {
    "source": "redteam",
    "sample_id": 71,
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
