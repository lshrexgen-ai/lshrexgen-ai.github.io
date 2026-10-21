#!/usr/bin/env python3
"""블로그 본문을 만들어 '본문 복사' 버튼이 있는 HTML 미리보기 페이지로 저장합니다.

사용법
  python write_post.py draft.txt                       # 직접 쓴 초안으로 페이지 생성
  python write_post.py --topic "주제" --style style.txt # Claude API로 초안 생성 후 페이지 생성

초안 형식
  제목: 글 제목                 (선택, 맨 윗줄)
  # 소제목                      (소제목)
  [사진: 설명]                  (사진 자리, photos/ 폴더의 파일을 순서대로 연결)
  빈 줄로 구분된 문단             (본문, 줄바꿈은 그대로 유지)
  이모티콘은 그대로 입력

Claude API 사용 시 ANTHROPIC_API_KEY 환경 변수가 필요합니다.
"""

import argparse
import html
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
PHOTO_RE = re.compile(r"^\[사진:\s*(.+?)\]$")
DEFAULT_MODEL = "claude-opus-5-5"

PAGE_TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, "Malgun Gothic", sans-serif; background: #f6f6f6; margin: 0; color: #222; }}
  main {{ max-width: 720px; margin: 0 auto; padding: 16px; }}
  .toolbar {{ position: sticky; top: 0; background: #fff; padding: 12px 0; border-bottom: 1px solid #ddd; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
  button {{ padding: 10px 16px; font-size: 15px; border: 0; border-radius: 6px; background: #03c75a; color: #fff; cursor: pointer; }}
  #status {{ font-size: 14px; color: #555; }}
  .article {{ background: #fff; padding: 20px; margin-top: 16px; border-radius: 8px; line-height: 1.8; font-size: 16px; }}
  .article h3 {{ margin: 28px 0 8px; font-size: 19px; }}
  .article p {{ margin: 0 0 14px; }}
  .photo {{ margin: 16px 0; text-align: center; }}
  .photo .marker {{ display: inline-block; padding: 6px 10px; background: #fff7d6; border: 1px dashed #c9a400; border-radius: 4px; font-size: 14px; color: #6b5600; }}
  .photo img {{ max-width: 100%; border-radius: 6px; margin-top: 8px; }}
  .title {{ font-size: 22px; font-weight: bold; margin: 0; }}
  .hint {{ font-size: 13px; color: #777; margin-top: 8px; }}
</style>
</head>
<body>
<main>
  <div class="toolbar">
    <button id="copy">본문 복사</button>
    <span id="status">제목: {title}</span>
  </div>
  <p class="hint">복사한 뒤 블로그 글쓰기 화면의 본문에 Ctrl+V 하세요. 노란 표시 자리에 직접 찍은 사진을 넣고, 스티커·지도·링크는 에디터에서 추가하세요.</p>
  <div class="article" id="body">
{body}
  </div>
</main>
<script>
const statusEl = document.getElementById('status');
document.getElementById('copy').addEventListener('click', async () => {{
  const body = document.getElementById('body').cloneNode(true);
  body.querySelectorAll('figure.photo').forEach(fig => {{
    const p = document.createElement('p');
    p.textContent = fig.dataset.marker;
    fig.replaceWith(p);
  }});
  const html = body.innerHTML;
  try {{
    await navigator.clipboard.write([new ClipboardItem({{
      'text/html': new Blob([html], {{ type: 'text/html' }}),
    }})]);
    statusEl.textContent = '복사 완료! 블로그 글쓰기 화면에 Ctrl+V 하세요.';
  }} catch (e) {{
    statusEl.textContent = '자동 복사에 실패했습니다. 본문을 드래그해서 직접 복사하세요.';
  }}
}});
</script>
</body>
</html>
"""


def parse_draft(text):
    """초안 텍스트를 (제목, 블록 목록)으로 나눕니다. 블록은 (종류, 값) 튜플입니다."""
    title = None
    blocks = []
    lines = []

    def flush():
        if lines:
            blocks.append(("p", list(lines)))
            lines.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
        elif title is None and not blocks and not lines and line.startswith("제목:"):
            title = line[len("제목:"):].strip()
        elif line.startswith("# "):
            flush()
            blocks.append(("h", line[2:].strip()))
        elif PHOTO_RE.match(line):
            flush()
            blocks.append(("photo", PHOTO_RE.match(line).group(1)))
        else:
            lines.append(line)
    flush()
    return title, blocks


def list_photos(photos_dir):
    if not photos_dir.is_dir():
        return []
    return sorted(p for p in photos_dir.iterdir() if p.suffix.lower() in PHOTO_EXTS)


def render_body(blocks, photos, out_dir):
    """블록을 HTML로 바꿉니다. 사진 자리는 i번째 사진 파일을 순서대로 연결합니다."""
    parts = []
    photo_index = 0
    for kind, value in blocks:
        if kind == "h":
            parts.append(f"    <h3>{html.escape(value)}</h3>")
        elif kind == "p":
            text = "<br>".join(html.escape(line) for line in value)
            parts.append(f"    <p>{text}</p>")
        elif kind == "photo":
            marker = f"[사진: {value}]"
            img = ""
            if photo_index < len(photos):
                rel = os.path.relpath(photos[photo_index], out_dir).replace(os.sep, "/")
                img = f'<img src="{html.escape(rel)}" alt="{html.escape(value)}">'
            photo_index += 1
            parts.append(
                f'    <figure class="photo" data-marker="{html.escape(marker)}">'
                f'<span class="marker">{html.escape(marker)}</span>{img}</figure>'
            )
    return "\n".join(parts)


def generate_draft(topic, style_text, photo_count, model):
    """Claude API로 초안을 만듭니다. 결과는 parse_draft가 읽는 형식입니다."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY 환경 변수가 없습니다.")

    style_part = f"\n\n다음 말투와 글 흐름을 참고하세요:\n{style_text}" if style_text else ""
    prompt = f"""주제: {topic}{style_part}

네이버 블로그 본문을 한국어로 써 주세요. 아래 형식을 정확히 지키세요.
- 첫 줄은 "제목: ..." 형식의 제목
- 소제목은 "# 소제목" 형식으로 3~5개
- 사진 자리는 "[사진: 설명]" 한 줄로 정확히 {photo_count}번 넣고, 사진이 필요한 장면을 설명
- 문단은 빈 줄로 구분하고, 필요하면 이모티콘을 사용
- 형식 외의 설명이나 인사말은 쓰지 마세요"""

    body = {
        "model": model,
        "max_tokens": 3000,
        "messages": [{"role": "user", "content": prompt}],
    }
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def main():
    ap = argparse.ArgumentParser(description="블로그 본문 HTML 미리보기 생성")
    ap.add_argument("draft", nargs="?", help="직접 쓴 초안 파일 경로")
    ap.add_argument("--topic", help="Claude API로 초안을 만들 주제")
    ap.add_argument("--style", help="말투 참고용 텍스트 파일 경로")
    ap.add_argument("--photo-count", type=int, default=3, help="API 초안의 사진 자리 개수")
    ap.add_argument("--photos", default=str(HERE / "photos"), help="사진 폴더")
    ap.add_argument("--out", default=str(HERE / "output" / "post.html"), help="출력 HTML 경로")
    ap.add_argument("--model", default=os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL))
    args = ap.parse_args()

    if args.topic:
        style_text = Path(args.style).read_text(encoding="utf-8") if args.style else ""
        draft_text = generate_draft(args.topic, style_text, args.photo_count, args.model)
        draft_path = HERE / "output" / "draft.txt"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(draft_text, encoding="utf-8")
        print(f"초안 저장: {draft_path}")
    elif args.draft:
        draft_text = Path(args.draft).read_text(encoding="utf-8")
    else:
        ap.error("draft 파일 또는 --topic 중 하나는 필요합니다.")

    title, blocks = parse_draft(draft_text)
    title = title or "블로그 글"
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    photos = list_photos(Path(args.photos).resolve())
    photo_blocks = sum(1 for kind, _ in blocks if kind == "photo")
    if photo_blocks > len(photos):
        print(f"경고: 사진 자리 {photo_blocks}개, 사진 파일 {len(photos)}개. 나머지는 빈 표시로 남습니다.")

    page = PAGE_TEMPLATE.format(
        title=html.escape(title),
        body=render_body(blocks, photos, out_path.parent),
    )
    out_path.write_text(page, encoding="utf-8")
    print(f"완성: {out_path}")


if __name__ == "__main__":
    main()
