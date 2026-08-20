import os
import re
import hashlib

OBSIDIAN_QUOTE_DIR = r"D:\Obsidian仓库\每日金句知识库\01-金句素材库"

CORRUPTION_PATTERN = re.compile(r'\?{3,}')
PLACEHOLDER_PATTERN = re.compile(
    r'(这句话是|引用的内容|你的引用|此处插入|金句内容|示例|测试|'
    r'这是某个|这是一段|被引用的内容|placeholder|test|example|content)',
    re.IGNORECASE
)
QUOTE_FIELD_PATTERN = re.compile(r'^quote:\s*"(.+?)"\s*$', re.MULTILINE)
STATUS_PATTERN = re.compile(r'^status:\s*(.+)$', re.MULTILINE)
SOURCE_PATTERN = re.compile(r'^source:\s*"?(.+?)"?\s*$', re.MULTILINE)
AUTHOR_PATTERN = re.compile(r'^author:\s*"?(.+?)"?\s*$', re.MULTILINE)
TOPICS_PATTERN = re.compile(r'^applicable_topics:\s*\n((?:\s*-\s*.+\n?)+)', re.MULTILINE)


def _parse_obsidian_quote(content):
    quote_match = QUOTE_FIELD_PATTERN.search(content)
    if not quote_match:
        print(f"  No quote field found")
        return None
    
    quote = quote_match.group(1).strip()
    print(f"  Quote: {quote[:50]}...")
    
    if CORRUPTION_PATTERN.search(quote):
        print(f"  CORRUPTION detected")
        return None
    
    if PLACEHOLDER_PATTERN.search(quote):
        print(f"  PLACEHOLDER detected")
        return None
    
    if len(quote) < 5:
        print(f"  Too short ({len(quote)} chars)")
        return None
    
    status_match = STATUS_PATTERN.search(content)
    if status_match:
        status = status_match.group(1).strip()
        print(f"  Status: {status}")
        if status != "已审核":
            print(f"  NOT approved, skipping")
            return None
    else:
        print(f"  No status field found")
    
    return {"content": quote, "source": "", "author": "", "topics": []}


def _read_obsidian_quotes():
    quotes = []
    
    if not os.path.exists(OBSIDIAN_QUOTE_DIR):
        print(f"Dir not found: {OBSIDIAN_QUOTE_DIR}")
        return quotes
    
    print(f"Scanning: {OBSIDIAN_QUOTE_DIR}")
    
    count = 0
    for root, dirs, files in os.walk(OBSIDIAN_QUOTE_DIR):
        for fname in files:
            if not fname.endswith('.md') or fname.startswith('_'):
                continue
            
            fpath = os.path.join(root, fname)
            count += 1
            
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                parsed = _parse_obsidian_quote(content)
                if parsed:
                    file_hash = hashlib.md5(fname.encode()).hexdigest()[:12]
                    parsed['id'] = f"obsidian_{file_hash}"
                    parsed['filename'] = fname
                    quotes.append(parsed)
                    print(f"  -> ADDED ({len(quotes)} total)")
                else:
                    print(f"  -> SKIPPED")
            except Exception as e:
                print(f"  -> ERROR: {e}")
                continue
    
    print(f"\nTotal files scanned: {count}")
    print(f"Total quotes loaded: {len(quotes)}")
    return quotes


if __name__ == "__main__":
    quotes = _read_obsidian_quotes()
    if quotes:
        print(f"\nSample quotes:")
        for q in quotes[:3]:
            print(f"  - {q['filename']}: {q['content'][:60]}...")
