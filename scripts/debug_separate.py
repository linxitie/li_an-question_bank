import requests, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = 'http://localhost:8000'
r = requests.post(f'{BASE}/api/auth/login', data={'username':'admin','password':'Admin123456'})
token = r.json().get('access_token')
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

# Test update-answer endpoint
print('Test update-answer for question 154:')
r = requests.put(f'{BASE}/api/questions/import/update-answer/154', json={
    'answer': 'B',
    'paper_name': 'test_separate'
}, headers=headers)
print(f'Status: {r.status_code}')
print(f'Body: {r.text[:500]}')

# Also check the GET endpoint to verify answer was updated
print('\nCheck question 154:')
r = requests.get(f'{BASE}/api/questions/154', headers=headers)
if r.status_code == 200:
    q = r.json()
    print(f'Answer: {repr(q.get("answer"))}')
