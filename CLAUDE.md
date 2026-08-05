# moonz.lab_site

개인 작업 기록 사이트. 마크다운 → `index.html` 한 장 → GitHub Pages.

- 사이트: https://moon-cardone.github.io/moonz-lab/
- 저장소: moon-cardone/moonz-lab

## "발행해줘" 라고 하면

```powershell
python build.py      # 실패하면(exit 1) 여기서 멈춘다. 절대 무시하고 진행하지 말 것
git add -A
git commit -m "발행: <바뀐 내용 한 줄>"
git push
```

푸시 후 GitHub Actions가 다시 빌드해 배포한다. 2~3분 걸린다.
`gh run watch` 로 확인하고, 끝나면 사용자에게 주소를 알려준다.

**build.py 가 실패하면 커밋하지 않는다.** 어느 파일이 왜 문제인지 그대로 사용자에게 전달하고 멈춘다.
사용자가 고칠 때까지 임의로 날짜·제목을 채워 넣지 않는다.

## 글 쓰는 법

일지는 `content/log/`, 프로젝트는 `content/projects/`, 소개는 `content/about.md`.
파일명은 자유지만 일지는 `YYYY-MM-DD-제목.md` 를 권장.

일지 앞머리 — **날짜와 제목은 필수**, 나머지는 없어도 된다:

```markdown
---
date: 2026-08-06
title: 제목
tags: 태그1, 태그2
status: 러프
---

본문. 한 줄이어도 된다.
```

프로젝트 앞머리 — **이름은 필수**:

```markdown
---
name: 프로젝트명
summary: 한 줄 설명
status: 운영 중
tools: Python, 텔레그램
order: 1
---
```

상태값은 정해진 것만 쓴다. 다른 걸 쓰면 발행이 멈춘다.

- 일지: `러프` / `다듬는 중` / `정리됨`
- 프로젝트: `운영 중` / `만드는 중` / `멈춤`

`order` 는 프로젝트 카드 순서(작은 수가 위). 빈 칸 카드는 build.py가 항상 맨 끝에 자동으로 넣는다.
한글 키(`날짜`·`제목`·`상태`·`태그`·`이름`·`설명`·`도구`)도 그대로 받는다.

## 프로젝트 페이지

카드를 누르면 `project/<slug>.html` 로 간다. hankan.app 의 `/apps/<이름>` 구조를 참고했다.
build.py가 자동으로 만들고, 지운 프로젝트의 페이지는 자동으로 지운다.

**어떤 일지가 어느 프로젝트에 붙는가** — 일지의 `tags` 나 `project` 값이 프로젝트 이름(또는 slug)과
같으면 그 프로젝트 페이지에 들어간다. 대소문자는 무시한다.

```markdown
tags: pushdown        ← pushdown 프로젝트 페이지에 들어감
project: 한 줄 육아일기  ← 이름에 띄어쓰기가 있을 때 이 항목이 편하다
```

이름이 한글이면 주소도 한글이 되어 공유할 때 지저분해진다. `slug:` 를 직접 적어주면 된다:

```markdown
name: 한 줄 육아일기
slug: one-line-diary   → project/one-line-diary.html
```

두 프로젝트의 주소가 겹치면 발행이 멈춘다. 한쪽에 `slug:` 를 적어 구분한다.

## 만들지 않기로 한 것

댓글, 방문자 통계, 검색창, 다크모드, 뉴스레터, 로그인, 광고, 조회수·수익 표시.

이 목록 밖의 기능이 필요해 보여도 **먼저 사용자에게 묻는다.** 임의로 추가하지 않는다.

> 프로젝트 상세 페이지는 원래 이 목록에 있었으나 2026-08-06 사용자가 hankan.app 을 근거로
> 직접 요청해 추가했다. 나머지 항목은 여전히 만들지 않는다.

## 손대는 김에 알아둘 것

- `index.html` 은 build.py가 만드는 결과물이다. 직접 고치지 말 것 — 다음 발행 때 덮어써진다.
- 스타일은 build.py 안의 `CSS` 문자열 하나에 다 있다. 별도 css 파일 없음.
- 로직을 고쳤으면 `python test_build.py` 를 돌린다 (11개 검사).
- 미리보기: `python -m http.server 8000` 후 http://127.0.0.1:8000
