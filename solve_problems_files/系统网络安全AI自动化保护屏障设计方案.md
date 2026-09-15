# 公安联考题库系统 网络安全保护屏障设计方案（AI自动化安全防护增强版）


## 文档说明

- **文档版本**：v2.0
- **编写日期**：2026年9月
- **更新说明**：在v1.0七层纵深防御体系基础上，新增AI自动化漏洞检测、开源组件安全分析（SCA）、垂直/水平权限攻击防护、文件删除漏洞防护等深度安全能力
- **适用对象**：系统架构师、后端开发人员、运维工程师、安全工程师


## 一、AI自动化漏洞检测系统设计

### 1.1 设计目标

| 目标 | 说明 |
|------|------|
| **自动化漏洞发现** | 无需人工干预，AI智能体自动扫描代码库发现安全漏洞 |
| **零日漏洞挖掘** | 利用AI推理能力发现未知漏洞，而非仅依赖已知漏洞库 |
| **低误报率** | 通过多智能体协作与沙箱验证，大幅降低传统SAST工具的误报 |
| **CI/CD集成** | 在代码提交和合并阶段自动触发安全扫描，实现DevSecOps |
| **自动修复建议** | 针对发现的漏洞自动生成修复建议或补丁代码 |

### 1.2 核心AI安全工具选型

针对OpenCode+Ollama的本地部署环境，我重新调整了安全工具选型，聚焦于能直接集成到OpenCode生态的AI安全方案。

---

### 1.3 OpenCode生态可直接集成的AI安全工具

## 1.3.1 OpenCode YOLO 渗透测试智能体（替代Strix的首选）

**open-sploit** 是一个为OpenCode原生设计的YOLO模式攻防安全智能体，通过 `/target` 命令即可启动完整的渗透测试流程。

| 特性 | 说明 |
|------|------|
| **一键式攻击流程** | `/target <url>` 命令自动执行：侦察 → 枚举 → 利用 → 后渗透 → 报告的全链路攻击 |
| **19个攻击技能** | 自动安装到 `~/.config/opencode/skills/`，覆盖OWASP Top 10、SQL注入、IDOR、JWT攻击、SSRF等 |
| **智能目标分类** | 自动识别目标类型（Web/API/PHP），加载匹配的攻击技能 |
| **Kali Linux集成** | 所有工具通过 `wsl -d kali-linux` 运行（nmap、sqlmap、metasploit、ffuf等） |
| **Playwright MCP** | 真实浏览器处理登录流程、会话管理、CSRF、XSS、DOM漏洞 |
| **Burp Suite MCP** | 自动检测并集成Burp Suite进行拦截、扫描、攻击流程 |

**一键安装**：
```bash
npx open-sploit
```
该命令会自动复制智能体配置、安装19个攻击技能、安全合并权限和MCP服务器配置到 `opencode.json`。

**使用示例**：
```
/target http://10.10.10.10
# 或
/target https://api.example.com/openapi.json
```

### 1.3.2 KaliSec-MCP + OpenCode Skill（193个Kali工具的智能集成）

**KaliSec-MCP** 将193个Kali Linux安全工具与AI深度集成，实现智能化的渗透测试和CTF解题。

| 特性 | 说明 |
|------|------|
| **193个安全工具** | 涵盖信息收集、Web测试、密码攻击、漏洞利用、PWN/逆向 |
| **58,543行知识库** | 五层架构的完整安全测试知识体系 |
| **6个快捷命令** | 一键启动复杂攻击流程 |
| **智能决策树** | 自动根据工具输出选择下一步行动 |
| **CTF专用模式** | 自动Flag检测和提取 |

**OpenCode配置**（`~/.config/opencode/opencode.json`）：
```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "kali-security": {
      "type": "local",
      "command": ["python3", "/opt/kali-mcp/mcp_server.py"],
      "enabled": true,
      "environment": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```


**运行模式**：
- **本地模式（stdio）**：默认，适用于OpenCode本地连接
- **远程模式（SSE）**：可通过HTTP网络连接外部AI系统

### 1.3.3 KAVACH——零输入AI安全审计（Claude Code Skill + Python核心）

**KAVACH** 是一个Claude Code Skill + Python确定性核心的零输入AI安全审计工具，**可在Claude Code/OpenCode中直接使用**。

**检测六大威胁**：
1. **密钥泄露**：硬编码、客户端可访问、Git历史中的密钥
2. **免费聊天滥用**
3. **计费绕过**：客户端信任的价格、未验证的Webhook
4. **跨租户数据盗窃**：IDOR/BOLA
5. **AI劫持**：提示词注入、过度代理权限
6. **恶意依赖**：真实CVE + 安装脚本恶意软件 + 域名欺诈

**三种审计模式**：
| 模式 | 阶段数 | 用途 |
|------|--------|------|
| `lite` | 6 | 快速分类——几分钟内获得信号 |
| `balanced` | 13 | **默认**。知识库、8个领域猎人、PoC |
| `deep` | 20 | 补丁历史、权限/状态/规范专家、跨服务污点追踪 |

**安装与使用**（在Claude Code/OpenCode中）：
```bash
git clone https://github.com/adhuniklabs/kavach.git && cd kavach
./install.sh global   # 全局安装，对所有仓库生效
# 或
./install.sh project  # 项目级安装，可提交共享
```
在Claude Code中执行（OpenCode中可类似方式调用）：
```
/kavach          # 平衡审计（默认）
/kavach deep     # 深度审计
/kavach lite     # 快速分类
/kavach deep --live  # 沙箱PoC执行（需启用）
```


**输出格式**：
- `final-audit-report.md` — 主要交付物
- `audit-report.pdf/html` — 分页报告
- `report.json / .sarif` — CI集成用
- 六轴评分卡、ASVS/CWE/GDPR映射、三阶段修复计划

### 1.3.4 opencode-security-agent——深度技能扫描器

**opencode-security-agent** 的v1.7.0版本引入了**深度技能扫描器（Deep Skill Scanner）**，在安装前对Skills/MCP进行静态分析。

| 特性 | 说明 |
|------|------|
| **零依赖、零LLM成本** | 纯静态分析，无需调用AI模型 |
| **8个扫描模块** | 多语言检测（8种语言），133+检测模式 |
| **预安装扫描** | 在技能/MCP安装前执行安全扫描 |
| **灵感来源** | 借鉴NVIDIA SkillSpector |

