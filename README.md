# moonz.lab

혼자 만들고, 혼자 굴립니다.

https://moon-cardone.github.io/moonz-lab/

## 글 하나 올리기

1. `content/log/` 에 마크다운 파일을 만든다

```markdown
---
date: 2026-08-06
title: 오늘 고친 것
tags: threads-poster
status: 러프
---

한 줄만 써도 된다.
```

2. 클로드에게 **"발행해줘"** 라고 한다. 2~3분 뒤 사이트에 올라간다.

날짜나 제목을 빠뜨리면 발행이 멈추고 어느 파일이 문제인지 알려준다.

## 상태값

일지는 `러프` · `다듬는 중` · `정리됨`, 프로젝트는 `운영 중` · `만드는 중` · `멈춤` 중에서만 쓴다.

## 직접 돌려보기

```powershell
python build.py               # index.html 생성
python build.py --check       # 검사만
python test_build.py          # 자체 점검
python -m http.server 8000    # 미리보기
```
