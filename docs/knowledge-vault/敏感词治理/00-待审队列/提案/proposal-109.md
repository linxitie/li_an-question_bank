---
type: content_guard_proposal
proposal_id: 109
kind: add_variant
status: pending
proposer: redteam
created_at: 2026-11-18T13:52:45
---

# 提案 109：红队发现绕过写法：我要杀了你 → 我要殺了你

## 变更内容
~~~json
{
  "term_id": 119,
  "variant": "我要殺了你",
  "kind": "traditional",
  "term": "我要杀了你"
}
~~~

## 证据
~~~json
[
  {
    "source": "redteam",
    "sample_id": 149,
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