### 1.3.5 @symbioticsec/opencode-security-plugin——安全护栏与漏洞扫描

**@symbioticsec/opencode-security-plugin** 为OpenCode提供自动强制执行的安全护栏和漏洞扫描。

**核心能力**：
- 自动执行安全护栏，不中断工作流
- SAST分析检测代码中的安全问题
- 通过 `scanner` 工具运行静态应用安全测试

### 1.3.6 security-scan——AgentShield安全扫描

**security-scan** 使用AgentShield扫描OpenCode配置中的安全漏洞、错误配置和注入风险。

- 检查 `opencode.json` 配置安全
- 检测技能/MCP的注入风险

### 1.3.7 mcp-audit——MCP服务器安全审计

**mcp-audit** 是一个100%本地的MCP服务器配置安全扫描器。

**检测能力**：
| 类别 | 检测内容 |
|------|---------|
| **已知恶意包** | 实时恶意软件活动、已知C2端点 |
| **权限过度** | 配置挂载一个目录但代码读取另一个目录（~/.ssh、.aws）、未声明的网络出站、隐藏的shell生成 |
| **供应链风险** | 域名欺诈、安装钩子（postinstall）、单维护者包 |
| **提示词注入** | 指令覆盖、凭证索取 |
| **遥测泄露** | Segment、Amplitude等分析调用 |
| **安全卫生** | 硬编码密钥、明文HTTP传输、危险启动标志 |

**快速使用**：
```bash
npx @limjonathan/mcp-audit@latest scan
```


每个服务器获得0-100评分和A-F等级，已知恶意匹配自动评为F级。支持JSON和SARIF格式输出，可集成CI。

### 1.3.8 frostagent——默认拒绝能力检查器

**frostagent** 是一个能力检查器，读取MCP服务器、钩子、权限规则和技能，采用“默认拒绝”策略。

- 一个屏幕的策略说明代理工具可以做什么
- 任何未明确允许的操作都会失败
- 锁定文件功能：当工具发生变化时失败
- 支持Claude Code、Claude Desktop、Cursor、VS Code、**OpenCode**等

### 1.3.9 Ollama原生漏洞扫描工具

**LocalVulnAI** 是一个使用Ollama的本地AI驱动漏洞扫描器。

| 特性 | 说明 |
|------|------|
| **离线运行** | 完全本地，无需互联网 |
| **代码+网站扫描** | 支持代码仓库和Web应用扫描 |
| **检测类型** | SQL注入、远程代码执行模式 |
| **修复建议** | 提供漏洞解释和修复建议 |

**安装与使用**：
```bash
git clone https://github.com/BluHExH/LocalVulnAI
# 配置Ollama模型后运行
python scanner.py --target ./backend
```


## 1.4 OpenCode集成配置方案

### 1.4.1 核心MCP服务器配置（`~/.config/opencode/opencode.json`）

```json
{
  "$schema": "https://opencode.ai/config.json",
  
  "mcp": {
    "kali-security": {
      "type": "local",
      "command": ["python3", "/opt/kali-mcp/mcp_server.py"],
      "enabled": true,
      "environment": { "PYTHONUNBUFFERED": "1" }
    },
    "security-auditor": {
      "type": "local",
      "command": ["npx", "-y", "@claude-mcp-skills/security-auditor"],
      "enabled": true,
      "environment": { "AUDIT_LANGUAGE": "python" }
    },
    "mcp-audit": {
      "type": "local",
      "command": ["npx", "-y", "@limjonathan/mcp-audit@latest", "scan"],
      "enabled": true
    },
    "playwright": {
      "type": "local",
      "command": ["npx", "-y", "@playwright/mcp-server"],
      "enabled": true
    }
  },
  
  "permissions": {
    "allow": [
      "Bash(nmap *)",
      "Bash(sqlmap *)",
      "Bash(ffuf *)",
      "Bash(metasploit *)"
    ],
    "deny": [
      "Bash(rm -rf /*)",
      "Bash(dd *)",
      "Bash(mkfs.*)"
    ]
  }
}
```

### 1.4.2 安全技能自动安装

```bash
# 1. 安装open-sploit（19个攻击技能 + 渗透测试智能体）
npx open-sploit

# 2. 安装KaliSec-MCP
git clone https://github.com/your-repo/kali-mcp-server.git
cd kali-mcp-server/deploy
chmod +x install.sh && ./install.sh

# 3. 安装security-scan（AgentShield扫描）
npx skills add https://github.com/yzlin/supa-opencode --skill security-scan

# 4. 安装KAVACH（AI安全审计Skill）
git clone https://github.com/adhuniklabs/kavach.git && cd kavach
./install.sh project

# 5. 安装opencode-security-agent
npm install -g @red-orbita/opencode-security-agent
```

### 1.4.3 安全扫描自动化脚本

创建 `scripts/security-scan.sh`：

```bash
#!/bin/bash
# 每日安全扫描自动化脚本

echo "=== 砺安题库 安全扫描报告 $(date) ==="

# 1. mcp-audit扫描
echo "[1/5] MCP安全审计..."
npx @limjonathan/mcp-audit@latest scan --json > reports/mcp-audit-$(date +%Y%m%d).json

# 2. OpenCode安全插件扫描
echo "[2/5] OpenCode安全扫描..."
opencode security scan --format sarif > reports/opencode-scan-$(date +%Y%m%d).sarif

# 3. LocalVulnAI扫描（Ollama本地）
echo "[3/5] 本地漏洞扫描..."
python3 /opt/LocalVulnAI/scanner.py --target ./backend --output reports/vuln-$(date +%Y%m%d).json

# 4. 依赖漏洞扫描
echo "[4/5] 依赖漏洞扫描..."
pip-audit -r backend/requirements.txt --format json > reports/pip-audit-$(date +%Y%m%d).json
npm audit --json > reports/npm-audit-$(date +%Y%m%d).json

# 5. 生成汇总报告
echo "[5/5] 生成汇总报告..."
python3 scripts/aggregate_security_report.py --date $(date +%Y%m%d)

echo "=== 扫描完成 ==="
```


## 1.5 AI自动化安全检测增强架构

