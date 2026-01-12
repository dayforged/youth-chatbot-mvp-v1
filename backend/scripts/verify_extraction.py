import json
from pathlib import Path

JSONL_PATH = Path("processed-data/0154b536d619.jsonl")

pages = {}
with JSONL_PATH.open("r", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        pages[r["page"]] = r["text"]

# 1) 페이지 수 확인(추출된 페이지 개수)
print("extracted_pages:", len(pages))
print("min_page:", min(pages), "max_page:", max(pages))

# 2) 텍스트가 너무 짧은 페이지(표/이미지 가능성) 상위 20개
short = sorted([(p, len(t)) for p, t in pages.items()], key=lambda x: x[1])[:20]
print("\n[short pages]")
for p, ln in short:
    print(p, ln)

# 3) '□', '※', '붙임', '서식' 같은 키워드 페이지가 제대로 있는지 (원하면 키워드 추가)
keywords = ["지원대상", "지원요건", "신청", "서식", "붙임", "제외", "중복"]
print("\n[keyword hit counts]")
for k in keywords:
    hit = sum(1 for t in pages.values() if k in t)
    print(k, hit)
