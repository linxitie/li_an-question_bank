---
type: content_guard_proposal
proposal_id: 104
kind: consistency
status: pending
proposer: system
created_at: 2026-11-07T03:30:01
---

# 提案 104：一致性异常：audit_chain_broken

## 变更内容
~~~json
{
  "code": "audit_chain_broken",
  "key": "3",
  "detail": "prev_hash 与上一条事件不一致",
  "severity": "error"
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