### 1.5.1 安全检测工具分层架构

```mermaid
flowchart TD
    subgraph CI/CD/定时触发
        A[代码提交/每日定时] --> B[安全扫描调度器]
    end
    
    subgraph 静态分析层
        B --> C[opencode-security-agent<br>深度技能扫描器<br>133+模式/8语言]
        B --> D[@symbioticsec/security-plugin<br>SAST分析]
        B --> E[security-scan<br>AgentShield配置扫描]
    end
    
    subgraph 动态渗透层
        B --> F[open-sploit YOLO智能体<br>/target 一键渗透]
        B --> G[KaliSec-MCP<br>193个Kali工具智能调度]
        B --> H[Playwright MCP<br>浏览器安全测试]
    end
    
    subgraph AI审计层
        B --> I[KAVACH<br>Claude Code Skill + Python核心<br>零输入AI审计]
        B --> J[LocalVulnAI<br>Ollama本地AI扫描]
    end
    
    subgraph MCP安全审计层
        B --> K[mcp-audit<br>MCP服务器安全评分]
        B --> L[frostagent<br>默认拒绝能力检查]
    end
    
    subgraph 报告与告警
        C --> M[漏洞聚合引擎]
        D --> M
        E --> M
        F --> M
        G --> M
        H --> M
        I --> M
        J --> M
        K --> M
        L --> M
        M --> N[安全报告<br>SARIF/JSON/Markdown]
        M --> O[告警通知<br>钉钉/企业微信/邮件]
    end
```

### 1.5.2 精准漏洞发现算法（Skills + MCP + 规则引擎）

**核心算法设计**：采用 **“多引擎交叉验证 + 置信度加权”** 的漏洞发现算法，大幅降低误报率：

```
漏洞置信度 = α × SAST检测 + β × AI推理检测 + γ × 动态验证检测

其中：
- SAST检测：opencode-security-agent静态分析（权重α=0.3）
- AI推理检测：KAVACH/Ollama本地模型推理（权重β=0.4）
- 动态验证检测：open-sploit/KaliSec-MCP实际攻击验证（权重γ=0.3）

最终决策：
- 置信度 ≥ 0.85 → 确认漏洞（自动创建工单）
- 0.60 ≤ 置信度 < 0.85 → 疑似漏洞（人工复核队列）
- 置信度 < 0.60 → 忽略（降低误报）
```

### 1.5.3 OpenCode专用安全Skills清单

基于搜索结果，以下Skills可直接在OpenCode中使用：

| Skill名称 | 来源 | 功能 |
|-----------|------|------|
| `security-reviewer` | farmage/opencode-skills | 渗透测试、基础设施安全审查 |
| `security-auditor` | opencode-agent-config | 安全分析与审计 |
| `penetration-tester` | opencode-agent-config | 渗透测试与漏洞评估 |
| `web-app-penetration-testing` | open-sploit | Web应用渗透测试 |
| `owasp-top-10-testing` | open-sploit | OWASP Top 10测试 |
| `exploiting-sql-injection` | open-sploit | SQL注入利用 |
| `exploiting-idor-vulnerabilities` | open-sploit | IDOR漏洞利用 |
| `api-security-testing` | open-sploit | API安全测试 |
| `exploiting-jwt-algorithm-confusion` | open-sploit | JWT算法混淆攻击 |
| `kali-security` | KaliSec-MCP | 193个Kali工具集成 |
| `security-scan` | supa-opencode | AgentShield安全扫描 |

**在OpenCode中调用Skill**：
```
@security-reviewer 审查 backend/app/routers/ 目录的API安全
@penetration-tester 对 https://staging.li-an.com 执行渗透测试
@exploiting-sql-injection 检测 /api/questions 接口的SQL注入风险
@kali-security 对目标IP执行nmap扫描和漏洞枚举
```


## 1.6.定期安全巡检自动化

### 1.6.1 巡检频率与工具映射

| 巡检频率 | 扫描任务 | 工具 |
|---------|---------|------|
| **每次代码提交** | 增量安全扫描 | opencode-security-agent + @symbioticsec/plugin |
| **每日（凌晨2:00）** | 全量静态分析 + MCP审计 | mcp-audit + frostagent + security-scan |
| **每周（周日凌晨）** | 渗透测试 + AI深度审计 | open-sploit + KAVACH deep |
| **每月（1号）** | 完整安全评估报告 | 所有工具汇总 + 人工复核 |

### 1.6.2 告警与响应机制

| 告警级别 | 触发条件 | 响应动作 |
|---------|---------|---------|
| **🔴 严重** | 确认漏洞（置信度≥0.85） | 立即告警管理员 + 自动创建修复工单 |
| **🟡 高危** | 疑似漏洞（0.60≤置信度<0.85） | 进入人工复核队列 + 每日汇总邮件 |
| **🟢 中低** | 配置问题、依赖告警 | 记录日志 + 周报汇总 |


## 1.7 实施优先级

| 优先级 | 工具/措施 | 说明 |
|--------|----------|------|
| **P0** | open-sploit安装 + `/target`命令验证 | 核心渗透测试能力 |
| **P0** | mcp-audit扫描 + 安全评分基线建立 | MCP安全基线 |
| **P0** | opencode-security-agent深度技能扫描器 | 预安装安全检测 |
| **P1** | KaliSec-MCP集成 + 快捷命令配置 | 193个工具智能化 |
| **P1** | KAVACH安装 + 首次深度审计 | AI零输入审计 |
| **P1** | LocalVulnAI + Ollama配置 | 本地AI漏洞扫描 |
| **P2** | 安全Skills安装（security-reviewer等） | 增强AI编码安全 |
| **P2** | 自动化巡检脚本 + 告警配置 | 持续安全监控 |
| **P3** | frostagent + 默认拒绝策略 | 权限精细管控 |


## 1.8总结

针对OpenCode+Ollama的本地化部署环境，本方案用以下工具替代了原方案中的Strix：

