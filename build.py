#!/usr/bin/env python3
"""content/ 마크다운을 읽어 index.html 하나를 만든다.

python build.py        → index.html 생성
python build.py --check → 검사만, 파일 안 씀
"""
import html
import re
import sys
from datetime import date
from pathlib import Path

# 윈도우 콘솔 기본 인코딩(cp949)에서 한글·기호 출력이 깨지지 않게
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent
LOG_DIR = ROOT / "content" / "log"
PROJ_DIR = ROOT / "content" / "projects"
ABOUT = ROOT / "content" / "about.md"

SITE_NAME = "moonz.lab"
TAGLINE = "혼자 만들고, 혼자 굴립니다."

LOG_STATES = ("러프", "다듬는 중", "정리됨")
PROJ_STATES = ("운영 중", "만드는 중", "멈춤")


class ContentError(Exception):
    """발행을 멈춰야 하는 콘텐츠 문제."""


def parse_front_matter(path):
    """--- ... --- 앞머리를 dict로. 본문은 그대로 돌려준다."""
    raw = path.read_text(encoding="utf-8-sig")
    # 앞머리 구분선은 파일 첫 줄이어야 한다
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", raw, re.S)
    if not m:
        raise ContentError(f"{path.name}: 맨 위 --- 앞머리 블록이 없습니다")
    meta = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ContentError(f"{path.name}: 앞머리 '{line}' 줄에 콜론(:)이 없습니다")
        k, v = line.split(":", 1)
        meta[k.strip().lower()] = v.strip().strip("\"'")
    return meta, m.group(2)


