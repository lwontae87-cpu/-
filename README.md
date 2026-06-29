# 실시간 IT 이슈 키워드 수집기

블로그 포스팅 아이디어를 빠르게 얻기 위해, 공개 API에서 최신 IT 관련 글 제목을 수집하고 **지금 뜨는 키워드**를 추출하는 간단한 CLI 도구입니다.

## 기능
- Hacker News, Reddit(r/technology), DEV Community 글 제목 수집
- 제목 기반 키워드 빈도 분석 (불용어 제거)
- 상위 키워드와 예시 제목 출력
- 키워드를 활용한 블로그 포스팅 제목 아이디어 자동 생성

## 요구사항
- Python 3.10+

## 실행 방법
```bash
python it_keyword_tracker.py --hours 24 --limit 30 --top 15
```

### 옵션
- `--hours`: 최근 N시간 이내 데이터만 사용 (기본값: 24)
- `--limit`: 소스별 최대 수집 건수 (기본값: 30)
- `--top`: 출력할 상위 키워드 개수 (기본값: 15)
- `--no-fallback`: 실시간 소스 실패 시 샘플 데이터 대체 비활성화

## 출력 예시
- Top keywords: `ai`, `openai`, `release`, `security` ...
- Suggested titles:
  - `2026년 지금 뜨는 AI 이슈 총정리`
  - `OpenAI 관련 최신 업데이트, 블로그로 빠르게 정리하기`

## YouTube Phase 2.5 UX 대시보드

YouTube Data API로 이미 수집된 결과 JSON을 HTML 대시보드로 변환합니다. `.env.local`은 수정하지 않고, API 키도 읽거나 출력하지 않습니다.

```bash
python youtube_phase_2_5_dashboard.py --input youtube_results.json --output youtube_dashboard.html
```

### 반영된 UX 개선
- 상단 분석 요약 카드
  - 최고 성과 영상
  - 가장 빠른 초반 반응 영상
  - 구독자 대비 조회수 높은 영상
  - 숏폼 비율
  - 롱폼 비율
- 영상 결과 테이블
  - Performance 기준 내림차순 기본 정렬
  - Early Reaction 기준 정렬 버튼
  - Shorts / Longform 배지
  - 업로드 날짜가 미래 날짜처럼 보일 때 `미래 날짜 의심` 경고 배지
- 추천 아이디어 영역
  - 실제 검색 결과 제목 기반 추천 아이디어 최대 10개 생성
  - 아이디어별 추천 포맷 표시: Shorts / Blog / YouTube
  - 추천 이유 표시
- 썸네일/source 처리
  - `source`가 `youtube`일 때는 실제 YouTube thumbnail URL만 사용
  - Rick Astley 같은 mock/placeholder 이미지는 제거
  - `YOUTUBE` / `MOCK` source 배지를 화면에서 눈에 띄게 표시

### 지원하는 JSON 필드명

대시보드 생성기는 아래처럼 다양한 필드명을 자동으로 인식합니다.

- 제목: `title`, `video_title`, `Video`
- 채널: `channel`, `channel_title`, `Channel`
- 업로드 날짜: `upload_date`, `published_at`, `publishedAt`, `date`, `Date`
- 조회수: `views`, `view_count`, `Views`
- 구독자: `subscribers`, `subscriber_count`, `Subscribers`
- 성과: `performance`, `Performance`
- 초반 반응: `early_reaction`, `earlyReaction`, `Early Reaction`
- 썸네일: `thumbnail_url`, `thumbnail`, `thumbnailUrl`, `image`, `image_url`
- source: `source`
- Shorts 여부: `is_short`, `isShort`, `shorts`, `is_shorts`

## 활용 팁
1. 하루 1~2회 실행해서 키워드 변화 추이를 기록하세요.
2. 상위 키워드 2~3개를 묶어 비교형 포스팅을 작성해 보세요.
3. 특정 키워드가 2일 이상 유지되면 심층 글감으로 발전시키세요.

## 한계
- API 응답 지연/차단 시 일부 소스 수집이 실패할 수 있습니다.
- 단순 빈도 분석 기반이라 문맥적 중요도까지 반영하지는 않습니다.
- 네트워크가 막힌 환경에서는 내장 샘플 데이터로 동작합니다(기본값).
