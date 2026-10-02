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
            date_display = meta.get("date_display", "full")
            if date_display not in ("full", "year"):
                raise ContentError(f"{path.name}: date_display는 full 또는 year여야 합니다")
            entries.append(
                {
                    "date": parse_date(raw_date, path),
                    "date_display": date_display,
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
    entries.sort(key=lambda e: (e["date_display"] == "full", e["date"], e["file"]), reverse=True)
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
            featured = meta.get("featured", "false")
            if featured not in ("true", "false"):
                raise ContentError(f"{path.name}: featured는 true 또는 false여야 합니다")
            if featured == "true":
                for field in ("problem", "approach", "result"):
                    if not meta.get(field):
                        raise ContentError(f"{path.name}: 대표 작업의 {field} 항목이 없습니다")
            cards.append(
                {
                    "name": name,
                    "slug": meta.get("slug") or slugify(name),
                    "aliases": split_tags(meta.get("aliases") or meta.get("옛이름")),
                    "summary": summary,
                    "featured": featured == "true",
                    "problem": meta.get("problem", ""),
                    "approach": meta.get("approach", ""),
                    "result": meta.get("result", ""),
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
html{scroll-behavior:smooth;scroll-padding-top:1rem}
body{margin:0;background:#f7f6ef;color:#183e35;
  background-image:radial-gradient(ellipse 65% 24rem at 45% 0,#dceacb 0,transparent 100%);
  font:16px/1.7 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;
  -webkit-text-size-adjust:100%;word-break:keep-all;overflow-wrap:anywhere}
a{color:inherit;text-underline-offset:.24em}
a:focus-visible{outline:3px solid #175d4e;outline-offset:4px}
::selection{background:#d1b5ef;color:#173f35}
.wrap{max-width:72rem;margin:auto;padding:0 1.5rem}
.site-nav{display:flex;align-items:center;justify-content:space-between;gap:.75rem;padding:1.25rem 0;border-bottom:1px solid #d3dcce}
.brand{font-size:1.15rem;font-weight:750;letter-spacing:-.05em;text-decoration:none}
.nav-links{display:flex;gap:.15rem}
.nav-links a{font-size:.8rem;text-decoration:none;padding:.4rem .6rem;border-radius:.5rem}
.nav-links a:hover{background:#ffffff80}
.skip{position:absolute;left:1rem;top:-6rem;background:#fff;padding:.5rem 1rem;z-index:10}
.skip:focus{top:1rem}
.hero{padding:2rem 0 2.5rem}
.eyebrow{margin:0 0 .7rem;font-size:.76rem;color:#526b5c;letter-spacing:.04em}
.hero h1{font-size:clamp(1.6rem,3.5vw,2.2rem);line-height:1.4;letter-spacing:-.055em;margin:0;font-weight:750;color:#07564a}
.hero h1 span{margin-left:.25em}
.hero .tagline{margin:.65rem 0 0;color:#44685c;font-size:.9rem}
.hero-foot{margin-top:.8rem;font-size:.75rem;color:#44685c}
section{margin-bottom:3rem}
.section-head{display:flex;align-items:baseline;justify-content:space-between;gap:.75rem;margin-bottom:.9rem}
h2{font-size:1.2rem;letter-spacing:-.035em;font-weight:700;margin:0}
.section-head p{font-size:.75rem;color:#5a7166;margin:0;text-align:right}
.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.75rem}
.collection-label{grid-column:1/-1;display:flex;justify-content:space-between;gap:1rem;margin:0;font-size:.85rem;font-weight:650}
.collection-label span{font-weight:400;font-size:.75rem;color:#526b5c}
.collection-label.secondary{margin-top:1rem;padding-top:1rem;border-top:1px solid #d3dcce}
.card.featured{border-top:3px solid #175d4e;padding-top:.9rem}
.case{margin:.8rem 0 0;display:grid;gap:.6rem;font-size:.82rem;line-height:1.65}
.case div{display:grid;grid-template-columns:3.3rem minmax(0,1fr);gap:.45rem}
.case dt{color:#35584d;font-size:.7rem;padding-top:.1rem;font-weight:600}
.case dd{margin:0;color:#183e35}
.card{--card-color:#b2ddd1;background:var(--card-color);border-radius:.85rem;padding:1rem;
  display:flex;flex-direction:column;text-decoration:none;color:#183e35;transition:box-shadow .15s}
.card:nth-of-type(6n+2){--card-color:#d6c1eb}
.card:nth-of-type(6n+3){--card-color:#f3d6b9}
.card:nth-of-type(6n+4){--card-color:#c8daed}
.card:nth-of-type(6n+5){--card-color:#e5dfa9}
.card:nth-of-type(6n){--card-color:#e8c8cf}
a.card:hover{box-shadow:inset 0 0 0 1px #35584d60}
.card-meta{display:flex;justify-content:space-between;align-items:flex-start;gap:.5rem}
.card h3{margin:0;min-width:0;font-size:1.05rem;letter-spacing:-.035em;line-height:1.5;font-weight:700}
.card p{margin:.55rem 0 0;font-size:.85rem;line-height:1.65;color:#36594e}
.project-list{grid-column:1/-1;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.5rem .75rem}
.card.compact{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:0 .75rem;padding:.65rem .85rem;border-radius:.4rem}
.compact h3{font-size:.9rem}.compact p{margin:.1rem 0 0;font-size:.8rem}
.compact .arrow{grid-column:2;grid-row:1/3;font-size:.9rem}
.card-bottom{display:flex;align-items:flex-end;justify-content:space-between;gap:.6rem;margin-top:auto;padding-top:.85rem}
.tools{display:flex;flex-wrap:wrap;gap:.15rem .5rem;list-style:none;padding:0;margin:0}
.tools li{font-size:.72rem;line-height:1.6;color:#35584d}
.count{font-size:.72rem;white-space:nowrap;flex-shrink:0}
.count::after{content:" ↗"}
.badge{display:inline-block;flex-shrink:0;font-size:.68rem;padding:.15rem .5rem;border-radius:99px;line-height:1.6;white-space:nowrap;font-weight:550}
.badge.live,.badge.done{background:#ffffff85;color:#225440}
.badge.wip,.badge.shaping{background:#fff2d2;color:#6d4e19}
.badge.paused{background:#e6e8e2;color:#4e594e}
.badge.rough{background:#e5dcf0;color:#57436b}
.card.empty{grid-column:1/-1;background:transparent;border:1px dashed #b6c7b6;flex-direction:row;align-items:center;justify-content:center;text-align:center;gap:.6rem;padding:.65rem}
.empty-mark{font-size:1.5rem;line-height:1;color:#8ca391}
.card.empty span:last-of-type{font-size:.95rem;font-weight:600}
.card.empty p{color:#5a7166;font-size:.8rem;margin:.25rem 0 0}
.journal{max-width:49rem;margin:0 auto 3rem}
.journal .section-head{padding-bottom:.8rem;border-bottom:1px solid #cfdbce;margin-bottom:0}
.log{padding:1.15rem 0;border-bottom:1px solid #dce3d7}
.log-head{display:flex;align-items:center;gap:.4rem .6rem;flex-wrap:wrap}
.log-date{color:#566d60;font-size:.75rem;font-variant-numeric:tabular-nums;flex-basis:100%}
.log h3{font-size:1rem;line-height:1.5;letter-spacing:-.02em;margin:0;font-weight:650}
.log h3 a{text-decoration:none}.log h3 a:hover{text-decoration:underline}
.log-body{margin-top:.6rem;color:#40574b;font-size:.9rem;line-height:1.8}
.log-body p{margin:.6rem 0 0}.log-body p:first-child{margin-top:0}
.log-body ul{padding-left:1.2rem}.log-body li{margin:.25rem 0}
.tags{display:flex;gap:.5rem;flex-wrap:wrap;padding:0;list-style:none;margin:.5rem 0 0}
.tags li{font-size:.7rem;color:#526b5c}.tags li::before{content:"#"}
code{font-size:.9em;background:#e9ece2;border-radius:.2rem;padding:.1em .35em}
.about-section{background:#e4ead9;border-radius:.85rem;padding:1.5rem;display:grid;grid-template-columns:1fr 3fr;gap:1.5rem}
.about p{margin:0 0 .7rem;color:#40574b;font-size:.9rem}.about p:first-child{font-size:1.1rem;font-weight:650;color:#175d4e}.about p:last-child{margin-bottom:0}
footer{border-top:1px solid #d3dcce;padding:1.3rem 0 2rem;display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;font-size:.75rem;color:#526b5c}
footer a{text-decoration:none;font-weight:700;font-size:.9rem}
.project-header{padding:2rem 0 1.5rem;margin:0 auto;max-width:49rem}
.project-header h1{font-size:clamp(1.5rem,4vw,2rem);line-height:1.4;letter-spacing:-.045em;margin:.7rem 0;color:#07564a}
.project-header .tagline{color:#44685c;margin:.7rem 0;font-size:.95rem}
.project-header .tools{margin-top:.8rem}.project-header .tools li{font-size:.75rem}
.project-header .case{padding:1rem;background:#e4ead9;border-radius:.65rem;margin-top:1.3rem;font-size:.9rem}
.back{margin:0 0 1rem;font-size:.8rem}.back a{text-decoration:none}
.project-main{max-width:49rem;margin:auto}.project-main h2{padding-bottom:.8rem;border-bottom:1px solid #cfdbce}
.muted{color:#566d60}
@media(max-width:1000px){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:600px){
  .wrap{padding:0 1rem}.site-nav{padding:1rem 0;gap:.4rem}.brand{font-size:1.05rem}
  .nav-links a{font-size:.75rem;padding:.35rem .45rem}
  .hero{padding:1.5rem 0 2rem}.hero h1 span{display:block;margin-left:0}
  .cards{grid-template-columns:minmax(0,1fr);gap:.6rem}
  .project-list{grid-template-columns:minmax(0,1fr)}
  .section-head p{max-width:11rem}
  .about-section{grid-template-columns:1fr;padding:1.15rem;gap:.8rem}
}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important}}
"""


def case_html(project):
    if not project.get("featured"):
        return ""
    return '<dl class="case">' + "".join(
        f'<div><dt>{label}</dt><dd>{html.escape(project[field])}</dd></div>'
        for field, label in (("problem", "출발점"), ("approach", "만든 방식"), ("result", "지금은"))
    ) + "</dl>"


def card_html(c, base=""):
    if not c.get("featured"):
        return (
            f'<a class="card compact" href="{base}project/{c["slug"]}.html">'
            f'<h3>{html.escape(c["name"])}</h3><p>{html.escape(c["summary"])}</p>'
            '<span class="arrow" aria-hidden="true">↗</span></a>'
        )
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
    count = (
        '<span class="count">작업 기록</span>' if c.get("log_count") else '<span class="count">프로젝트 보기</span>'
    )
    return (
        f'<a class="card featured" href="{base}project/{c["slug"]}.html">'
        f'<div class="card-meta"><h3>{html.escape(c["name"])}</h3>{badge}</div>{case_html(c)}'
        f'<div class="card-bottom">{tools}{count}</div></a>'
    )


def log_html(e, show_tags=True, href="", compact=False):
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
    content = e["body"].split("\n", 1)[0] if compact else e["body"]
    body = f'<div class="log-body">{content}</div>' if content else ""
    title = html.escape(e["title"])
    if href:
        title = f'<a href="{html.escape(href, quote=True)}">{title}</a>'
    date_label = (
        f'<span class="log-date">{e["date"].year}년 · 작업 정리</span>'
        if e.get("date_display") == "year"
        else f'<time class="log-date" datetime="{e["date"].isoformat()}">{fmt_date(e["date"])}</time>'
    )
    return (
        f'<article class="log"><div class="log-head">'
        f'{date_label}'
        f'<h3>{title}</h3>{badge}</div>{body}{tags}</article>'
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
<a class="skip" href="#main">본문으로 건너뛰기</a>
<div class="wrap">
<nav class="site-nav" aria-label="주 메뉴">
<a class="brand" href="{base}index.html">{html.escape(SITE_NAME)}</a>
<div class="nav-links"><a href="{base}index.html#work">만든 것</a><a href="{base}index.html#log">작업 일지</a><a href="{base}index.html#about">소개</a></div>
</nav>
{body}
<footer><a href="{base}index.html">{html.escape(SITE_NAME)}</a><span>혼자 만들고, 조금씩 고칩니다.</span></footer>
</div>
</body>
</html>
"""


def render(logs, projects, about):
    featured = [project for project in projects if project.get("featured")]
    others = [project for project in projects if not project.get("featured")]
    cards = '<p class="collection-label">대표 작업<span>자동화 · 생활 앱 · 사용성 개선</span></p>' if featured else ""
    cards += "".join(card_html(project) for project in featured)
    if featured and others:
        cards += '<p class="collection-label secondary">그 밖에 만든 것<span>작게 시작해 다듬는 도구들</span></p>'
    if others:
        cards += '<div class="project-list">' + "".join(card_html(project) for project in others) + '</div>'
    cards += '<article class="card empty"><span class="empty-mark" aria-hidden="true">＋</span><span>빈 칸</span><p>다음에 만들 것은 아직 비워둡니다.</p></article>'
    links = {}
    for project in projects:
        for entry in logs_for(project, logs):
            links.setdefault(entry["file"], f'project/{project["slug"]}.html')
    entries = "".join(log_html(entry, href=links.get(entry["file"], ""), compact=True) for entry in logs) or "<p>아직 없습니다.</p>"
    body = f"""<header class="hero">
<p class="eyebrow">카르돈의 작은 작업실</p>
<h1>반복되는 일은 덜고,<span>남기고 싶은 순간은 담습니다.</span></h1>
<p class="tagline">직접 쓰려고 만든 자동화와 생활 앱입니다.<br>무엇을 만들었는지보다, 어떤 불편을 어떻게 풀었는지 남깁니다.</p>
<div class="hero-foot">기획부터 구현·운영까지 직접 · Python / Flutter / Apps Script</div>
</header>
<main id="main">
<section id="work"><div class="section-head"><h2>만든 것</h2><p>{len(projects)}개의 앱과 자동화 · 카드에서 작업 기록으로</p></div><div class="cards">{cards}</div></section>
<section id="log" class="journal"><div class="section-head"><h2>작업 일지</h2><p>제목을 누르면 프로젝트별 전체 기록을 볼 수 있습니다.</p></div>{entries}</section>
<section id="about" class="about-section"><h2>소개</h2><div class="about">{about}</div></section>
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
    body = f"""<header class="project-header">
<p class="back"><a href="../index.html#log">← 전체 일지</a></p>
{badge}<h1>{html.escape(project["name"])}</h1>
{summary}{tools}{case_html(project)}
</header>
<main id="main" class="project-main"><section><h2>작업 일지</h2>{logs_html}</section></main>"""
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

    # 이 사이트는 프로젝트 업데이트를 올리는 곳이다.
    # 어느 프로젝트에도 안 붙은 일지는 태그를 빠뜨린 것일 수 있으니 알려준다.
    # 다만 일부러 그런 걸 수도 있으니 발행을 막지는 않는다.
    attached = {id(e) for group in matched.values() for e in group}
    orphans = [e for e in logs if id(e) not in attached]
    if orphans:
        print("\n  참고 — 어느 프로젝트에도 안 붙은 일지:", file=sys.stderr)
        for e in orphans:
            print(f"    {e['file']}  ({e['title']})", file=sys.stderr)
        print(
            "    tags 에 프로젝트 이름을 적으면 그 프로젝트 페이지에도 들어갑니다.\n",
            file=sys.stderr,
        )

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
