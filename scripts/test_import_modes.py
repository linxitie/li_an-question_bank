import requests, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = 'http://localhost:8000'

# 1. Login
r = requests.post(f'{BASE}/api/auth/login', data={'username':'admin','password':'Admin123456'})
token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

print('1. Test: GET /api/questions/import/stats')
r = requests.get(f'{BASE}/api/questions/import/stats', headers=headers)
print(f'   Status: {r.status_code}, total={r.json().get("total_questions")}')

print('\n2. Test: GET /api/questions/random?count=5')
r = requests.get(f'{BASE}/api/questions/random?count=5', headers=headers)
data = r.json()
print(f'   Status: {r.status_code}, Questions: {len(data.get("questions",[]))}')
if data.get('questions'):
    q = data['questions'][0]
    print(f'   First: id={q.get("question_id")}, answer={repr(q.get("answer"))}, content_preview={repr(q.get("question_content","")[:50])}')

print('\n3. Test: Single import - combined mode')
r = requests.post(f'{BASE}/api/questions/import/single', json={
    'paper_name': 'test_combined',
    'subject_category': '公专',
    'question_type_detail': '选择题',
    'question_content': '测试合并导入题目X',
    'options': [{'key':'A','value':'选项A'}],
    'answer': 'A',
    'import_mode': 'combined'
}, headers=headers)
data = r.json()
print(f'   Status: {r.status_code}, result={data.get("import_status")}, msg={data.get("message","")}')

print('\n4. Test: Single import - separate mode (no answer)')
r = requests.post(f'{BASE}/api/questions/import/single', json={
    'paper_name': 'test_separate',
    'subject_category': '公专',
    'question_type_detail': '选择题',
    'question_content': '测试分离导入题目Y',
    'options': [{'key':'A','value':'选项A'},{'key':'B','value':'选项B'}],
    'answer': '',
    'import_mode': 'separate'
}, headers=headers)
data = r.json()
print(f'   Status: {r.status_code}, result={data.get("import_status")}, qid={data.get("question_id")}, msg={data.get("message","")}')

if data.get('question_id'):
    qid = data['question_id']
    print(f'\n5. Test: PUT /api/questions/import/update-answer/{qid}')
    r = requests.put(f'{BASE}/api/questions/import/update-answer/{qid}', json={
        'answer': 'B',
        'paper_name': 'test_separate'
    }, headers=headers)
    data = r.json()
    print(f'   Status: {r.status_code}, result={data.get("update_status")}, old={repr(data.get("old_answer"))}, new={repr(data.get("new_answer"))}')

    print(f'\n6. Test: POST /api/questions/import/batch-answers')
    r = requests.post(f'{BASE}/api/questions/import/batch-answers', json={
        'answer_pairs': [{'question_id': qid, 'answer': 'C'}]
    }, headers=headers)
    data = r.json()
    print(f'   Status: {r.status_code}, updated={data.get("updated")}, failed={data.get("failed")}')

print('\n7. Test: GET /api/questions/import/records')
r = requests.get(f'{BASE}/api/questions/import/records?page=1&page_size=5', headers=headers)
print(f'   Status: {r.status_code}, items={len(r.json().get("items",[]))}')

print('\n=== ALL TESTS PASSED ===')
