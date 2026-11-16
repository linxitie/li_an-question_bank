---
type: content_guard_proposal
proposal_id: 1
kind: add_variant
status: pending
proposer: redteam
created_at: 2026-11-10T03:30:00
---

# 提案 1：红队发现绕过写法：黄色视频 → 黃色视频

## 变更内容
~~~json
{
  "term_id": 10,
  "variant": "黃色视频",
  "kind": "traditional",
  "term": "黄色视频"
}
~~~

## 证据
~~~json
[
  {
    "source": "redteam",
    "sample_id": 15,
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
