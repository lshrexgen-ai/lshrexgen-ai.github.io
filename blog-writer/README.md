# 블로그 본문 생성기

네이버 블로그 에디터에 붙여넣을 본문을 HTML 미리보기 페이지로 만듭니다. 이모티콘과 서식이 유지됩니다.

## 사용법

1. 초안을 준비합니다. 형식은 `draft.example.txt`를 참고하세요.
   - `제목: ...` (선택)
   - `# 소제목`
   - `[사진: 설명]` → 사진 자리
   - 빈 줄로 문단 구분
2. 직접 찍은 사진을 `photos/` 폴더에 넣습니다. 파일 이름 순서대로 사진 자리에 연결됩니다.
3. 실행합니다.

```bash
python write_post.py draft.example.txt
```

4. `output/post.html`을 브라우저로 엽니다.
5. **본문 복사** 버튼을 누르고, 블로그 글쓰기 화면의 본문에 `Ctrl+V` 합니다.
6. 노란 표시 자리에 사진을 넣고, 스티커·지도·링크는 에디터에서 추가합니다.

## Claude API로 초안 자동 생성

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python write_post.py --topic "성수동 카페 후기" --style style.txt --photo-count 4
```

- `--style`은 말투나 글 흐름 참고용 텍스트 파일입니다. 선택 사항입니다.
- 생성된 초안은 `output/draft.txt`에 저장되고, 같은 방식으로 페이지가 만들어집니다.
- 모델은 `CLAUDE_MODEL` 환경 변수나 `--model`로 바꿀 수 있습니다.

## 참고

- `photos/`와 `output/`은 `.gitignore`에 들어 있어 저장소에 올라가지 않습니다.
- HEIC 사진은 브라우저 미리보기에 안 나올 수 있습니다. JPG로 바꿔 넣으세요.
- 본문 복사는 서식 있는 텍스트로 복사합니다. 스마트에디터가 붙여넣은 서식을 얼마나 유지하는지는 직접 확인해 보세요.
