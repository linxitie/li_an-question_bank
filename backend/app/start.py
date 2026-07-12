#!/usr/bin/env python
"""
公安联考题库系统启动脚本
"""
import subprocess
import sys
import os

def main():
    # 设置环境变量 - 修复：需要指向 backend 目录（app 的父目录）
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)  # backend/app -> backend
    os.environ.setdefault("PYTHONPATH", parent_dir)

    # 切换工作目录到 backend 目录
    os.chdir(parent_dir)

    # 安装依赖（如果需要）
    if len(sys.argv) > 1 and sys.argv[1] == "install":
        print("安装依赖...")
        requirements_file = os.path.join(parent_dir, "requirements.txt")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", requirements_file])
        print("依赖安装完成")
        return

    # 启动服务
    print("启动公安联考题库系统...")
    print(f"工作目录: {os.getcwd()}")
    print(f"PYTHONPATH: {parent_dir}")
    print(f"访问地址: http://0.0.0.0:8000")
    print(f"API 文档: http://0.0.0.0:8000/docs")
    print("-" * 50)

    subprocess.run([
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ])

if __name__ == "__main__":
    main()