---
type: content_guard_proposal
proposal_id: 68
kind: consistency
status: pending
proposer: system
created_at: 2026-11-15T03:30:01
---

# 提案 68：一致性异常：term_without_policy

## 变更内容
~~~json
{
  "code": "term_without_policy",
  "key": "147",
  "detail": "词条「狗腿子」未绑定政策条款",
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
