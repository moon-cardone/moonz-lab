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
            image_name = meta.get("image", "")
            image_alt = meta.get("image_alt", "")
            if image_name:
                if not re.fullmatch(r"[a-z0-9-]+\.(png|jpg|webp)", image_name):
                    raise ContentError(f"{path.name}: image에는 assets/projects/ 안의 이미지 파일명만 적어주세요")
                if not (ROOT / "assets" / "projects" / image_name).is_file():
                    raise ContentError(f"{path.name}: 이미지 파일 '{image_name}'이 없습니다")
                if not image_alt:
                    raise ContentError(f"{path.name}: 이미지 설명(image_alt)이 없습니다")
            cards.append(
                {
                    "name": name,
                    "slug": meta.get("slug") or slugify(name),
                    "aliases": split_tags(meta.get("aliases") or meta.get("옛이름")),
                    "summary": summary,
                    "image": image_name,
                    "image_alt": image_alt,
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
html{scroll-behavior:smooth;scroll-padding-top:2rem}
body{margin:0;background:#f7f6ef;color:#183e35;
  background-image:radial-gradient(ellipse 65% 35rem at 45% 0,#dceacb 0,transparent 100%);
  font:16px/1.75 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;
  -webkit-text-size-adjust:100%;word-break:keep-all;overflow-wrap:anywhere}
a{color:inherit;text-underline-offset:.24em}
a:focus-visible{outline:3px solid #175d4e;outline-offset:5px}
::selection{background:#d1b5ef;color:#173f35}
.wrap{max-width:76rem;margin:auto;padding:0 2rem}
.site-nav{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:2rem 0}
.brand{font-size:1.3rem;font-weight:800;letter-spacing:-.06em;text-decoration:none}
.nav-links{display:flex;gap:.25rem;padding:.35rem;background:#ffffff65;border-radius:99px}
.nav-links a{font-size:.85rem;text-decoration:none;padding:.45rem 1rem;border-radius:99px}
.nav-links a:hover{background:#fff9}
.skip{position:absolute;left:1rem;top:-6rem;background:#fff;padding:.5rem 1rem;z-index:10}
.skip:focus{top:1rem}
.hero{text-align:center;position:relative;padding:4.5rem 0 6.5rem}
.eyebrow{font-size:.72rem;letter-spacing:.18em;font-weight:650;margin:0 0 1.5rem}
.hero h1{font-size:clamp(2.65rem,6.5vw,5.5rem);line-height:1.24;letter-spacing:-.075em;margin:0;font-weight:800;color:#07564a}
.hero h1 span{display:block}
.hero .tagline{max-width:34rem;margin:1.8rem auto 0;color:#44685c;font-size:1.05rem}
.hero .spark{position:absolute;font-size:3.5rem;color:#fff;line-height:1;pointer-events:none}
.hero .spark:first-child{left:7%;top:48%;transform:rotate(-15deg)}
.hero .spark:nth-child(2){right:9%;top:15%;font-size:2.5rem;transform:rotate(15deg)}
.hero-foot{display:flex;justify-content:center;gap:.75rem;align-items:center;margin-top:2.3rem;font-size:.8rem;color:#44685c}
.hero-foot::before{content:"";width:6px;height:6px;background:#44795f;border-radius:50%}
section{margin-bottom:6.5rem}
.section-head{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;margin-bottom:1.6rem}
h2{font-size:1.7rem;letter-spacing:-.055em;font-weight:750;margin:0}
.section-head p{font-size:.82rem;color:#5a7166;margin:0;text-align:right}
.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1.4rem}
.card{--card-color:#b2ddd1;background:var(--card-color);border-radius:2rem;padding:2rem 2rem 1.5rem;
  display:flex;flex-direction:column;text-decoration:none;color:#183e35;position:relative;overflow:hidden;
  min-height:16rem;transition:transform .22s,box-shadow .22s}
.card:nth-child(6n+2){--card-color:#d6c1eb}
.card:nth-child(6n+3){--card-color:#f3d6b9}
.card:nth-child(6n+4){--card-color:#c8daed}
.card:nth-child(6n+5){--card-color:#e5dfa9}
.card:nth-child(6n){--card-color:#e8c8cf}
a.card:hover{transform:translateY(-5px);box-shadow:0 15px 30px -20px #254a4355}
.card-meta{display:flex;justify-content:space-between;align-items:center;gap:.5rem;margin-bottom:.7rem}
.card-label{font-size:.65rem;letter-spacing:.16em;font-weight:650}
.card h3{margin:0;font-size:1.75rem;letter-spacing:-.055em;line-height:1.35;font-weight:750}
.card p{margin:.65rem 0 0;max-width:27rem;font-size:.9rem;line-height:1.65;color:#36594e}
.card-bottom{display:flex;align-items:flex-end;justify-content:space-between;gap:1rem;margin-top:auto;padding-top:1.8rem}
.tools{display:flex;flex-wrap:wrap;gap:.3rem .65rem;list-style:none;padding:0;margin:0}
.tools li{font-size:.67rem;line-height:1.6;color:#35584d}
.count{font-size:.73rem;white-space:nowrap;flex-shrink:0}
.count::after{content:" ↗";font-size:1rem}
.badge{display:inline-block;font-size:.7rem;padding:.2rem .65rem;border-radius:99px;line-height:1.6;white-space:nowrap;font-weight:550}
.badge.live,.badge.done{background:#ffffff85;color:#225440}
.badge.wip,.badge.shaping{background:#fff2d2;color:#6d4e19}
.badge.paused{background:#e6e8e2;color:#4e594e}
.badge.rough{background:#e5dcf0;color:#57436b}
.project-image{display:block;width:100%;height:23rem;object-fit:contain;margin:1.5rem 0 0;border-radius:.8rem;background:#ffffff50}
.card.empty{background:transparent;border:1.5px dashed #b6c7b6;align-items:center;justify-content:center;text-align:center;gap:.8rem;min-height:20rem}
.empty-mark{font-size:4rem;font-weight:250;line-height:1;color:#8ca391}
.card.empty span:last-of-type{font-size:1.2rem;font-weight:650}
.card.empty p{color:#5a7166;font-size:.85rem;margin:0}
.journal{max-width:52rem;margin:0 auto 6.5rem}
.journal .section-head{padding-bottom:1.5rem;border-bottom:1px solid #cfdbce;margin-bottom:0}
.log{padding:2rem 0;border-bottom:1px solid #dce3d7}
.log-head{display:flex;align-items:center;gap:.65rem;flex-wrap:wrap}
.log-date{color:#566d60;font-size:.76rem;font-variant-numeric:tabular-nums;flex-basis:100%;letter-spacing:.04em}
.log h3{font-size:1.15rem;line-height:1.5;letter-spacing:-.025em;margin:0;font-weight:650}
.log-body{margin-top:.9rem;color:#40574b;font-size:.94rem;line-height:1.9}
.log-body p{margin:.7rem 0 0}.log-body p:first-child{margin-top:0}
.log-body ul{padding-left:1.2rem}.log-body li{margin:.3rem 0}
.tags{display:flex;gap:.5rem;flex-wrap:wrap;padding:0;list-style:none;margin:.8rem 0 0}
.tags li{font-size:.7rem;color:#526b5c}.tags li::before{content:"#"}
code{font-size:.9em;background:#e9ece2;border-radius:.2rem;padding:.1em .35em}
.about-section{background:#e4ead9;border-radius:2rem;padding:3rem;display:grid;grid-template-columns:1fr 2fr;gap:2rem}
.about p{margin:0 0 1rem;color:#40574b}.about p:first-child{font-size:1.8rem;font-weight:700;line-height:1.4;letter-spacing:-.05em;color:#175d4e}.about p:last-child{margin-bottom:0}
footer{border-top:1px solid #d3dcce;padding:2rem 0 3rem;display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;font-size:.78rem;color:#526b5c}
footer a{text-decoration:none;font-weight:750;font-size:1rem;letter-spacing:-.04em}
.project-header{padding:3.5rem 0;margin:0 auto 2.5rem;max-width:52rem}
.project-header h1{font-size:clamp(2rem,5vw,3.5rem);line-height:1.3;letter-spacing:-.06em;margin:1rem 0;color:#07564a}
.project-header .tagline{color:#44685c;max-width:38rem;margin:1rem 0;font-size:1.1rem}
.project-header .tools{margin-top:1.3rem}.project-header .tools li{font-size:.8rem}
.back{margin:0 0 2rem;font-size:.85rem}.back a{text-decoration:none}
.project-main{max-width:52rem;margin:auto}.project-main h2{padding-bottom:1.5rem;border-bottom:1px solid #cfdbce}
.muted{color:#566d60}
@media(max-width:700px){
  .wrap{padding:0 1.15rem}.site-nav{padding:1.2rem 0;gap:.5rem}.brand{font-size:1.1rem}
  .nav-links a{font-size:.74rem;padding:.35rem .6rem}.nav-links{padding:.25rem;gap:0}
  .hero{padding:3.2rem 0 4rem}.hero .tagline{font-size:.93rem;max-width:20rem;margin-top:1.4rem}
  .hero .spark:first-child{left:1%;top:5%;font-size:1.8rem}.hero .spark:nth-child(2){right:3%;top:6%;font-size:1.2rem}
  .eyebrow{font-size:.6rem;margin-bottom:1rem}.hero-foot{margin-top:1.4rem;font-size:.72rem}
  .cards{grid-template-columns:minmax(0,1fr);gap:1rem}.card{padding:1.5rem;border-radius:1.5rem;min-height:15rem}
  .card h3{font-size:1.55rem}.card p{font-size:.85rem}.card-bottom{gap:.5rem}
  .project-image{height:20rem}
  .section-head{gap:.6rem}h2{font-size:1.45rem}.section-head p{font-size:.72rem;max-width:12rem}
  section,.journal{margin-bottom:4rem}.log{padding:1.7rem 0}.log h3{font-size:1.05rem}.log-body{font-size:.9rem}
  .about-section{grid-template-columns:1fr;padding:1.7rem;gap:1.2rem;border-radius:1.5rem}.about p:first-child{font-size:1.45rem}
  .project-header{padding:2rem 0 1.5rem;margin-bottom:1rem}.project-header .tagline{font-size:1rem}
}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important}}
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
        f'<span class="count">일지 {c["log_count"]}</span>' if c.get("log_count") else '<span class="count">프로젝트 보기</span>'
    )
    preview = (
        f'<img class="project-image" src="{base}assets/projects/{html.escape(c["image"], quote=True)}" '
        f'alt="{html.escape(c["image_alt"], quote=True)}" loading="lazy" decoding="async">'
        if c.get("image") else ""
    )
    return (
        f'<a class="card" href="{base}project/{c["slug"]}.html">'
        f'<div class="card-meta"><span class="card-label">PROJECT</span>{badge}</div>'
        f'<h3>{html.escape(c["name"])}</h3>{summary}{preview}'
        f'<div class="card-bottom">{tools}{count}</div></a>'
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
    date_label = (
        f'<span class="log-date">{e["date"].year}년 · 작업 정리</span>'
        if e.get("date_display") == "year"
        else f'<time class="log-date" datetime="{e["date"].isoformat()}">{fmt_date(e["date"])}</time>'
    )
    return (
        f'<article class="log"><div class="log-head">'
        f'{date_label}'
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
    cards = "".join(card_html(c) for c in projects)
    cards += '<article class="card empty"><span class="empty-mark" aria-hidden="true">＋</span><span>빈 칸</span><p>다음에 만들 것은 아직 비워둡니다.</p></article>'
    entries = "".join(log_html(e) for e in logs) or "<p>아직 없습니다.</p>"
    body = f"""<header class="hero">
<span class="spark" aria-hidden="true">✦</span><span class="spark" aria-hidden="true">✦</span>
<p class="eyebrow">A SMALL LAB FOR EVERYDAY IDEAS</p>
<h1>작은 불편을,<span>쓸모 있는 도구로.</span></h1>
<p class="tagline">혼자 만든 앱과 자동화를 모았습니다.<br>만들면서 달라진 것들도 조금씩 남깁니다.</p>
<div class="hero-foot">{len(projects)}개의 프로젝트, 계속 만드는 중</div>
</header>
<main id="main">
<section id="work"><div class="section-head"><h2>만든 것</h2><p>일상에서 출발한 작은 프로젝트들</p></div><div class="cards">{cards}</div></section>
<section id="log" class="journal"><div class="section-head"><h2>작업 일지</h2><p>만들고, 고치고, 기록합니다.</p></div>{entries}</section>
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
{summary}{tools}
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
