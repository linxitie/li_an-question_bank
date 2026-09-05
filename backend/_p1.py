import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
src = open(r'app\api\v1\question_import.py', encoding='utf-8').read()
i = src.find('async def import_single_question')
print(src[i:i+1500])
print('...')
# 找到函数结束附近返回体
j = src.find("import_status': 'SUCCESS'", i)
print(src[j-600:j+400])