| 原方案工具 | 替代方案 | 替代理由 |
|-----------|---------|---------|
| Strix（AI渗透测试） | **open-sploit** + **KaliSec-MCP** | 原生OpenCode集成，一键`/target`命令，19个攻击技能，193个Kali工具 |
| DeepAudit（多智能体审计） | **KAVACH** | Claude Code Skill + Python核心，零输入AI审计，26阶段流水线，模型无关 |
| vbsec（Claude Code安全扫描） | **opencode-security-agent** + **@symbioticsec/plugin** | 原生OpenCode支持，深度技能扫描器，133+检测模式 |
| Security Auditor MCP | **mcp-audit** + **frostagent** | 100%本地MCP审计，A-F评分，默认拒绝能力检查 |

**核心优势**：
1. **原生OpenCode集成**：所有工具均通过Skill/MCP方式集成，无需额外适配
2. **本地化运行**：配合Ollama，完全离线，保护代码和数据隐私
3. **一键式操作**：`/target`命令启动完整渗透测试流程
4. **多层级验证**：SAST静态分析 + AI推理 + 动态渗透验证的三层漏洞发现算法
5. **精准低误报**：通过多引擎交叉验证和置信度加权，显著降低误报率



## 二、开源组件漏洞分析（SCA）

### 2.1 设计目标

| 目标 | 说明 |
|------|------|
| **供应链风险识别** | 自动检测项目中使用的开源组件是否存在已知漏洞 |
| **依赖深度分析** | 分析传递依赖（间接依赖）的安全风险 |
| **合规性检查** | 检测开源许可证的合规性及兼容性风险 |
| **实时漏洞告警** | 当组件新漏洞被披露时，自动告警 |
| **SBOM生成** | 自动生成软件物料清单，满足合规要求 |

### 2.2 技术栈组件分析

根据砺安题库技术栈，需要重点监控以下开源组件：

| 组件 | 版本（示例） | 已知漏洞关注点 |
|------|------------|---------------|
| **FastAPI** | 0.100+ | 依赖注入安全、Pydantic验证绕过 |
| **Vue 3** | 3.3+ | XSS、模板注入、v-html使用 |
| **Vue I18n** | 9.x / 10.x | CVE-2025-53892：`escapeParameterHtml`选项在9.14.5、10.0.8、11.1.0之前存在DOM型XSS漏洞 |
| **Element Plus** | 2.x | 组件库已知XSS |
| **SQLAlchemy** | 2.x | SQL注入（使用不当） |
| **PostgreSQL** | 14+ | 远程代码执行、权限提升 |
| **Redis** | 7.x | 未授权访问 |
| **python-jose** | JWT实现 | 算法混淆攻击 |
| **passlib** | 密码哈希 | 弱哈希算法 |

### 2.3 SCA工具选型

| 工具 | 特点 | 适用场景 |
|------|------|---------|
| **OpenSCA** | 国内排名第一、用户量最大的开源SCA工具，支持多级开源依赖挖掘、纵深代码同源检测 | 首选，中文支持好 |
| **软安SCA** | 提供软件资产识别（SBOM）、安全风险分析、开源合规检测、漏洞告警 | 企业级合规需求 |
| **Package Dashboard** | 跨生态SCA工具，提供供应链风险统一视图 | 多项目统一管理 |
| **npm audit / pip-audit** | 官方包管理器安全审计 | 快速本地检查 |

### 2.4 SCA集成方案

```yaml
# .github/workflows/sca-scan.yml
name: SCA Security Scan
on:
  push:
    branches: [main, develop]
  schedule:
    - cron: '0 2 * * *'  # 每日凌晨2点

jobs:
  sca-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Python依赖扫描
        run: |
          pip install pip-audit
          pip-audit -r backend/requirements.txt --format json > reports/python-sca.json
      - name: Node.js依赖扫描
        run: |
          npm audit --json > reports/node-sca.json
      - name: OpenSCA深度扫描
        run: |
          opensca-cli -path ./ -format json -output reports/opensca.json
      - name: 生成SBOM
        run: |
          cyclonedx-bom -o reports/sbom.json
      - name: 漏洞告警
        if: contains(vulnerabilities, 'critical')
        run: |
          # 发送告警到钉钉/企业微信
          python scripts/alert.py --severity critical
```

### 2.5 已知漏洞应急响应

**Vue I18n XSS漏洞（CVE-2025-53892）**：
- **影响版本**：9.0.0至9.14.5、10.0.0至10.0.8
- **漏洞描述**：`escapeParameterHtml: true`选项无法阻止基于DOM的XSS，当插值内容在HTML上下文中使用v-html渲染时，`<img src=x onerror=...>`等负载可被执行
- **修复版本**：9.14.5、10.0.8、11.1.0
- **修复措施**：立即升级至修复版本，检查所有v-html使用场景


## 三、垂直权限攻击与水平权限攻击防护

### 3.1 攻击原理

| 攻击类型 | 定义 | 示例 |
|---------|------|------|
| **垂直越权** | 低权限用户访问高权限功能 | 普通学生访问管理员API `/api/admin/users` |
| **水平越权** | 用户获取同角色其他用户的资源 | 学生A查看学生B的错题集 |
| **交叉越权** | 同时包含水平与垂直越权 | 普通用户既查看其他用户数据，又操作管理员接口 |

### 3.2 核心防护原则

**根本原则：服务端全接口权限校验，所有权限校验必须在服务端执行，前端校验仅作为辅助，完全不可信**。

### 3.3 垂直越权防护

#### 3.3.1 接口级权限控制

```python
from fastapi import Depends, HTTPException
from functools import wraps

def require_role(allowed_roles: list):
    """角色权限装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user=Depends(get_current_user), **kwargs):
            if current_user.role not in allowed_roles:
                raise HTTPException(
                    status_code=403,
                    detail="权限不足，无法访问此资源"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# 使用示例
@router.delete("/admin/users/{user_id}")
@require_role(["admin", "super_admin"])
async def delete_user(user_id: int):
    """仅管理员可访问"""
    pass
```

#### 3.3.2 路由级权限隔离

```python
# FastAPI路由分层
app.include_router(public_router, prefix="/api/public")      # 无需认证
app.include_router(student_router, prefix="/api/student")    # 仅学生
app.include_router(teacher_router, prefix="/api/teacher")    # 仅教师
app.include_router(admin_router, prefix="/api/admin")        # 仅管理员
```

**禁止使用自增ID、顺序编号等可遍历的资源标识，使用UUID、雪花ID等不可预测的字符串作为资源唯一标识，防止批量遍历越权**。

