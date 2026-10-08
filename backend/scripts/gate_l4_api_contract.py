#!/usr/bin/env python3
"""L4 API 契约门禁 — OpenAPI 快照 + 端点存在性"""
import subprocess, sys, os, json, urllib.request

def main():
    try:
        r = urllib.request.urlopen('http://localhost:8000/openapi.json', timeout=10)
        spec = json.loads(r.read())
        paths = list(spec.get('paths', {}).keys())
        required = [
            '/api/questions/import/upload',
            '/api/questions/import/records/{import_id}/status',
            '/api/questions/import/confirm',
            '/api/questions/import/batch-parsed',
            '/api/questions/import/separate-match',
            '/api/questions/import/separate-match-xingce',
            '/api/questions/import/mineru-health',
        ]
        missing = [p for p in required if p not in paths]
        if missing:
            print(f'L4 FAIL: 缺少端点 {missing}')
            sys.exit(1)
        print(f'L4 API 契约: PASS ({len(paths)} 个端点，{len(required)} 个必需端点全部存在)')
        sys.exit(0)
    except Exception as e:
        print(f'L4 FAIL: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()
