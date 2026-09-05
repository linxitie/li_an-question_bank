"""Quick test: /api/quotes/random returns different obsidian quotes each call"""
import requests, json

seen = set()
for i in range(8):
    r = requests.get("http://localhost:8000/api/quotes/random", timeout=5)
    d = r.json()
    content = d.get("content", "")[:50]
    stype = d.get("source_type", "?")
    seen.add(content)
    print(f"  {i+1}. [{stype}] {content}")

print(f"\nTotal calls: 8, Unique quotes: {len(seen)}")
print("PASS" if len(seen) > 1 else "FAIL - all same!")
