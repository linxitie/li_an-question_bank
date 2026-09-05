"""直接调用 API 测试 /api/notes/question 返回"""
import urllib.request
import urllib.parse
import json

BASE = 'http://localhost:8000'

# 1. 登录获取 token (OAuth2 表单格式)
accounts = [
    ('202516001', 'cbr1234'),
    ('ycc5678', 'ycc5678'),
    ('cbrycc', 'cbrycc'),
]

token = None
for username, password in accounts:
    try:
        data = urllib.parse.urlencode({'username': username, 'password': password}).encode('utf-8')
        req = urllib.request.Request(f'{BASE}/api/auth/login', data=data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        resp = urllib.request.urlopen(req, timeout=5)
        body = json.loads(resp.read().decode('utf-8'))
        token = body.get('access_token') or body.get('token')
        if token:
            print(f"✓ 登录成功: {username}, token={token[:30]}...")
            break
    except Exception as e:
        print(f"✗ 登录失败 {username}: {e}")

if not token:
    print("所有账号登录失败")
    exit(1)

# 2. 调用 /api/notes/stats
print("\n=== /api/notes/stats ===")
req = urllib.request.Request(f'{BASE}/api/notes/stats')
req.add_header('Authorization', f'Bearer {token}')
try:
    resp = urllib.request.urlopen(req, timeout=5)
    body = json.loads(resp.read().decode('utf-8'))
    print(f"Status: {resp.status}")
    print(f"Response: {json.dumps(body, ensure_ascii=False, indent=2)}")
except Exception as e:
    print(f"Error: {e}")

# 3. 调用 /api/notes/question
print("\n=== /api/notes/question?page=1&page_size=20 ===")
req = urllib.request.Request(f'{BASE}/api/notes/question?page=1&page_size=20')
req.add_header('Authorization', f'Bearer {token}')
try:
    resp = urllib.request.urlopen(req, timeout=5)
    body = json.loads(resp.read().decode('utf-8'))
    print(f"Status: {resp.status}")
    print(f"Content-Type: {resp.headers.get('Content-Type')}")
    print(f"Response: {json.dumps(body, ensure_ascii=False, indent=2)}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(f"Body: {e.read().decode('utf-8')[:500]}")
except Exception as e:
    print(f"Error: {e}")

# 4. 调用 /api/notes/news (对照)
print("\n=== /api/notes/news?page=1&page_size=20 ===")
req = urllib.request.Request(f'{BASE}/api/notes/news?page=1&page_size=20')
req.add_header('Authorization', f'Bearer {token}')
try:
    resp = urllib.request.urlopen(req, timeout=5)
    body = json.loads(resp.read().decode('utf-8'))
    print(f"Status: {resp.status}")
    print(f"Response: {json.dumps(body, ensure_ascii=False, indent=2)}")
except Exception as e:
    print(f"Error: {e}")