def parse_date(value, path):
    """YYYY-MM-DD만 받는다. 실제 달력에 있는 날짜인지까지 확인."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ContentError(
            f"{path.name}: 날짜 '{value}' 형식이 잘못됐습니다 (YYYY-MM-DD 로 적어주세요)"
        )
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ContentError(f"{path.name}: 날짜 '{value}' 는 없는 날짜입니다")


def split_tags(value):
    return [t.strip() for t in re.split(r"[,，]", value or "") if t.strip()]


def md_inline(text):
    """굵게 / 코드 / 링크만. 나머지는 이스케이프."""
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        r'<a href="\2" rel="noopener">\1</a>',
        out,
    )
    return out


def md_body(text):
    """문단과 - 목록만 처리한다. 일지 본문은 대개 한두 줄이라 이걸로 충분."""
    blocks = []
    for chunk in re.split(r"\n\s*\n", text.strip()):
        lines = [l.strip() for l in chunk.splitlines() if l.strip()]
        if not lines:
            continue
        if all(l.startswith(("- ", "* ")) for l in lines):
            items = "".join(f"<li>{md_inline(l[2:])}</li>" for l in lines)
            blocks.append(f"<ul>{items}</ul>")
        else:
            blocks.append(f"<p>{md_inline(' '.join(lines))}</p>")
    return "\n".join(blocks)


def check_state(meta, path, allowed, field="상태"):
    """상태는 있으면 검사하고, 없으면 None. 날짜·제목과 달리 필수가 아니다."""
    value = meta.get("status") or meta.get("상태")
    if not value:
        return None
    if value not in allowed:
        raise ContentError(
            f"{path.name}: {field} '{value}' 는 쓸 수 없습니다 "
            f"(가능: {' / '.join(allowed)})"
        )
    return value


def load_logs():
    errors, entries = [], []
    for path in sorted(LOG_DIR.glob("*.md")):
        try:
            meta, body = parse_front_matter(path)
            raw_date = meta.get("date") or meta.get("날짜")
            title = meta.get("title") or meta.get("제목")
            # 요청 규칙: 날짜나 제목이 없으면 조용히 넘어가지 않는다
            if not raw_date:
                raise ContentError(f"{path.name}: 날짜(date)가 없습니다")
            if not title:
                raise ContentError(f"{path.name}: 제목(title)이 없습니다")
            entries.append(
                {
                    "date": parse_date(raw_date, path),
                    "title": title,
                    "tags": split_tags(meta.get("tags") or meta.get("태그")),
                    "state": check_state(meta, path, LOG_STATES),
                    "project": meta.get("project") or meta.get("프로젝트") or "",
                    "body": md_body(body),
                    "file": path.name,
                }
            )
        except ContentError as e:
            errors.append(str(e))
    entries.sort(key=lambda e: (e["date"], e["file"]), reverse=True)
    return entries, errors


def load_projects():
    errors, cards = [], []
    for path in sorted(PROJ_DIR.glob("*.md")):
        try:
            meta, body = parse_front_matter(path)
            name = meta.get("name") or meta.get("이름") or meta.get("title")
            if not name:
                raise ContentError(f"{path.name}: 이름(name)이 없습니다")
            first_line = body.strip().splitlines()[0] if body.strip() else ""
            summary = meta.get("summary") or meta.get("설명") or first_line
            cards.append(
                {
                    "name": name,
                    "slug": meta.get("slug") or slugify(name),
                    "aliases": split_tags(meta.get("aliases") or meta.get("옛이름")),
                    "summary": summary,
                    "state": check_state(meta, path, PROJ_STATES),
                    "tools": split_tags(meta.get("tools") or meta.get("도구")),
                    "order": meta.get("order") or meta.get("순서") or "999",
                    "file": path.name,
                }
            )
        except ContentError as e:
            errors.append(str(e))
    cards.sort(key=lambda c: (int(c["order"]) if c["order"].isdigit() else 999, c["file"]))
    # 슬러그가 겹치면 페이지 파일이 서로 덮어써진다. 조용히 넘어가면 안 된다.
    seen = {}
    for c in cards:
        if c["slug"] in seen:
            errors.append(
                f"{c['file']}: 주소가 '{seen[c['slug']]}' 와 겹칩니다 "
                f"(둘 다 /project/{c['slug']}.html). 한쪽에 slug: 를 적어 구분해주세요"
            )
        else:
            seen[c["slug"]] = c["file"]
    return cards, errors


def load_about():
    if not ABOUT.exists():
        return f"<p>{html.escape(TAGLINE)}</p>"
    text = ABOUT.read_text(encoding="utf-8-sig")
    if text.startswith("---"):
        _, text = parse_front_matter(ABOUT)
    return md_body(text)


def state_class(value):
    """한글 상태값을 CSS 클래스로. ASCII가 아니면 클래스명으로 못 쓴다."""
    return {
        "운영 중": "live",
        "만드는 중": "wip",
        "멈춤": "paused",
        "러프": "rough",
        "다듬는 중": "shaping",
        "정리됨": "done",
    }.get(value, "none")


def fmt_date(d):
    return f"{d.year}.{d.month:02d}.{d.day:02d}"


def slugify(name):
    """프로젝트 이름 → 파일명. 한글은 그대로 두고 공백·특수문자만 정리."""
    s = name.strip().lower().replace(" ", "-")
    s = re.sub(r"[^0-9a-z가-힣ㄱ-ㅎㅏ-ㅣ._-]", "", s)
    return s.strip("-.") or "project"


def logs_for(project, logs):
    """이 프로젝트의 일지.

    태그나 project 항목이 아래 중 아무거나와 맞으면 가져온다.
    이름을 바꿔도 예전 태그로 쓴 일지가 떨어져 나가지 않게 하려는 것.
      - 표시 이름 (밤새 도는 손)
      - 주소 슬러그 (threads-poster)
      - 별칭 aliases: 에 적은 것들
      - 마크다운 파일명 (threads-poster.md → threads-poster)
    """
    keys = {project["name"].lower(), project["slug"]}
    keys |= {a.lower() for a in project["aliases"]}
    keys |= {slugify(a) for a in project["aliases"]}
    stem = Path(project["file"]).stem.lower()
    keys |= {stem, stem.replace("-", "_"), stem.replace("_", "-")}
    # blog-auto 와 blog_auto 처럼 구분자만 다른 경우도 같이 본다
    keys |= {k.replace("_", "-") for k in list(keys)}

    picked = []
    for e in logs:
        marks = {t.lower() for t in e["tags"]} | {slugify(t) for t in e["tags"]}
        if e["project"]:
            marks |= {e["project"].lower(), slugify(e["project"])}
        marks |= {m.replace("_", "-") for m in list(marks)}
        if marks & keys:
            picked.append(e)
    return picked


CSS = """
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:#fbfbfa;color:#1d1c1a;
  font:16px/1.75 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Pretendard",
  "Malgun Gothic","맑은 고딕",system-ui,sans-serif;
  -webkit-text-size-adjust:100%;word-break:keep-all;overflow-wrap:anywhere}