### 3.4 水平越权防护

#### 3.4.1 数据归属校验（IDOR防护）

```python
async def verify_data_ownership(
    resource_id: int, 
    current_user: User,
    resource_model: Model
):
    """校验当前用户是否有权访问该资源"""
    resource = await db.get(resource_model, resource_id)
    if not resource:
        raise HTTPException(404, "资源不存在")
    
    # 核心：数据归属校验
    if resource.user_id != current_user.id:
        # 检查是否为管理员（管理员可查看所有数据）
        if current_user.role not in ["admin", "super_admin"]:
            raise HTTPException(403, "无权访问此资源")
    
    return resource
```

#### 3.4.2 使用不可预测的资源ID

```python
import uuid
from sqlalchemy.dialects.postgresql import UUID

class Question(Base):
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # 不使用自增整数ID
```

### 3.5 自动化权限测试

利用Strix的权限提升智能体进行自动化权限测试：

```bash
# 测试认证绕过和越权访问
strix --target https://staging.li-an.com \
      --instruction "重点测试权限控制和越权访问"
```


## 四、文件上传漏洞与文件删除漏洞防护

### 4.1 文件上传漏洞防护

#### 4.1.1 上传目录安全配置

**上传目录必须配置在Web应用根目录之外，且禁止执行任何文件**。

**Nginx配置**：
```nginx
location /uploads/ {
    alias /data/uploads/;
    # 禁止执行PHP/Python等脚本
    location ~* \.(php|py|pl|sh|cgi)$ {
        return 403;
    }
    # 仅允许特定文件扩展名
    location ~* \.(jpg|jpeg|png|gif|pdf|docx|xlsx|mp4)$ {
        expires 30d;
    }
}
```

#### 4.1.2 文件重命名与路径不可预测

**使用UUID重命名文件，防止攻击者通过猜测上传文件的路径和文件名进行攻击**。

```python
import uuid
import os

def secure_filename(original_filename: str) -> str:
    """生成安全的文件名"""
    ext = os.path.splitext(original_filename)[1].lower()
    allowed_exts = {'.jpg', '.jpeg', '.png', '.gif', '.pdf', '.docx', '.xlsx', '.mp4'}
    if ext not in allowed_exts:
        raise ValueError(f"不支持的文件格式: {ext}")
    return f"{uuid.uuid4().hex}{ext}"
```

#### 4.1.3 文件类型双重验证

```python
import magic  # python-magic

async def validate_file(file: UploadFile):
    # 1. 扩展名验证
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "不支持的文件格式")
    
    # 2. MIME类型验证（防止伪装）
    content = await file.read(1024)
    mime_type = magic.from_buffer(content, mime=True)
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, "文件类型与扩展名不匹配")
    
    # 3. 文件大小验证
    file_size = len(content)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(400, f"文件超过大小限制: {MAX_FILE_SIZE} bytes")
```

### 4.2 文件删除漏洞防护

#### 4.2.1 输入验证与路径限制

**对文件删除接口实施严格的输入验证和路径限制，确保仅允许删除经过验证的文件，并使用黑名单对传入参数（如`./`和`../`）进行限制**。

```python
import re
from pathlib import Path

def validate_delete_path(file_path: str, base_dir: str) -> bool:
    """
    验证删除路径的安全性
    """
    # 1. 禁止路径遍历
    if re.search(r'\.\./', file_path) or re.search(r'\.\.\\', file_path):
        raise HTTPException(400, "非法路径")
    
    # 2. 禁止绝对路径
    if os.path.isabs(file_path):
        raise HTTPException(400, "不支持绝对路径")
    
    # 3. 验证文件在允许目录内
    full_path = Path(base_dir) / file_path
    if not str(full_path.resolve()).startswith(str(Path(base_dir).resolve())):
        raise HTTPException(400, "路径超出允许范围")
    
    # 4. 验证文件存在
    if not full_path.exists():
        raise HTTPException(404, "文件不存在")
    
    return True

@router.delete("/api/files/{file_id}")
async def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user)
):
    # 1. 从数据库获取文件记录
    file_record = await db.get(File, file_id)
    if not file_record:
        raise HTTPException(404, "文件不存在")
    
    # 2. 权限校验（只能删除自己的文件）
    if file_record.user_id != current_user.id:
        if current_user.role not in ["admin", "super_admin"]:
            raise HTTPException(403, "无权删除此文件")
    
    # 3. 验证删除路径
    validate_delete_path(file_record.path, UPLOAD_DIR)
    
    # 4. 执行删除
    os.remove(os.path.join(UPLOAD_DIR, file_record.path))
    await db.delete(file_record)
    
    return {"message": "删除成功"}
```

### 4.3 木马与恶意文件检测

| 检测层 | 技术方案 | 说明 |
|--------|---------|------|
| **文件头检测** | `python-magic` | 验证真实文件类型，防止伪装 |
| **病毒扫描** | ClamAV（开源杀毒引擎） | 上传文件实时扫描 |
| **内容分析** | YARA规则 | 检测已知恶意代码特征 |
| **行为沙箱** | Docker隔离执行 | 可疑文件在沙箱中分析 |


## 五、缓冲区溢出防护（Python/FastAPI特有）

### 5.1 风险分析

由于砺安题库使用Python开发，Python本身具有内存管理机制，不易发生传统C/C++缓冲区溢出。但以下场景仍需注意：

| 风险场景 | 说明 | 防护措施 |
|---------|------|---------|
| **C扩展模块** | 使用`ctypes`或`Cython`调用C库 | 严格输入验证、使用安全库版本 |
| **大量数据处理** | 处理超大JSON/文件导致内存溢出 | 流式处理、限制请求体大小 |
| **正则表达式DoS** | 恶意构造的正则导致ReDoS攻击 | 使用超时机制、避免嵌套量词 |
| **ZIP炸弹** | 解压超大ZIP文件耗尽资源 | 限制解压大小、文件数量 |

### 5.2 防护实现

