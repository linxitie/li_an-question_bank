"""
后端启动入口（带看门狗自愈）
使用方式: python start.py

P1.4 进程守护：后端子进程异常退出（如第三方原生库崩溃）时自动重启，
避免系统瘫痪直至人工干预。连续异常超过阈值则放弃重启并提示排查。
"""
import os
import sys
import time
import subprocess

MAX_CONSECUTIVE_RESTARTS = 20   # 连续崩溃上限（防死循环）
RESTART_DELAY = 3               # 重启间隔秒数


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    cmd = [
        sys.executable, '-m', 'uvicorn', 'app.main:app',
        '--host', '0.0.0.0', '--port', '8000', '--log-level', 'info',
    ]
    consecutive = 0
    while True:
        print(f"[watchdog] 启动后端: {' '.join(cmd)}", flush=True)
        proc = subprocess.run(cmd)
        if proc.returncode == 0:
            print("[watchdog] 后端正常退出", flush=True)
            break
        consecutive += 1
        print(f"[watchdog] ⚠️ 后端异常退出 code={proc.returncode}，"
              f"{RESTART_DELAY}秒后自动重启（连续第{consecutive}次）", flush=True)
        if consecutive >= MAX_CONSECUTIVE_RESTARTS:
            print(f"[watchdog] ❌ 连续崩溃 {consecutive} 次，放弃重启。"
                  "请查看 logs/app.log 排查根因后手动启动。", flush=True)
            sys.exit(1)
        time.sleep(RESTART_DELAY)


if __name__ == "__main__":
    main()
