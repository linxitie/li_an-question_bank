# 推送脚本（push-main.ps1）运维说明 v1

> 位置：`scripts/push-main.ps1`
> 适用：本机 DNS 把 `github.com` 解析到被黑洞 IP（20.205.243.166）时，普通 `git push` 卡 21 秒后失败。

## 1. 现象与根因

```
git push origin main
→ fatal: unable to access 'https://github.com/...': Failed to connect to github.com port 443 after 21104 ms
```

实测同一时刻：

| 目标 | 结果 |
|---|---|
| `github.com`（DNS → 20.205.243.166） | :443 不通 |
| `140.82.113.3` / `140.82.112.3` / `20.27.177.113` | :443 通 |
| `codeload.github.com` / `api.github.com` | :443 通 |
| gitee.com / baidu.com | 200（整体网络正常） |

结论：**不是断网，是 DNS 解析到的那个 GitHub IP 被墙**。git 支持用
`-c http.curloptResolve=github.com:443:<IP>` 绕过 DNS 直连可用 IP。

## 2. 用法

```powershell
# 正常推送（远端领先会提示，不自动合并）
.\scripts\push-main.ps1

# 远端领先时自动合并 origin/main 后再推
.\scripts\push-main.ps1 -Merge

# 自定义合并提交信息
.\scripts\push-main.ps1 -Merge -Message "merge: 同步远端"
```

参数：`-Remote`（默认 origin）、`-Branch`（默认 main）。

## 3. 脚本做了什么

1. **预检**：当前分支必须是 main、工作区必须干净；
2. **普通 push**：先试一次（DNS 正常时最快）；
3. **探测 IP**：依次 TCP 测 `140.82.113.3 / 140.82.112.3 / 140.82.114.3 / 20.27.177.113 / 20.205.243.166`；
4. **fetch + 差距检查**：落后远端时提示（或 `-Merge` 自动合并）；
5. **带 IP 覆盖 push**：`git -c http.curloptResolve=github.com:443:<IP> push origin main`。

退出码：`0` 成功/无需推送；`1` 失败（工作区脏、合并冲突、网络不可达）；`2` 远端领先且未加 `-Merge`。

## 4. 实测记录（2026-11-05）

```
.\scripts\push-main.ps1
== 预检 ==
   ✓ 分支 main
   × 工作区有未提交改动，先提交再推送：
       ?? scripts/push-main.ps1        ← 脚本自身未提交时的正确拦截
```

提交后重跑：

```
== 预检 == ✓ 分支 main ✓ 工作区干净
== 尝试普通 push == 失败（已知 DNS 问题）
== 探测 GitHub 可用 IP == 140.82.113.3 可达 ...
== 同步远端状态 == fetch 成功；落后 0 / 领先 0 → 无需推送
```

真实推送：`git -c http.curloptResolve=github.com:443:140.82.113.3 push origin main`
→ `3032b11d..cf42b447 main -> main` ✅

## 5. 注意

- 候选 IP 是 GitHub 官方地址段，会变；脚本每次运行都会**重新探测**，不用手工维护。
- 若所有 IP 都不通，可能是真断网或需要代理：
  `git config --global http.proxy http://127.0.0.1:<端口>`。
- 脚本不改任何全局 git 配置，只对单条命令加 `-c`。