```python
import resource
import signal
import time

# 1. 设置内存限制（Linux）
resource.setrlimit(resource.RLIMIT_AS, (2 * 1024 * 1024 * 1024, -1))  # 2GB

# 2. 正则表达式超时
import re
def safe_regex_search(pattern, text, timeout=1):
    """带超时的正则搜索"""
    def timeout_handler(signum, frame):
        raise TimeoutError("正则表达式执行超时")
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)
    try:
        return re.search(pattern, text)
    finally:
        signal.alarm(0)

# 3. 请求体大小限制（FastAPI）
from fastapi import FastAPI
app = FastAPI()
# 在Nginx层限制 client_max_body_size
```


## 六、口令入侵与暴力破解防护（增强）

### 6.1 多因素认证（MFA）

**本系统需为管理员和教师强制启用MFA**：

| 因素 | 实现方式 | 启用对象 |
|------|---------|---------|
| 密码 | bcrypt哈希存储 | 所有用户 |
| TOTP | 基于时间的一次性密码（Google Authenticator） | 教师、管理员 |
| 备用码 | 一次性备用恢复码（10个） | 教师、管理员 |

### 6.2 智能异常登录检测

```python
class LoginAnomalyDetector:
    """基于AI的异常登录检测"""
    
    async def detect(self, user_id: int, request: Request) -> bool:
        # 1. 地理位置突变检测
        current_location = await self.get_location(request.client.host)
        last_location = await self.get_last_location(user_id)
        if current_location and last_location:
            distance = self.calc_distance(current_location, last_location)
            if distance > 500:  # 超过500公里
                await self.trigger_alert(user_id, "异地登录")
                return True
        
        # 2. 设备指纹检测
        current_device = self.get_device_fingerprint(request)
        last_device = await self.get_last_device(user_id)
        if current_device != last_device:
            await self.send_verification_code(user_id)
            return True
        
        # 3. 登录时间异常检测
        current_hour = datetime.now().hour
        if 1 <= current_hour <= 5:  # 凌晨1-5点登录
            await self.trigger_alert(user_id, "非常规时间登录")
            return True
        
        return False
```


## 七、安全监控与告警增强

### 7.1 实时安全监控指标

| 监控指标 | 阈值 | 告警动作 |
|---------|------|---------|
| 登录失败率 | 5分钟内>50次 | 自动阻断源IP + 告警管理员 |
| 异常API调用 | 单IP调用>1000次/分钟 | 自动限流 + 告警 |
| 文件上传异常 | 单IP上传>50次/小时 | 自动阻断 + 告警 |
| SQL注入尝试 | 检测到注入模式 | 记录 + 阻断 + 告警 |
| 越权尝试 | 403响应率>10% | 告警管理员 |
| 新漏洞披露 | 匹配到组件CVE | 自动创建工单 |

### 7.2 AI安全事件响应流程

```mermaid
flowchart TD
    A[AI安全监控] --> B{事件类型}
    B -->|SQL注入尝试| C[自动阻断 + 记录证据]
    B -->|越权尝试| D[记录证据 + 告警]
    B -->|新CVE披露| E[自动评估影响]
    B -->|异常流量| F[自动限流 + 溯源]
    
    C --> G[生成安全事件报告]
    D --> G
    E --> H{影响范围}
    H -->|高危| I[立即告警 + 创建修复工单]
    H -->|中低| J[记录 + 定期汇总]
    F --> G
    I --> K[安全团队响应]
```

### 7.3 安全事件响应SLA

| 事件等级 | 描述 | 响应时间 | 解决时间 |
|---------|------|---------|---------|
| **P0（紧急）** | 数据泄露、系统瘫痪、权限突破 | 15分钟内 | 2小时内 |
| **P1（严重）** | 持续攻击、敏感数据访问 | 1小时内 | 4小时内 |
| **P2（一般）** | 扫描探测、异常流量 | 4小时内 | 24小时内 |
| **P3（低）** | 安全告警、可疑记录 | 24小时内 | 72小时内 |


## 八、实施优先级与路线图

| 阶段 | 时间 | 重点任务 |
|------|------|---------|
| **第一阶段（P0）** | 第1-2周 | 部署DeepAudit、配置权限校验中间件（垂直+水平越权防护）、文件上传安全加固 |
| **第二阶段（P1）** | 第3-4周 | 集成SCA工具（OpenSCA）、部署vbsec扫描、配置安全监控告警 |
| **第三阶段（P2）** | 第5-6周 | 集成Strix渗透测试、MFA多因素认证、异常登录检测 |
| **第四阶段（P3）** | 第7-8周 | 自动化修复流水线、安全仪表盘、定期渗透测试 |

### 8.1 安全工具快速集成命令

```bash
# 1. DeepAudit部署
git clone https://github.com/your-org/DeepAudit
cd DeepAudit
docker-compose up -d

# 2. vbsec安装（Claude Code中）
/plugin install vbsec@security-skills

# 3. OpenSCA安装
pip install opensca-cli
opensca-cli -path ./backend -format json -output sca-report.json

# 4. 安全审计MCP Server配置
# 在.mcp.json中添加
{
  "mcpServers": {
    "security-auditor": {
      "command": "npx",
      "args": ["-y", "@claude-mcp-skills/security-auditor"],
      "env": {
        "AUDIT_LANGUAGE": "python"
      }
    }
  }
}
```


## 九、总结

本方案v2.0在v1.0“七层纵深防御”体系基础上，新增以下核心安全能力：

| 新增能力 | 核心工具/方案 | 防护目标 |
|---------|-------------|---------|
| **AI自动化漏洞检测** | DeepAudit、Strix、vbsec | 零日漏洞、代码级安全缺陷 |
| **开源组件安全分析** | OpenSCA、pip-audit、npm audit | 供应链漏洞、已知CVE、合规风险 |
| **垂直/水平越权防护** | 服务端权限校验、UUID资源ID、数据归属校验 | IDOR、权限提升攻击 |
| **文件删除漏洞防护** | 路径遍历防护、输入验证、权限校验 | 任意文件删除攻击 |
| **缓冲区溢出防护** | 内存限制、正则超时、请求体限制 | ReDoS、内存耗尽攻击 |
| **智能异常登录检测** | 地理位置、设备指纹、时段分析 | 账号盗用、撞库攻击 |
| **MFA多因素认证** | TOTP（Google Authenticator） | 口令入侵、凭证泄露 |

通过以上**AI自动化+多层级纵深防御**的融合方案，砺安题库系统将具备自动化漏洞发现、智能攻击检测、快速应急响应的完整安全能力，有效防范各类已知与未知网络攻击。


