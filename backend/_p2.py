import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
m = open(r'app\middleware.py', encoding='utf-8').read()
i = m.find('class RateLimitMiddleware')
print(m[i:i+1200])
print('====SECURITY RATELIMITER====')
s = open(r'app\core\security.py', encoding='utf-8').read()
j = s.find('class RateLimiter')
print(s[j:j+900])
print('====DATABASE====')
d = open(r'app\core\database.py', encoding='utf-8').read()
for kw in ['SessionLocal', 'sessionmaker']:
    k = d.find(kw)
    print(d[max(0,k-60):k+80].replace('\n',' | '))
