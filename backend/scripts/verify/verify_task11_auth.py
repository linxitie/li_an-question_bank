# -*- coding: utf-8 -*-
"""T11 鉴权与入参校验（走真实 ASGI 栈，含 Depends(get_current_user)）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app

URL = '/api/questions/import/separate-match-xingce'
fails = []


def check(name, cond, detail=''):
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  -> ' + str(detail)) if detail else ''))
    if not cond:
        fails.append(name)


c = TestClient(app)

print('=== 鉴权 ===')
r = c.post(URL, json={'questions_text': '1. 题目', 'answers_text': '1. 正确答案：A'})
check('无 token 被拒(401/403)', r.status_code in (401, 403), r.status_code)

r = c.post(URL, json={'questions_text': '1. 题目', 'answers_text': '1. 正确答案：A'},
           headers={'Authorization': 'Bearer invalid.token.here'})
check('无效 token 被拒(401/403)', r.status_code in (401, 403), r.status_code)

print()
print('=== 入参校验（需合法 token 才能走到 400 分支）===')
#登录用 OAuth2PasswordRequestForm（表单，非 JSON）。
# 若无已知口令，退而用应用自身的 create_access_token 为真实用户铸造合法
# token —— 这才是验证「有效 token 能穿过鉴权、到达 400 分支」的正确方式，
# 不用 mock 绕过鉴权。
token = None
for user, pwd in (('admin', 'admin123'), ('admin', '123456'),
                  ('test', 'test123'), ('admin', 'admin')):
    lr = c.post('/api/auth/login',
                data={'username': user, 'password': pwd})
    if lr.status_code == 200:
        try:
            token = (lr.json().get('access_token')
                     or lr.json().get('data', {}).get('access_token'))
        except Exception:
            token = None
        if token:
            print('  登录成功: %s' % user)
            break

if not token:
    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.models.models import SysUser
    s = SessionLocal()
    try:
        uid = s.query(SysUser.user_id).first()
        uid = uid[0] if uid else None
    finally:
        s.close()
    if uid:
        # get_current_user 读的是 payload['user_id']（security.py:274），
        # 不是 JWT 标准的 'sub'。用 'sub' 会被判「无效的令牌载荷」。
        token = create_access_token({'user_id': uid})
        print('  无可用口令，改用应用自身 create_access_token 铸造 token (user_id=%s)' % uid)

if not token:
    print('  [WARN] 无法获得合法 token，400 分支未实测（不得据此声称通过）')
else:
    H = {'Authorization': 'Bearer %s' % token}
    r = c.post(URL, json={'questions_text': '', 'answers_text': 'x'}, headers=H)
    check('空 questions_text -> 400', r.status_code == 400, r.status_code)
    check('  detail 含「题目文件文本为空」', '题目文件文本为空' in str(r.json()), r.json())

    r = c.post(URL, json={'questions_text': 'x', 'answers_text': ''}, headers=H)
    check('空 answers_text -> 400', r.status_code == 400, r.status_code)
    check('  detail 含「答案文件文本为空」', '答案文件文本为空' in str(r.json()), r.json())

    r = c.post(URL, json={'questions_text': '   \n\t ', 'answers_text': '  \n '}, headers=H)
    check('纯空白 -> 400', r.status_code == 400, r.status_code)

    r = c.post(URL, json={'answers_text': 'x'}, headers=H)
    check('缺 questions_text 键 -> 400', r.status_code == 400, r.status_code)

print()
print('=== 文档可见性 ===')
r = c.get('/openapi.json')
if r.status_code == 200:
    spec = r.json()
    check('openapi.json 含新端点', URL in spec.get('paths', {}),
          URL in spec.get('paths', {}))
else:
    check('openapi.json 可读', False, r.status_code)

print()
print('RESULT = %s   失败 %d 项 %s'
      % ('PASS' if not fails else 'FAIL', len(fails), fails or ''))
sys.exit(0 if not fails else 1)