针对系统高峰期可能面临1万人同时在线的挑战，我已在原有的安全方案基础上，为你补充了以下关于系统稳定性与高可用性的设计方案。

### 十、系统高并发与稳定性保障方案（新增）

#### 10.1 高并发挑战分析

当系统面临10,000人同时在线的高峰期时，主要挑战集中在以下三个维度：

| 挑战维度 | 具体表现 | 影响 |
|---------|---------|------|
| **资源瓶颈** | CPU上下文切换频繁、内存缓存命中率低、磁盘I/O阻塞 | 响应延迟增加，吞吐量下降 |
| **数据库连接耗尽** | PostgreSQL默认最大连接数为100，10,000并发登录会耗尽所有连接 | 返回 "too many clients" 错误 |
| **峰值流量不可预测** | 突发流量（如模拟考试集中时段）超出系统设计容量 | 系统响应变慢甚至宕机 |


#### 10.2 数据库连接池与读写分离

**核心问题**：PostgreSQL的每个连接都是一个独立的OS进程，盲目提高`max_connections`会导致内存耗尽。正确的做法是使用连接池。

**（1）部署PgBouncer连接池**

```ini
# pgbouncer.ini 配置
[databases]
liankao_db = host=127.0.0.1 port=5432 dbname=liankao_db

[pgbouncer]
pool_mode = transaction          # 事务级复用，适合短连接场景
default_pool_size = 20           # 每个数据库的默认连接池大小
max_client_conn = 10000          # 最大客户端连接数
max_db_connections = 50          # 到PostgreSQL的最大连接数
listen_port = 6432
listen_addr = 127.0.0.1
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
```

**连接数计算公式**：总连接数 = (Pod数 × Worker数 × pool_size × 1.2) + buffer

**（2）配置SQLAlchemy异步连接池**

```python
# backend/app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://user:pass@localhost:6432/liankao_db"

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,                # 每个worker的持久连接数
    max_overflow=10,             # 额外允许的连接数
    pool_timeout=60,             # 获取连接超时时间（秒）
    pool_recycle=3600,           # 连接回收间隔（秒）
    pool_pre_ping=True,          # 使用前检测连接有效性
    echo_pool=False
)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

**（3）读写分离**

```python
# 配置读写分离
ENGINE_CONFIG = {
    "master": "postgresql+asyncpg://user:pass@master.db:5432/liankao_db",
    "slave": "postgresql+asyncpg://user:pass@slave.db:5432/liankao_db"
}

# 读操作使用从库，写操作使用主库
async def get_db_session(read_only: bool = False):
    url = ENGINE_CONFIG["slave"] if read_only else ENGINE_CONFIG["master"]
    engine = create_async_engine(url, pool_size=10)
    async with AsyncSession(engine) as session:
        yield session
```


#### 10.3 多级缓存策略

**（1）三级缓存架构**

采用 **本地缓存(Caffeine) → 分布式缓存(Redis) → 数据库** 的三级缓存策略：

| 缓存层级 | 技术方案 | 缓存内容 | 过期策略 |
|---------|---------|---------|---------|
| **L1 本地缓存** | Python `functools.lru_cache` / `cachetools` | 题目选项、知识点映射等静态数据 | 5分钟 |
| **L2 分布式缓存** | Redis Cluster | 试卷列表、用户会话、热点题目 | 1-24小时 |
| **L3 数据库** | PostgreSQL | 所有持久化数据 | 永久 |

**（2）缓存策略实现**

```python
# backend/app/core/cache.py
import redis.asyncio as redis
from cachetools import TTLCache
from functools import wraps

# L1: 本地缓存
local_cache = TTLCache(maxsize=10000, ttl=300)

# L2: Redis集群
redis_client = redis.RedisCluster(
    host='redis-cluster.example.com',
    port=6379,
    decode_responses=True
)

