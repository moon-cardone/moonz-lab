#!/usr/bin/env python3
"""python test_build.py — 발행 로직 자체 점검."""
import shutil
import tempfile
from datetime import date
from pathlib import Path

import build


def with_content(files):
    """임시 content/ 를 만들어 build 모듈이 그걸 보게 한다."""
    tmp = Path(tempfile.mkdtemp())
    (tmp / "log").mkdir()
    (tmp / "projects").mkdir()
    for rel, text in files.items():
        (tmp / rel).write_text(text, encoding="utf-8")
    build.LOG_DIR, build.PROJ_DIR = tmp / "log", tmp / "projects"
    build.ABOUT = tmp / "about.md"
    return tmp


def test_sorted_newest_first():
    tmp = with_content({
        "log/a.md": "---\ndate: 2026-01-05\ntitle: 오래된 것\n---\n본문",
        "log/b.md": "---\ndate: 2026-08-01\ntitle: 최신\n---\n본문",
        "log/c.md": "---\ndate: 2026-03-10\ntitle: 중간\n---\n본문",
    })
    logs, errors = build.load_logs()
    assert not errors, errors
    assert [e["title"] for e in logs] == ["최신", "중간", "오래된 것"], logs
    shutil.rmtree(tmp)


def test_missing_date_and_title_named():
    tmp = with_content({
        "log/no-date.md": "---\ntitle: 날짜 없음\n---\n본문",
        "log/no-title.md": "---\ndate: 2026-02-02\n---\n본문",
        "log/fine.md": "---\ndate: 2026-02-03\ntitle: 정상\n---\n본문",
    })
    logs, errors = build.load_logs()
    assert len(errors) == 2, errors
    assert any("no-date.md" in e and "날짜" in e for e in errors), errors
    assert any("no-title.md" in e and "제목" in e for e in errors), errors
    assert len(logs) == 1  # 정상 파일은 그대로 읽힌다
    shutil.rmtree(tmp)


def test_bad_date_rejected():
    tmp = with_content({
        "log/x.md": "---\ndate: 2026-13-45\ntitle: 없는 날짜\n---\n본문",
        "log/y.md": "---\ndate: 2026/01/01\ntitle: 형식 틀림\n---\n본문",
    })
    _, errors = build.load_logs()
    assert len(errors) == 2, errors
    assert any("없는 날짜" in e for e in errors), errors
    shutil.rmtree(tmp)


def test_no_front_matter_reported():
    tmp = with_content({"log/plain.md": "그냥 본문만 있는 파일"})
    _, errors = build.load_logs()
    assert len(errors) == 1 and "plain.md" in errors[0], errors
    shutil.rmtree(tmp)


def test_bad_state_rejected():
    tmp = with_content({
        "log/s.md": "---\ndate: 2026-01-01\ntitle: 상태 이상\nstatus: 대충함\n---\n본문",
    })
    _, errors = build.load_logs()
    assert len(errors) == 1 and "대충함" in errors[0], errors
    shutil.rmtree(tmp)


def test_one_line_body_ok():
    tmp = with_content({
        "log/one.md": "---\ndate: 2026-08-06\ntitle: 한 줄\n---\n크론 시간만 바꿨다.",
    })
    logs, errors = build.load_logs()
    assert not errors and logs[0]["body"] == "<p>크론 시간만 바꿨다.</p>", logs
    shutil.rmtree(tmp)


def test_empty_body_ok():
    """본문이 아예 없어도 통과해야 한다 — 제목만 있는 일지."""
    tmp = with_content({"log/e.md": "---\ndate: 2026-08-06\ntitle: 제목만\n---\n"})
    logs, errors = build.load_logs()
    assert not errors and logs[0]["body"] == "", logs
    shutil.rmtree(tmp)


def test_empty_card_always_present():
    tmp = with_content({
        "projects/p.md": "---\nname: 무언가\nsummary: 설명\nstatus: 운영 중\n---\n",
    })
    projects, errors = build.load_projects()
    assert not errors, errors
    out = build.render([], projects, "<p>소개</p>")
    assert out.count('class="card empty"') == 1, "빈 칸 카드가 정확히 하나여야 함"
    assert out.index("무언가") < out.index("빈 칸"), "빈 칸은 항상 맨 끝"
    shutil.rmtree(tmp)


