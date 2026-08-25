# MinerU 部署记录（T0）

## 结论：✅ 部署成功，系统可调用（2026-08-25）

| 项 | 值 |
|---|---|
| MinerU 版本 | mineru[all]（PyPI 最新稳定版，pipeline 后端）|
| Python | uv 托管 CPython **3.11.15**（主环境 3.13.5 不兼容 ray，已规避）|
| venv 位置 | `C:\mineru_env` ⚠️ 必须纯 ASCII 路径（见下方坑点）|
| 模型源 | `MINERU_MODEL_SOURCE=modelscope`（国内镜像）|
| CLI 调用 | `C:\mineru_env\Scripts\mineru.exe -p <in> -o <out> -b pipeline` |
| 验收样例 | 图片型 PDF（中文文档截图转 PDF，0 文字层）|
| **基准耗时** | **71.2s / 单页**（CPU pipeline，含模型热加载；首次冷启动另计模型下载时间）|
| OCR 质量 | cjk_in_head=113，与源文本逐句一致 ✅ |

## 🕳️ 关键坑点（运维必读）

### 坑 1：非 ASCII 安装路径导致 FastText 加载失败
- **现象**：`fast_langdetect ... lid.176.ftz cannot be opened for loading!`
- **根因**：项目位于 `D:\砺安题库\砺安题库\`（中文路径），FastText 的 C++ 文件读取层不支持非 ANSI 路径。
- **解决**：venv 迁移至 `C:\mineru_env`。**任何情况下不要把该 venv 移回中文目录**。

### 坑 2：主环境 Python 3.13 不被支持
- ray 等依赖不支持 3.13+，故用 `uv python install 3.11` + `uv venv --python 3.11` 构建独立解释器。

### 坑 3：长任务超时
- CPU 解析单页约 70s+，多页扫描件可达分钟级 → 业务层必须异步 + 轮询（见实施计划 T5/T6 设计），且子进程超时熔断设 600s。

## 自检脚本

```powershell
$env:MINERU_MODEL_SOURCE="modelscope"
python backend\scripts\verify_mineru.py <任意PDF>          # 完整链路
python backend\scripts\verify_mineru.py <任意PDF> --text   # 仅测文字层(路由判定用)
```

## 对业务代码的约束传递

1. `backend/app/services/mineru_service.py` 的 `MINERU_EXE` 常量 = `C:\mineru_env\Scripts\mineru.exe`
2. subprocess 启动时 env 必须带 `MINERU_MODEL_SOURCE=modelscope`
3. 输入/输出文件路径经 Python 传参不受中文影响（仅 venv 内部资源加载受影响）
4. 主服务 requirements.txt **不得**加入 mineru/torch —— 保持子进程隔离