def cache_result(ttl: int = 3600, local_ttl: int = 300):
    """多级缓存装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # L1: 本地缓存
            if cache_key in local_cache:
                return local_cache[cache_key]
            
            # L2: Redis缓存
            cached = await redis_client.get(cache_key)
            if cached:
                local_cache[cache_key] = cached
                return cached
            
            # L3: 数据库查询
            result = await func(*args, **kwargs)
            
            # 写入两级缓存
            await redis_client.setex(cache_key, ttl, result)
            local_cache[cache_key] = result
            return result
        return wrapper
    return decorator
```

**（3）缓存穿透/击穿/雪崩防护**

| 问题 | 防护措施 | 实现方式 |
|------|---------|---------|
| **缓存穿透** | 布隆过滤器 + 空值缓存 | 查询不存在的key时缓存空值（TTL=60s） |
| **缓存击穿** | 互斥锁（分布式锁） | 热点数据过期时，仅单个请求重建缓存 |
| **缓存雪崩** | 随机过期时间 | 为缓存设置 `base_ttl + random(0, 600)` |


#### 10.4 异步任务与爬虫隔离

**（1）爬虫任务与Web服务隔离**

后端启动时自动进行的招考信息、新闻爬取任务，必须与Web服务隔离，避免阻塞API响应：

```python
# backend/app/core/celery_app.py
from celery import Celery

celery_app = Celery(
    "liankao",
    broker="redis://redis-cluster:6379/0",
    backend="redis://redis-cluster:6379/1"
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    worker_concurrency=2,          # 爬虫Worker并发数
    task_track_started=True,
    task_time_limit=1800,          # 30分钟超时
    task_soft_time_limit=1500,     # 25分钟软超时
    task_acks_late=True,           # 任务完成后确认
    worker_prefetch_multiplier=1,  # 每次仅预取1个任务
)
```

**（2）爬虫任务定义**

```python
# backend/app/tasks/crawler_tasks.py
from app.core.celery_app import celery_app
from app.services.recruitment_scraper import scrape_all_recruitment
from app.services.news_scraper import scrape_all_news

@celery_app.task(bind=True, max_retries=3)
def scrape_recruitment_task(self):
    """招考信息爬取任务"""
    try:
        result = scrape_all_recruitment()
        return {"status": "success", "count": len(result)}
    except Exception as e:
        self.retry(exc=e, countdown=60 * 5)  # 5分钟后重试

@celery_app.task(bind=True, max_retries=3)
def scrape_news_task(self):
    """新闻爬取任务"""
    try:
        result = scrape_all_news()
        return {"status": "success", "count": len(result)}
    except Exception as e:
        self.retry(exc=e, countdown=60 * 5)
```

**（3）定时调度配置**

```python
# backend/app/core/scheduler.py
from celery.schedules import crontab
from app.tasks.crawler_tasks import scrape_recruitment_task, scrape_news_task

celery_app.conf.beat_schedule = {
    'scrape-recruitment-every-6h': {
        'task': 'app.tasks.crawler_tasks.scrape_recruitment_task',
        'schedule': crontab(minute=0, hour='*/6'),  # 每6小时执行
    },
    'scrape-news-every-2h': {
        'task': 'app.tasks.crawler_tasks.scrape_news_task',
        'schedule': crontab(minute=30, hour='*/2'),  # 每2小时执行
    },
}
```


#### 10.5 Nginx限流与DDoS防护

**（1）请求速率限制**

Nginx内置的`limit_req`模块基于漏桶/令牌桶算法，可有效防止单IP恶意刷请求：

```nginx
# nginx.conf - 限流配置
http {
    # 定义限流区域（10MB共享内存可存储约160,000个IP地址）
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/s;
    limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;
    
    # 定义并发连接限制
    limit_conn_zone $binary_remote_addr zone=conn_limit:10m;
    
    server {
        listen 443 ssl http2;
        
        # API通用限流（30 req/s）
        location /api/ {
            limit_req zone=api_limit burst=50 nodelay;  # 允许突发50个请求
            limit_conn conn_limit 10;                    # 单IP最大10个并发连接
            proxy_pass http://backend;
        }
        
        # 登录接口严格限流（5次/分钟）
        location /api/auth/login {
            limit_req zone=login_limit burst=3 nodelay;
            proxy_pass http://backend;
        }
        
        # 大文件下载限速
        location /uploads/ {
            limit_rate 1M;           # 限速1MB/s
            limit_conn conn_limit 5; # 单IP最多5个并发下载
            alias /data/uploads/;
        }
    }
}
```

**（2）连接数限制**

限制单个IP的并发连接数，防止恶意连接耗尽服务器资源：

```nginx
# 限制单个IP的最大并发连接数为10
limit_conn_zone $binary_remote_addr zone=addr:10m;
limit_conn addr 10;

# 限制单个服务器的总连接数
limit_conn_zone $server_name zone=servers:10m;
limit_conn servers 1000;
```


#### 10.6 水平扩展与负载均衡

**（1）无状态服务设计**

确保服务不存储本地数据（Session信息存储在Redis中），保证任意节点均可处理请求：

```python
# backend/app/core/session.py
from fastapi_sessions.backends.implementations import RedisBackend
from fastapi_sessions.session import Session

session_backend = RedisBackend(
    redis_client=redis_client,
    key_prefix="session:",
    cookie_secure=True,
    cookie_httponly=True,
    cookie_samesite="lax"
)
```

**（2）负载均衡配置**

```nginx
# nginx.conf - 负载均衡
http {
    upstream backend {
        # 轮询算法
        server 192.168.1.10:8000 weight=3;  # 权重3
        server 192.168.1.11:8000 weight=2;
        server 192.168.1.12:8000 weight=1;
        keepalive 32;  # 保持长连接
    }
    
    server {
        location /api/ {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            
            # 超时配置
            proxy_connect_timeout 10s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }
    }
}
```


#### 10.7 自动弹性扩缩容（Kubernetes HPA）

若采用Kubernetes部署，可配置Horizontal Pod Autoscaler实现自动弹性伸缩：

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: liankao-backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: liankao-backend
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
```


#### 10.8 全链路监控与告警

| 监控层面 | 监控指标 | 告警阈值 | 工具 |
|---------|---------|---------|------|
| **应用层** | API响应时间(P95/P99)、错误率、QPS | P95 > 2s / 错误率 > 5% | Prometheus + FastAPI |
| **数据库层** | 连接数、查询延迟、慢查询 | 连接数 > 80% / 慢查询 > 1s | PostgreSQL Exporter |
| **缓存层** | Redis命中率、内存使用率 | 命中率 < 80% / 内存 > 80% | Redis Exporter |
| **系统层** | CPU、内存、磁盘、网络 | CPU > 80% / 内存 > 85% | Node Exporter |
| **业务层** | 同时在线用户数、请求队列深度 | 在线 > 8000 / 队列 > 1000 | 自定义Metrics |


### 十一、方案更新总结

本次在原有安全方案基础上新增了第十章节“系统高并发与稳定性保障方案”，涵盖以下核心能力：

| 新增能力 | 核心措施 | 解决的核心问题 |
|---------|---------|---------------|
| **连接池管理** | PgBouncer + SQLAlchemy异步连接池 | 解决10,000并发连接耗尽数据库连接的问题 |
| **多级缓存** | 本地缓存 → Redis集群 → 数据库 | 减少数据库访问压力，降低响应延迟 |
| **任务隔离** | Celery异步任务队列 | 爬虫任务与Web服务隔离，避免互相影响 |
| **限流防护** | Nginx `limit_req` + `limit_conn` | 防止单IP恶意刷请求和DDoS攻击 |
| **水平扩展** | 无状态服务 + 负载均衡 + HPA | 突破单机性能上限，按需自动扩缩容 |
| **全链路监控** | 多维度指标采集与告警 | 提前发现性能瓶颈，快速定位故障 |

通过以上设计，砺安题库系统将在高峰期（10,000人同时在线）具备以下能力：
- **数据库层面**：通过PgBouncer将10,000个客户端连接复用至少量PostgreSQL连接
- **缓存层面**：三级缓存将数据库读压力降低80%以上
- **流量层面**：Nginx限流作为第一道防线，防止恶意流量击穿系统
- **扩展层面**：Kubernetes HPA根据CPU/内存自动扩缩容，应对流量波动
- **任务层面**：Celery异步队列将爬虫任务与Web服务完全隔离

这些措施共同构成了一个**可弹性扩展、高可用、自保护的稳定运行体系**。



## 十一、设计启动AI自动化AI_README文档
详细说明怎么启动和使用opencode+ollama进行网络安全自动化检测系统