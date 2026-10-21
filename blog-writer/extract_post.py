#!/usr/bin/env python3
"""네이버 블로그 글의 구조(문단 길이, 사진 자리, 스티커 등)를 추출해 초안 틀로 저장합니다.

원문 문장은 옮기지 않습니다. 어떤 자리에 무엇이 몇 줄쯤 있었는지만 남기고,
내용은 write_post.py 실행 전에 LLM이나 직접 작성해서 채웁니다.

사용법
  python extract_post.py https://m.blog.naver.com/블로그ID/글번호
  python extract_post.py https://m.blog.naver.com/블로그ID          # 가장 최근 글
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "output"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
ZERO_WIDTH = re.compile(r"[​‌‍﻿]")


def fetch(url, referer=None):
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def resolve_post_url(url):
    """글 번호가 없는 블로그 주소면 가장 최근 글의 주소를 돌려줍니다."""
    parts = [p for p in urlparse(url).path.split("/") if p]
    blog_id = parts[0]
    if len(parts) >= 2 and parts[1].isdigit():
        return f"https://m.blog.naver.com/{blog_id}/{parts[1]}"
    api = f"https://m.blog.naver.com/api/blogs/{blog_id}/post-list?categoryNo=0&itemCount=10&page=1"
    data = json.loads(fetch(api, referer=f"https://m.blog.naver.com/{blog_id}"))
    items = data["result"]["items"]
    if not items:
        sys.exit("공개된 글이 없습니다.")
    return f"https://m.blog.naver.com/{blog_id}/{items[0]['logNo']}"


def clean(text):
    return ZERO_WIDTH.sub("", text).strip()


def extract(html):
    """문서 순서대로 구조 틀을 만듭니다. 줄 형식은 write_post.py 초안 형식과 같습니다."""
    soup = BeautifulSoup(html, "html.parser")
    lines = []
    counts = {"text": 0, "photo": 0, "sticker": 0, "quote": 0, "map": 0}
    pending = 0  # 연속된 문단 줄 수

    def flush():
        nonlocal pending
        if pending:
            lines.append(f"[문단: 약 {pending}줄, 내용 작성]")
            lines.append("")
            pending = 0

    def add_marker(marker):
        flush()
        lines.append(marker)
        lines.append("")

    for comp in soup.select(".se-component"):
        classes = comp.get("class", [])
        if "se-documentTitle" in classes:
            continue
        if "se-text" in classes:
            for para in comp.select(".se-text-paragraph"):
                if clean(para.get_text(" ", strip=True)):
                    pending += 1
                    counts["text"] += 1
                else:
                    flush()
        elif "se-image" in classes or "se-imageGroup" in classes or "se-video" in classes:
            add_marker("[사진: 장면 설명]")
            counts["photo"] += 1
        elif "se-sticker" in classes:
            add_marker("[스티커: 표현 설명]")
            counts["sticker"] += 1
        elif "se-quotation" in classes:
            add_marker("[인용구: 강조할 한 줄]")
            counts["quote"] += 1
        elif "se-placesMap" in classes:
            add_marker("[지도: 장소 이름]")
            counts["map"] += 1
        elif "se-horizontalLine" in classes:
            add_marker("[구분선]")
    flush()

    body = "\n".join(lines)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return body, counts


def main():
    ap = argparse.ArgumentParser(description="네이버 블로그 글 구조 추출")
    ap.add_argument("url", help="글 주소 또는 블로그 주소")
    ap.add_argument("--out", default=str(OUT_DIR / "reference_structure.txt"))
    args = ap.parse_args()

    post_url = resolve_post_url(args.url)
    print(f"글 주소: {post_url}")
    body, counts = extract(fetch(post_url))

    draft = f"제목: [제목 작성]\n\n{body}\n"
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(draft, encoding="utf-8")

    print(
        f"문단 {counts['text']}줄, 사진 자리 {counts['photo']}개, 인용구 {counts['quote']}개, "
        f"스티커 {counts['sticker']}개, 지도 {counts['map']}개"
    )
    print(f"구조 틀 저장: {out_path}")


if __name__ == "__main__":
    main()
