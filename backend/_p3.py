import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
src = open(r'app\api\v1\question_import.py', encoding='utf-8').read()
i = src.find('async def import_single_question')
j = src.find('@router.put("/update-answer', i)
fn = src[i:j]
print('LEN:', len(fn))
print(fn)
