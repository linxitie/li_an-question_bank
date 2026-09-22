"""优雅重启后端（先优雅关闭，超时后再强制结束）"""
import subprocess, os, time

def find_port_pids(port: int = 8000):
    """找到监听指定端口的进程 PID"""
    result = subprocess.run('netstat -ano', shell=True, capture_output=True, text=True)
    pids = set()
    for line in result.stdout.splitlines():
        if f':{port}' in line and 'LISTENING' in line:
            pid = line.strip().split()[-1]
            if pid.isdigit():
                pids.add(pid)
    return pids

def kill_gracefully(pids):
    """
    先优雅关闭，再强制结束。

    为什么不用 taskkill /F 直接强杀：
    /F 强制终止会立即断开进程的所有 TCP 连接并发送 RST，
    导致前端（Vite 代理 / WebSocket）报 ECONNRESET 甚至崩溃。

    不带 /F 的 taskkill 会向进程发送 WM_CLOSE（触发 CTRL_CLOSE_EVENT），
    uvicorn 会捕获该信号并优雅关闭（完成在途请求、发送正常关闭帧），
    避免连接被 RST 复位。
    """
    remaining = set(pids)
    # 1) 优雅关闭（不带 /F）
    for pid in pids:
        subprocess.run(['taskkill', '/PID', pid], shell=True, capture_output=True)
    # 2) 等待优雅关闭完成（最长 5 秒）
    for _ in range(10):
        time.sleep(0.5)
        remaining = find_port_pids(8000)
        if not remaining:
            return
    # 3) 超时仍未退出，才强制结束（兜底）
    for pid in remaining:
        print(f'优雅关闭超时，强制结束 PID {pid}...')
        subprocess.run(['taskkill', '/F', '/PID', pid], shell=True, capture_output=True)
        time.sleep(1)

def clear_pycache():
    for root, dirs, files in os.walk('.'):
        for d in dirs:
            if d == '__pycache__':
                path = os.path.join(root, d)
                for f in os.listdir(path):
                    try:
                        os.remove(os.path.join(path, f))
                    except OSError:
                        pass
                try:
                    os.rmdir(path)
                except OSError:
                    pass

if __name__ == '__main__':
    pids = find_port_pids(8000)
    if pids:
        print(f'发现后端进程: {pids}，开始优雅关闭...')
        kill_gracefully(pids)
        print('旧进程已关闭')
    else:
        print('未发现监听 8000 端口的进程')

    clear_pycache()

    print('Starting new server...')
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    subprocess.Popen(['python', '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000'])
    time.sleep(5)
    print('Server should be on http://localhost:8000')