def test_card_links_to_project_page():
    tmp = with_content({
        "projects/p.md": "---\nname: threads-poster\nsummary: 설명\n---\n",
    })
    projects, _ = build.load_projects()
    out = build.render([], projects, "")
    assert 'href="project/threads-poster.html"' in out, out[:400]
    # 빈 칸 카드는 링크가 아니어야 한다
    assert '<article class="card empty"' in out
    shutil.rmtree(tmp)


def test_logs_matched_by_tag():
    """태그가 프로젝트 이름과 같으면 그 프로젝트 일지로 잡힌다."""
    tmp = with_content({
        "projects/p.md": "---\nname: pushdown\n---\n",
        "log/a.md": "---\ndate: 2026-08-05\ntitle: 관련 있음\ntags: pushdown\n---\n본문",
        "log/b.md": "---\ndate: 2026-08-04\ntitle: 관련 없음\ntags: 딴것\n---\n본문",
        "log/c.md": "---\ndate: 2026-08-03\ntitle: project 항목으로\nproject: pushdown\n---\n본문",
    })
    logs, _ = build.load_logs()
    projects, _ = build.load_projects()
    picked = build.logs_for(projects[0], logs)
    titles = [e["title"] for e in picked]
    assert titles == ["관련 있음", "project 항목으로"], titles
    shutil.rmtree(tmp)


def test_project_page_has_back_link_and_entries():
    tmp = with_content({
        "projects/p.md": "---\nname: pushdown\nsummary: 설명\nstatus: 만드는 중\n---\n",
        "log/a.md": "---\ndate: 2026-08-05\ntitle: 고친 것\ntags: pushdown\n---\n한 줄.",
    })
    logs, _ = build.load_logs()
    projects, _ = build.load_projects()
    html_out = build.render_project(projects[0], build.logs_for(projects[0], logs))
    assert "전체 일지" in html_out, "돌아가는 링크가 있어야 함"
    assert "../index.html" in html_out, "상위 경로로 돌아가야 함"
    assert "고친 것" in html_out and "만드는 중" in html_out
    shutil.rmtree(tmp)


def test_project_page_with_no_logs():
    """일지 0개인 프로젝트도 페이지가 깨지지 않아야 한다."""
    tmp = with_content({"projects/p.md": "---\nname: 새것\n---\n"})
    projects, _ = build.load_projects()
    out = build.render_project(projects[0], [])
    assert "아직 이 프로젝트로 쓴 일지가 없습니다" in out
    shutil.rmtree(tmp)


def test_duplicate_slug_reported():
    """주소가 겹치면 페이지가 덮어써지므로 발행을 멈춰야 한다."""
    tmp = with_content({
        "projects/a.md": "---\nname: my app\n---\n",
        "projects/b.md": "---\nname: My App\n---\n",
    })
    _, errors = build.load_projects()
    assert len(errors) == 1 and "겹칩니다" in errors[0], errors
    shutil.rmtree(tmp)


def test_korean_name_slug():
    """한글 이름도 주소가 만들어져야 한다."""
    assert build.slugify("한 줄 육아일기") == "한-줄-육아일기"
    assert build.slugify("threads-poster") == "threads-poster"
    assert build.slugify("blog_auto") == "blog_auto"


def test_section_order():
    out = build.render([], [], "<p>소개</p>")
    assert out.index("만든 것") < out.index("작업 일지") < out.index("소개"), "구역 순서"


def test_html_escaped():
    tmp = with_content({
        "log/x.md": "---\ndate: 2026-01-01\ntitle: <script>alert(1)</script>\n---\n본문",
    })
    logs, _ = build.load_logs()
    out = build.render(logs, [], "")
    assert "<script>alert(1)</script>" not in out, "제목이 그대로 들어가면 안 됨"
    assert "&lt;script&gt;" in out
    shutil.rmtree(tmp)


def test_korean_keys_work():
    """날짜/제목/상태 한글 키도 받는다."""
    tmp = with_content({
        "log/k.md": "---\n날짜: 2026-05-05\n제목: 한글 키\n상태: 러프\n태그: 자동화, 실험\n---\n본문",
    })
    logs, errors = build.load_logs()
    assert not errors, errors
    assert logs[0]["title"] == "한글 키" and logs[0]["state"] == "러프"
    assert logs[0]["tags"] == ["자동화", "실험"], logs[0]["tags"]
    shutil.rmtree(tmp)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)}개 통과")
