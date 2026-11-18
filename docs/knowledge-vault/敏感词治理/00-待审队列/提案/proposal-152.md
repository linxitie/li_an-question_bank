---
type: content_guard_proposal
proposal_id: 152
kind: consistency
status: pending
proposer: system
created_at: 2026-11-18T13:52:48
---

# 提案 152：一致性异常：term_without_policy

## 变更内容
~~~json
{
  "code": "term_without_policy",
  "key": "225",
  "detail": "词条「先垫付后返现」未绑定政策条款",
  "severity": "warn"
}
~~~

## 证据
~~~json
[
  {
    "source": "reconcile"
  }
]
~~~

## 审阅（勾选一项后执行受控导入）
- [ ] 通过
- [ ] 拒绝
- 备注：
