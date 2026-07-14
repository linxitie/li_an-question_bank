import requests, re, glob, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = requests.post('http://localhost:8000/api/auth/login', data={'username':'admin','password':'Admin123456'}).json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

files = sorted(glob.glob(r'd:\砺安题库\砺安题库\题库\公安题目（打印）\*.docx'))

# Test with manually filled answers
for fi, fp in enumerate(files[:2]):
    with open(fp, 'rb') as f:
        r = requests.post('http://localhost:8000/api/questions/import/upload', files={'file': f}, headers=headers)
    raw = r.json().get('raw_text_preview', '')
    lines = raw.split('\n')
    
    # Streaming parser
    blocks = []
    current_num = None
    current_lines = []
    qh_re = re.compile(r'^\s*(\d+)\s*[.\u3001\uff0e)]')
    for line in lines:
        m = qh_re.match(line)
        if m:
            if current_num is not None and current_lines:
                blocks.append({'num': current_num, 'text': '\n'.join(current_lines).strip()})
            current_num = int(m.group(1))
            rest = qh_re.sub('', line).strip()
            current_lines = [rest] if rest else []
        elif current_num is not None:
            current_lines.append(line)
    if current_num is not None and current_lines:
        blocks.append({'num': current_num, 'text': '\n'.join(current_lines).strip()})
    
    answer_rx = re.compile(r'[\u3010\u300a<]?\s*\u7b54\u6848\s*[\u3011\u300b>]?\s*[:.\uff1a]?\s*([A-D]+)')
    
    # Extract and import with manually filled answer='A' (simulating user fills answer)
    name = os.path.basename(fp)
    ok, dup, fail = 0, 0, 0
    for blk in blocks:
        full = blk['text']
        ans_m = answer_rx.search(full)
        answer = ans_m.group(1) if ans_m else 'A'  # Default to A if no answer in doc
        
        q_lines = []
        for line in full.split('\n'):
            line = line.strip()
            if not line: continue
            if re.match(r'^[A-D]\s*[.\u3001\uff0e)]', line): continue
            q_lines.append(line)
        question_content = ' '.join(q_lines).strip()[:2000]
        
        options = []
        for om in re.finditer(r'^([A-D])\s*[.\u3001\uff0e)]\s*(.+)', full, re.MULTILINE):
            options.append({'key': om.group(1), 'value': om.group(2).strip()})
        
        body = {
            'paper_name': name.replace('.docx',''),
            'subject_category': '公专',
            'question_type_detail': '选择题',
            'question_content': question_content,
            'options': options if len(options) >= 2 else [{'key':'A','value':''},{'key':'B','value':''},{'key':'C','value':''},{'key':'D','value':''}],
            'answer': answer, 'score': 1, 'difficulty': 3
        }
        r = requests.post('http://localhost:8000/api/questions/import/single', json=body, headers=headers)
        data = r.json()
        status = data.get('import_status', '?')
        if status == 'SUCCESS': ok += 1
        elif status == 'DUPLICATE': dup += 1
        else: fail += 1
        if fail > 0:
            print(f'  FAIL #{blk["num"]}: HTTP={r.status_code} answer={answer} qlen={len(question_content)} {data}')
    
    print(f'File {fi+1} ({name[:50]}): {len(blocks)} blocks, {ok} success, {dup} dup, {fail} fail')