.wrap{max-width:44rem;margin:0 auto;padding:4.5rem 1.25rem 6rem}
a{color:inherit;text-underline-offset:.2em;text-decoration-color:#c9c6c0}
code{background:#f0efec;padding:.1em .35em;border-radius:3px;font-size:.9em}
header{margin-bottom:5rem}
h1{margin:0;font-size:1.5rem;font-weight:650;letter-spacing:-.02em;
  display:flex;align-items:center;gap:.6rem;flex-wrap:wrap}
header .tools{margin-top:1rem}
footer a{text-decoration:none;color:inherit}
.tagline{margin:.6rem 0 0;color:#6b6862;font-size:1rem}
section{margin-bottom:4.5rem}
h2{margin:0 0 1.75rem;font-size:.8rem;font-weight:600;letter-spacing:.13em;
  color:#8a867e;text-transform:uppercase}
.cards{display:grid;gap:.75rem;grid-template-columns:1fr}
@media(min-width:34rem){.cards{grid-template-columns:1fr 1fr}}
.card{border:1px solid #e6e3dd;border-radius:10px;padding:1.15rem 1.25rem;background:#fff;
  display:block;text-decoration:none;color:inherit;transition:border-color .15s,transform .15s}
a.card:hover{border-color:#bdb9b1;transform:translateY(-1px)}
a.card:focus-visible{outline:2px solid #8a867e;outline-offset:2px}
.count{display:inline-block;margin-top:.85rem;font-size:.75rem;color:#8a867e}
.count::after{content:" →";color:#b5b1aa}
.back{margin:0 0 1.5rem;font-size:.85rem}
.back a{color:#8a867e;text-decoration:none}
.back a:hover{color:#403d38;text-decoration:underline}
.muted{color:#8a867e}
.card h3{margin:0;font-size:1rem;font-weight:620;display:flex;align-items:center;
  gap:.5rem;flex-wrap:wrap}
.card p{margin:.5rem 0 0;color:#5f5c56;font-size:.925rem;line-height:1.65}
.tools{margin:.85rem 0 0;padding:0;list-style:none;display:flex;flex-wrap:wrap;gap:.3rem}
.tools li{font-size:.75rem;color:#7d7a73;background:#f4f2ee;
  padding:.15rem .5rem;border-radius:4px}
.badge{font-size:.7rem;font-weight:600;padding:.15rem .5rem;border-radius:20px;
  letter-spacing:.02em;white-space:nowrap;flex-shrink:0}
.badge.live{background:#e4f0e6;color:#2f6b3c}
.badge.wip{background:#fdf0dd;color:#8a5a17}
.badge.paused{background:#eeecea;color:#6f6b65}
.badge.rough{background:#f0eef8;color:#565090}
.badge.shaping{background:#fdf0dd;color:#8a5a17}
.badge.done{background:#e4f0e6;color:#2f6b3c}
.card.empty{border-style:dashed;background:transparent;display:flex;
  align-items:center;justify-content:center;min-height:6.5rem}
.card.empty span{color:#a5a19a;font-size:.875rem}
.log{border-top:1px solid #e6e3dd;padding:1.6rem 0 0;margin:1.6rem 0 0}
.log:first-of-type{border-top:0;padding-top:0;margin-top:0}
.log-head{display:flex;align-items:baseline;gap:.6rem;flex-wrap:wrap}
time{color:#8a867e;font-size:.8rem;font-variant-numeric:tabular-nums;flex-shrink:0}
.log h3{margin:0;font-size:1.02rem;font-weight:620;letter-spacing:-.01em}
.log-body{margin-top:.5rem;color:#403d38}
.log-body p{margin:.5rem 0 0}
.log-body p:first-child{margin-top:0}
.log-body ul{margin:.5rem 0 0;padding-left:1.15rem}
.log-body li{margin:.15rem 0}
.tags{margin:.7rem 0 0;padding:0;list-style:none;display:flex;flex-wrap:wrap;gap:.3rem}
.tags li{font-size:.75rem;color:#8a867e}
.tags li::before{content:"#"}
.about p{margin:0 0 .9rem;color:#403d38}
.about p:last-child{margin-bottom:0}
footer{margin-top:5rem;padding-top:1.5rem;border-top:1px solid #e6e3dd;
  color:#a5a19a;font-size:.8rem}
"""


def card_html(c, base=""):
    badge = (
        f'<span class="badge {state_class(c["state"])}">{html.escape(c["state"])}</span>'
        if c["state"]
        else ""
    )
    tools = (
        '<ul class="tools">'
        + "".join(f"<li>{html.escape(t)}</li>" for t in c["tools"])
        + "</ul>"
        if c["tools"]
        else ""
    )
    summary = f"<p>{md_inline(c['summary'])}</p>" if c["summary"] else ""
    count = (
        f'<span class="count">일지 {c["log_count"]}</span>' if c.get("log_count") else ""
    )
    return (
        f'<a class="card" href="{base}project/{c["slug"]}.html">'
        f'<h3>{html.escape(c["name"])}{badge}</h3>{summary}{tools}{count}</a>'
    )


def log_html(e, show_tags=True):
    badge = (
        f'<span class="badge {state_class(e["state"])}">{html.escape(e["state"])}</span>'
        if e["state"]
        else ""
    )
    tags = (
        '<ul class="tags">'
        + "".join(f"<li>{html.escape(t)}</li>" for t in e["tags"])
        + "</ul>"
        if e["tags"] and show_tags
        else ""
    )
    body = f'<div class="log-body">{e["body"]}</div>' if e["body"] else ""
    return (
        f'<article class="log"><div class="log-head">'
        f'<time datetime="{e["date"].isoformat()}">{fmt_date(e["date"])}</time>'
        f'<h3>{html.escape(e["title"])}</h3>{badge}</div>{body}{tags}</article>'
    )


def page(title, body, desc=TAGLINE, base=""):
    """모든 페이지가 쓰는 공통 껍데기."""
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:type" content="website">
<link rel="icon" href="data:,">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
{body}
<footer><a href="{base}index.html">{html.escape(SITE_NAME)}</a></footer>
</div>
</body>
</html>
"""


def render(logs, projects, about):
    cards = "".join(card_html(c) for c in projects)
    cards += '<article class="card empty"><span>빈 칸</span></article>'
    entries = "".join(log_html(e) for e in logs) or "<p>아직 없습니다.</p>"
    body = f"""<header>
<h1>{html.escape(SITE_NAME)}</h1>
<p class="tagline">{html.escape(TAGLINE)}</p>
</header>
<main>
<section><h2>만든 것</h2><div class="cards">{cards}</div></section>
<section id="log"><h2>작업 일지</h2>{entries}</section>
<section><h2>소개</h2><div class="about">{about}</div></section>
</main>"""
    return page(SITE_NAME, body)


def render_project(project, entries):
    """프로젝트 한 개의 일지 모음 페이지."""
    badge = (
        f'<span class="badge {state_class(project["state"])}">'
        f'{html.escape(project["state"])}</span>'
        if project["state"]
        else ""
    )
    tools = (
        '<ul class="tools">'
        + "".join(f"<li>{html.escape(t)}</li>" for t in project["tools"])
        + "</ul>"
        if project["tools"]
        else ""
    )
    summary = f'<p class="tagline">{md_inline(project["summary"])}</p>' if project["summary"] else ""
    logs_html = (
        "".join(log_html(e, show_tags=False) for e in entries)
        or '<p class="muted">아직 이 프로젝트로 쓴 일지가 없습니다.</p>'
    )
    body = f"""<header>
<p class="back"><a href="../index.html#log">← 전체 일지</a></p>
<h1>{html.escape(project["name"])}{badge}</h1>
{summary}{tools}
</header>
<main><section><h2>작업 일지</h2>{logs_html}</section></main>"""
    return page(
        f'{project["name"]} — {SITE_NAME}',
        body,
        desc=project["summary"] or TAGLINE,
        base="../",
    )


def main():
    logs, log_errors = load_logs()
    projects, proj_errors = load_projects()
    errors = log_errors + proj_errors

    if errors:
        print("발행을 멈췄습니다. 아래 파일을 고쳐주세요:\n", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print(f"\n({len(errors)}개 문제)", file=sys.stderr)
        return 1

    # 카드에 일지 개수를 보여주려면 먼저 세어야 한다
    matched = {c["slug"]: logs_for(c, logs) for c in projects}
    for c in projects:
        c["log_count"] = len(matched[c["slug"]])

    if "--check" in sys.argv:
        print(f"이상 없음 — 일지 {len(logs)}개, 프로젝트 {len(projects)}개")
        for c in projects:
            print(f"    {c['name']}: 일지 {c['log_count']}개  → project/{c['slug']}.html")
        return 0

    (ROOT / "index.html").write_text(
        render(logs, projects, load_about()), encoding="utf-8"
    )

    proj_dir = ROOT / "project"
    proj_dir.mkdir(exist_ok=True)
    # 지운 프로젝트의 페이지가 남지 않게 먼저 비운다
    keep = {f"{c['slug']}.html" for c in projects}
    for old in proj_dir.glob("*.html"):
        if old.name not in keep:
            old.unlink()
    for c in projects:
        (proj_dir / f"{c['slug']}.html").write_text(
            render_project(c, matched[c["slug"]]), encoding="utf-8"
        )

    print(
        f"index.html + 프로젝트 페이지 {len(projects)}개 생성 — "
        f"일지 {len(logs)}개, 프로젝트 {len(projects)}개 (+빈 칸)"
    )
    for c in projects:
        print(f"    project/{c['slug']}.html  (일지 {c['log_count']}개)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
