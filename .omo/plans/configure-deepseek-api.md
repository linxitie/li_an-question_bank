# 配置 DeepSeek API 密钥

## TL;DR

> **快速摘要**: 将 DeepSeek API 密钥 `[REMOVED-DEEPSEEK-1]` 配置到 OpenCode 的 deepseek-v4-Pro 和 deepseek-v4-flash 模型中
>
> **交付物**:
> - 更新 `auth.json` 中的 API 密钥
> - 更新 `opencode.jsonc` 中的 DeepSeek 模型配置
>
> **预估工作量**: Quick
> **并行执行**: NO - 顺序执行

---

## 上下文

### 原始请求
用户想要将 DeepSeek API 密钥 `[REMOVED-DEEPSEEK-1]` 配置到 OpenCode 的 deepseek-v4-Pro 和 deepseek-v4-flash 模型中。

### 研究发现
1. API 密钥存储在 `~/.local/share/opencode/auth.json` 中
2. 模型配置在 `~/.opencode/opencode.jsonc` 的 `provider` 部分
3. DeepSeek V4 Pro 和 Flash 都支持 1,048,576 token 上下文窗口，最大输出 384,000 tokens

---

## 工作目标

### 核心目标
配置 DeepSeek API 密钥并添加 deepseek-v4-Pro 和 deepseek-v4-flash 模型配置

### 具体交付物
- 更新 `C:\Users\21499\.local\share\opencode\auth.json`
- 更新 `C:\Users\21499\.opencode\opencode.jsonc`

### 完成定义
- [ ] auth.json 中包含新的 API 密钥
- [ ] opencode.jsonc 中包含 DeepSeek 模型配置
- [ ] 配置格式正确

### 必须包含
- API 密钥: `[REMOVED-DEEPSEEK-1]`
- 模型: `deepseek-v4-Pro` 和 `deepseek-v4-flash`
- 正确的上下文窗口和输出限制

### 必须不包含（护栏）
- 不修改其他提供商的配置
- 不删除现有配置
- 不添加不必要的模型配置

---

## 验证策略

### 测试决策
- **自动化测试**: 无 - 配置任务不需要测试
- **QA 策略**: 手动验证配置文件内容

---

## 执行策略

### 执行顺序
1. 更新 auth.json 中的 API 密钥
2. 更新 opencode.jsonc 中的 DeepSeek 模型配置

### 关键路径
auth.json → opencode.jsonc

---

## 任务清单

- [ ] 1. 更新 auth.json 中的 DeepSeek API 密钥

  **要做的事情**:
  - 编辑 `C:\Users\21499\.local\share\opencode\auth.json`
  - 将 `key` 字段更新为 `[REMOVED-DEEPSEEK-1]`

  **不要做**:
  - 不修改其他字段
  - 不改变文件结构

  **参考文件**:
  - `C:\Users\21499\.local\share\opencode\auth.json` - 当前包含旧的 API 密钥

  **验收标准**:
  - [ ] auth.json 文件存在且可读
  - [ ] `key` 字段值为 `[REMOVED-DEEPSEEK-1]`

  **QA 场景**:
  ```
  场景: 验证 auth.json 更新成功
    工具: Bash (PowerShell)
    前提条件: auth.json 文件存在
    步骤:
      1. 读取 auth.json 文件内容
      2. 验证 deepseek.key 字段值
    预期结果: key 字段值为 "[REMOVED-DEEPSEEK-1]"
    失败指标: key 字段值不匹配或文件不存在
  ```

  **提交**: YES
  - 消息: `config(auth): update DeepSeek API key`
  - 文件: `C:\Users\21499\.local\share\opencode\auth.json`

---

- [ ] 2. 在 opencode.jsonc 中添加 DeepSeek 模型配置

  **要做的事情**:
  - 编辑 `C:\Users\21499\.opencode\opencode.jsonc`
  - 在 `provider` 部分添加 `deepseek` 提供商配置
  - 添加 `deepseek-v4-Pro` 和 `deepseek-v4-flash` 模型

  **不要做**:
  - 不修改现有的 Google 模型配置
  - 不删除任何现有配置

  **参考文件**:
  - `C:\Users\21499\.opencode\opencode.jsonc` - 当前配置文件
  - 搜索结果中的 DeepSeek 模型规格

  **配置内容**:
  ```json
  "deepseek": {
    "models": {
      "deepseek-v4-Pro": {
        "name": "DeepSeek V4 Pro",
        "limit": {
          "context": 1048576,
          "output": 384000
        },
        "modalities": {
          "input": ["text"],
          "output": ["text"]
        }
      },
      "deepseek-v4-flash": {
        "name": "DeepSeek V4 Flash",
        "limit": {
          "context": 1048576,
          "output": 384000
        },
        "modalities": {
          "input": ["text"],
          "output": ["text"]
        }
      }
    }
  }
  ```

  **验收标准**:
  - [ ] opencode.jsonc 文件包含 deepseek 提供商配置
  - [ ] deepseek-v4-Pro 模型配置正确
  - [ ] deepseek-v4-flash 模型配置正确
  - [ ] JSON 格式有效

  **QA 场景**:
  ```
  场景: 验证 opencode.jsonc 配置更新
    工具: Bash (PowerShell)
    前提条件: opencode.jsonc 文件存在
    步骤:
      1. 读取 opencode.jsonc 文件内容
      2. 验证 provider.deepseek 配置存在
      3. 验证 deepseek-v4-Pro 和 deepseek-v4-flash 模型配置
    预期结果: 两个模型都正确配置，JSON 格式有效
    失败指标: 配置缺失或 JSON 格式错误
  ```

  **提交**: YES
  - 消息: `config(provider): add DeepSeek V4 Pro and Flash models`
  - 文件: `C:\Users\21499\.opencode\opencode.jsonc`

---

## 最终验证波

- [ ] F1. **配置完整性检查**
  - 验证 auth.json 和 opencode.jsonc 都已更新
  - 验证 API 密钥格式正确
  - 验证模型配置格式正确

---

## 成功标准

### 验证命令
```powershell
# 验证 auth.json
Get-Content "$env:USERPROFILE\.local\share\opencode\auth.json" | ConvertFrom-Json | Select-Object -ExpandProperty deepseek

# 验证 opencode.jsonc 中的 deepseek 配置
Get-Content "$env:USERPROFILE\.opencode\opencode.jsonc" | ConvertFrom-Json | Select-Object -ExpandProperty provider | Select-Object -ExpandProperty deepseek
```

### 最终检查清单
- [ ] API 密钥已更新
- [ ] DeepSeek 模型配置已添加
- [ ] 配置格式正确
- [ ] 现有配置未被破坏
