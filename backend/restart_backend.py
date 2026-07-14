"""强制杀掉旧进程并重启后端"""
import subprocess, os, time

# 1. 找到端口 8000 的 PID
result = subprocess.run('netstat -ano', shell=True, capture_output=True, text=True)
pids = set()
for line in result.stdout.splitlines():
    if ':8000' in line and 'LISTENING' in line:
        pid = line.strip().split()[-1]
        pids.add(pid)

# 2. 杀掉这些 PID
for pid in pids:
    print(f'Killing PID {pid}...')
    subprocess.run(['taskkill', '/F', '/PID', pid], shell=True, capture_output=True)
    time.sleep(1)

# 3. 清缓存
for root, dirs, files in os.walk('.'):
    for d in dirs:
        if d == '__pycache__':
            path = os.path.join(root, d)
            for f in os.listdir(path):
                os.remove(os.path.join(path, f))
            os.rmdir(path)

# 4. 重启
print('Starting new server...')
os.chdir(os.path.dirname(os.path.abspath(__file__)))
subprocess.Popen(['python', '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000'])
time.sleep(5)
print('Server should be on http://localhost:8000')
