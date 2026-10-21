# 블로그 글 자동 작성 도구

Anthropic Claude API를 이용해 블로그 글을 자동으로 생성하고 HTML로 변환합니다.

## 설치

```bash
pip install -r requirements.txt
```

## API 키 설정

```bash
export ANTHROPIC_API_KEY='sk-...'
```

또는 Claude 클라우드 환경인 경우:
1. 세션 제목바 → **Edit**
2. **Network secrets** → `ANTHROPIC_API_KEY` 추가
3. 새 세션 열기

## 사용법

### 1️⃣ 블로그 구조 추출 (선택사항)

참고할 네이버 블로그의 구조를 분석합니다:

```bash
python extract_post.py https://m.blog.naver.com/username
python extract_post.py https://m.blog.naver.com/username/224448321722  # 특정 글
```

결과: `output/reference_structure.txt`

### 2️⃣ 글 자동 생성

주제로 새로운 글을 생성합니다:

```bash
# 기본
python write_post.py --topic "성수동 카페 추천"

# 사진 개수 지정
python write_post.py --topic "강남역 맛집 후기" --photo-count 4

# 말투 파일 적용
python write_post.py --topic "홍대 쇼핑 가이드" --style style.txt
```

결과: `output/draft.txt`

### 3️⃣ HTML 미리보기 생성

draft.txt를 HTML로 변환합니다:

```bash
python write_post.py output/draft.txt
```

결과: `output/post.html` (브라우저에서 열기)

## 블로그에 붙여넣기

1. `output/post.html` 브라우저에서 열기
2. **📋 본문 복사** 버튼 클릭
3. 네이버 블로그 글쓰기 화면 본문에 `Ctrl+V` 붙여넣기
4. 제목은 따로 제목 칸에 붙여넣기
5. `[사진: ...]` 자리에 직접 찍은 사진 삽입

## 말투 파일 (style.txt)

원하는 톤을 텍스트로 정의합니다:

```
짧은 문장 선호
친근한 톤
이모티콘 적게
구체적인 설명 포함
```

## 폴더 구조

```
.
├── extract_post.py      # 블로그 구조 추출
├── write_post.py        # 글 생성 및 HTML 변환
├── requirements.txt
├── README.md
├── style.txt            # (선택) 말투 정의
└── output/
    ├── reference_structure.txt
    ├── draft.txt
    └── post.html
```

## 주의사항

- ✅ 원문의 **구조와 말투만 참고**하세요
- ✅ 본문은 **새로 작성**하세요
- ✅ 참고 블로그 사진은 **재사용하지 마세요**
- ✅ **직접 찍은 사진**을 사용하세요

## 문제 해결

| 증상 | 해결 |
|---|---|
| `ANTHROPIC_API_KEY 환경변수가 없습니다` | 위의 API 키 설정 참고 |
| 블로그 접속 실패 (403) | m.blog.naver.com이 허용된 도메인인지 확인 |
| 공개된 글이 없다고 나옴 | 블로그에 공개 글이 있는지, URL이 맞는지 확인 |
| 생성된 글이 마음에 안 드나요? | `--topic`을 더 구체적으로 작성하거나 `--style` 파일로 톤 조정 |

## 예시

```bash
# 1. 카페 후기 생성
python write_post.py --topic "서울 강남역 근처 조용한 카페 3곳" --photo-count 3 --style style.txt

# 2. HTML로 변환
python write_post.py output/draft.txt

# 3. output/post.html을 브라우저에서 열어 복사 버튼 클릭
# 4. 블로그에 붙여넣기
```
