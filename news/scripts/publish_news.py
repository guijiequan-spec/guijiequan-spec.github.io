#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
新闻情报中心发布器。

扫描各定时任务的产出目录，把 md / docx 转成静态文章页，
重建 data/index.json，再增量推送到 GitHub Pages 的 news/ 目录。

用法：
  python scripts/publish_news.py              # 全量重建 + 推送
  python scripts/publish_news.py --no-push    # 只重建，不推送
  python scripts/publish_news.py --only hr    # 只处理某个频道

推荐用带 python-docx 的托管解释器跑（行业新闻日报是 docx）：
  C:\\Users\\quang\\.workbuddy\\binaries\\python\\envs\\default\\Scripts\\python.exe
"""

import argparse
import datetime as dt
import html
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # news-hub/
sys.path.insert(0, str(HERE))

import md2html                           # noqa: E402

SITE_NAME = "新闻情报中心"
SITE_SUB = "商业 · HR · 招聘舆情 · 行业 · 活动 | 每日自动更新"

CHANNELS = [
    {
        "id": "business",
        "name": "商业情报",
        "tab": "商业情报",
        "color": "#d9432f",
        "freq": "每日 08:00",
        "desc": "全球商业头条、权威期刊与智库观点、国内财经深度、商业模式创新",
        "dir": r"C:\Users\quang\WorkBuddy\2026-06-05-14-30-14",
        "pattern": "每日全球商业情报_*.md",
        "kind": "md",
        "max_posts": 40,
    },
    {
        "id": "recruit",
        "name": "招聘舆情",
        "tab": "招聘舆情",
        "color": "#c2185b",
        "freq": "每日 08:30",
        "desc": "招聘平台与用工市场舆情监测，含影响评估与来源链接",
        "dir": r"C:\Users\quang\WorkBuddy\20260408154152",
        "pattern": "招聘舆情日报_*.md",
        "kind": "md",
        "max_posts": 40,
    },
    {
        "id": "hr",
        "name": "HR 情报",
        "tab": "HR 情报",
        "color": "#2f6fd0",
        "freq": "每日 10:00",
        "desc": "SHRM / WEF / HBR 等权威机构的 HR 理论与实践最新内容",
        "dir": r"C:\Users\quang\WorkBuddy\automation-2026-08-14-17-00-54",
        "pattern": "HR前沿情报摘要_*.md",
        "kind": "md",
        "max_posts": 40,
    },
    {
        "id": "industry",
        "name": "行业新闻",
        "tab": "行业新闻",
        "color": "#2f9e6d",
        "freq": "每日 10:00",
        "desc": "医疗、具身智能、商务服务、新能源四行业动态与政策",
        "dir": r"E:\菜鸟无忧\行业新闻日报",
        "pattern": "行业新闻日报_*.docx",
        "kind": "docx",
        "max_posts": 30,
    },
    {
        "id": "event",
        "name": "活动周报",
        "tab": "活动周报",
        "color": "#8a5cd1",
        "freq": "每周一 08:00",
        "desc": "行业大会、赛事、HR 论坛等活动的报名与筹备节点",
        "dir": r"C:\Users\quang\WorkBuddy\2026-06-10-18-20-14",
        "pattern": "活动情报周报_*.md",
        "kind": "md",
        "max_posts": 20,
    },
]

# 摘要候选段落里要跳过的前缀（都是报告开头的元信息）
META_PREFIX = re.compile(
    r"^(报告日期|报告时间|数据覆盖|编制说明|监测窗口|信息来源|自动采集|"
    r"服务[:：]|说明[:：]|周期[:：]|本期|更新|生成时间|整理[:：]|来源[:：])"
)
TITLE_TAIL = [
    re.compile(r"\s*[|｜].*$"),                            # 竖线后的副标题/日期
    re.compile(r"\s*[·・]\s*\d{4}[-年]?\d{1,2}.*$"),       # · 2026-10-26（周一）
    re.compile(r"[_\s]+\d{4}[-]?\d{2}[-]?\d{2}.*$"),       # _2026-10-27
    re.compile(r"\d{4}-\d{2}-\d{2}.*$"),                   # 2026-10-27（下划线已被清掉）
    re.compile(r"\s*[（(]周[一二三四五六日][)）]\s*$"),
]


DATE_RE = re.compile(r"(\d{4})-?(\d{2})-?(\d{2})")

ARTICLE_TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} · {channel}</title>
<meta name="description" content="{excerpt}">
<link rel="stylesheet" href="../../assets/style.css">
</head>
<body class="article-page">
<header class="artbar">
  <div class="wrap artbar-in">
    <a class="back" href="../../index.html">← 返回情报中心</a>
    <div class="artmeta">
      <span class="chip-c" style="--c:{color}">{channel}</span>
      <span class="areport">{report}</span>
      <span class="adate">{date}</span>
    </div>
  </div>
</header>
<main class="wrap artmain">
  <article class="article">
    <div class="artbody">
{body}
    </div>
    <nav class="artnav">
      {nav}
    </nav>
  </article>
</main>
<footer class="foot">
  <div class="wrap">
    <p>本文由定时任务自动采集生成，来源链接已在正文标注。版权归原媒体所有。</p>
    <p><a href="../../index.html">新闻情报中心</a> · 数据每日自动更新</p>
  </div>
</footer>
</body>
</html>
"""


# ---------------------------------------------------------------- docx 解析
def docx_to_md(path):
    """把 docx 里的段落与表格按原顺序转成 markdown 文本。"""
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(str(path))
    out = []
    first_text = True
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            p = Paragraph(child, doc)
            txt = (p.text or "").strip()
            if not txt:
                continue
            style = (p.style.name or "").lower()
            m = re.match(r"heading\s*(\d)", style)
            if m:
                out.append("#" * min(int(m.group(1)) + 1, 6) + " " + txt)
            elif style.startswith("title"):
                out.append("# " + txt)
            elif first_text and len(txt) < 40:
                # 首段短文本通常是文档标题（这些日报没用 Title 样式）
                out.append("# " + txt)
            elif re.match(r"^[一二三四五六七八九十]+、", txt) and len(txt) < 40:
                out.append("## " + txt)
            else:
                out.append(txt)
            first_text = False
        elif child.tag == qn("w:tbl"):
            t = Table(child, doc)
            rows = []
            for r in t.rows:
                cells = [c.text.replace("\n", " ").strip() for c in r.cells]
                if any(cells):
                    rows.append(cells)
            if len(rows) >= 2:
                width = max(len(r) for r in rows)
                rows = [r + [""] * (width - len(r)) for r in rows]
                out.append("| " + " | ".join(rows[0]) + " |")
                out.append("|" + "|".join(["---"] * width) + "|")
                for r in rows[1:]:
                    out.append("| " + " | ".join(r) + " |")
                out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------- 工具
def parse_date(name):
    m = DATE_RE.search(name)
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def load_text(ch):
    p = Path(ch["_path"])
    if ch["kind"] == "docx":
        return docx_to_md(p)
    return p.read_text(encoding="utf-8", errors="ignore")


def headline(md, report_title):
    """
    这些日报的 H1 都是固定报头（「每日全球商业情报」），逐期一样。
    从正文里挖一条真实头条当标题，归档列表才能区分。
    按优先级尝试：### 编号小标题 → 编号列表的加粗引导句 → 编号列表首句 → 表格首行首格。
    """
    lines = [l.strip() for l in md.split("\n")]
    pats = [
        re.compile(r"^#{2,4}\s*(\d+)[.、]\s*(.+)$"),
        re.compile(r"^\d+[.、]\s*\*\*(.+?)\*\*"),
        re.compile(r"^\d+[.、]\s*(.{8,80})$"),
        re.compile(r"^\d{1,2}\s+(.{8,80})$"),      # 「1 诺思兰德…」这类无点号编号
    ]
    for pat in pats:
        for l in lines:
            m = pat.match(l)
            if not m:
                continue
            cand = m.group(m.lastindex)
            cand = re.sub(r"[*_`]", "", cand).strip()
            cand = re.split(r"(?:来源[:：]|｜|\s\|\s)", cand)[0].strip(" 　:：,，。.-—")
            cand = re.sub(r"\s+", " ", cand)
            if 6 <= len(cand) <= 60 and cand != report_title:
                return cand[:46]

    # 活动周报这类以表格为主的：取首个表格的第一行首格
    for i, l in enumerate(lines):
        if l.startswith("|") and i + 2 < len(lines) and re.match(r"^\|[\s:|-]+\|", lines[i + 1]):
            cells = [c.strip() for c in l.strip("|").split("|")]
            if cells and 4 < len(cells[0]) < 60:
                c = re.sub(r"[*_`]", "", cells[0])
                if c not in ("活动名称", "序号", "日期"):
                    return c[:46]
    return report_title


def clean_title(raw, fallback=""):
    """报告 H1 往往是「名称 | 日期」，把日期/副标题/后缀剥掉，日期由页面单独展示。"""
    t = re.sub(r"[*_`]", "", raw or "").strip()
    for pat in TITLE_TAIL:
        t = pat.sub("", t).strip()
    t = re.sub(r"[\s（(【\[·\-—|｜:：]+$", "", t)   # 去掉残留的悬空括号与连接符
    return (t or fallback).strip()[:80]


def pick_excerpt(md, limit=150):
    """跳过开头的元信息段落，取第一段有实质内容的正文做摘要。"""
    blocks = re.split(r"\n\s*\n", md)
    for b in blocks:
        s = b.strip()
        if not s or s.startswith(("#", "|", ">", "---", "```")):
            continue
        s_plain = re.sub(r"[*_`>]", "", s).strip()
        if META_PREFIX.match(s_plain):
            continue
        # 「行业新闻日报 2026-10-27（运行日）」这类重复标题行
        if re.match(r"^.{0,25}?\d{4}[-年]\d{1,2}", s_plain) and len(s_plain) < 90:
            continue
        if len(s_plain) < 30:
            continue
        return md2html.plain(b, limit)
    return md2html.plain(md, limit)


def article_nav(posts, idx, cid):
    """上一篇 / 下一篇（时间轴：旧的在前）"""
    parts = []
    if idx + 1 < len(posts):
        n = posts[idx + 1]
        parts.append('<a class="navi prev" href="%s.html">← 更早：%s %s</a>'
                     % (n["slug"], n["date"], html.escape(n["title"][:28])))
    if idx - 1 >= 0:
        n = posts[idx - 1]
        parts.append('<a class="navi next" href="%s.html">更新：%s %s →</a>'
                     % (n["slug"], n["date"], html.escape(n["title"][:28])))
    if not parts:
        parts.append("<span></span>")
    return "\n      ".join(parts)


def build_channel(ch):
    src = Path(ch["dir"])
    if not src.is_dir():
        return {"id": ch["id"], "name": ch["name"], "tab": ch["tab"],
                "color": ch["color"], "freq": ch["freq"], "desc": ch["desc"],
                "count": 0, "latest": None, "posts": [],
                "warn": "源目录不存在：%s" % ch["dir"]}

    files = []
    for p in sorted(src.glob(ch["pattern"])):
        d = parse_date(p.name)
        if d:
            files.append((d, p))
    files.sort(key=lambda x: x[0], reverse=True)
    files = files[: ch["max_posts"]]

    outdir = ROOT / "posts" / ch["id"]
    outdir.mkdir(parents=True, exist_ok=True)

    posts = []
    for d, p in files:
        try:
            md = load_text({**ch, "_path": str(p)})
        except Exception as e:                                  # noqa: BLE001
            print("  [WARN] 读取失败 %s: %s" % (p.name, e))
            continue
        if not md.strip():
            print("  [WARN] 内容为空，跳过 %s" % p.name)
            continue
        report = clean_title(md2html.first_heading(md, default=p.stem), p.stem)
        title = headline(md, report)
        slug = d.strftime("%Y-%m-%d")
        if any(x["slug"] == slug for x in posts):
            # 同一天存在两版（重新生成过），保留先到的，后来的加后缀
            n = 2
            while any(x["slug"] == "%s-%d" % (slug, n) for x in posts):
                n += 1
            slug = "%s-%d" % (slug, n)
            print("      [INFO] 同日重复：%s → 存为 %s" % (p.name, slug))
        posts.append({
            "slug": slug,
            "date": d.strftime("%Y-%m-%d"),
            "title": title,
            "report": report,
            "md": md,
            "excerpt": pick_excerpt(md),
        })

    for i, post in enumerate(posts):
        body = md2html.convert(post["md"])
        htmlout = ARTICLE_TPL.format(
            title=html.escape(post["title"]),
            channel=html.escape(ch["name"]),
            report=html.escape(post["report"]),
            excerpt=html.escape(post["excerpt"]),
            color=ch["color"],
            date=post["date"],
            body=body,
            nav=article_nav(posts, i, ch["id"]),
        )
        (outdir / (post["slug"] + ".html")).write_text(htmlout, encoding="utf-8")

    listed = [{
        "slug": p["slug"], "date": p["date"], "title": p["title"],
        "report": p["report"], "excerpt": p["excerpt"],
        "url": "posts/%s/%s.html" % (ch["id"], p["slug"]),
    } for p in posts]

    print("  %-8s %-14s %2d 篇%s" % (ch["id"], ch["name"], len(listed),
                                     "" if listed else "  (无产出)"))

    return {
        "id": ch["id"], "name": ch["name"], "tab": ch["tab"],
        "color": ch["color"], "freq": ch["freq"], "desc": ch["desc"],
        "count": len(listed),
        "latest": listed[0] if listed else None,
        "posts": listed,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--only", default=None, help="只处理指定频道 id")
    ap.add_argument("--message", default=None)
    args = ap.parse_args()

    chans = [c for c in CHANNELS if not args.only or c["id"] == args.only]
    if not chans:
        print("[FAIL] 未匹配到频道：%s" % args.only)
        return 2

    print("扫描频道产出…")
    result = [build_channel(c) for c in chans]

    data = {
        "site": SITE_NAME,
        "sub": SITE_SUB,
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": sum(c["count"] for c in result),
        "channels": result,
    }
    (ROOT / "data").mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "index.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("索引已更新：%d 个频道 / %d 篇" % (len(result), data["total"]))

    if args.no_push:
        print("跳过推送（--no-push）")
        return 0

    msg = args.message or ("chore: 新闻情报中心更新 %s" % dt.date.today().isoformat())
    cmd = [sys.executable, str(HERE / "push_github.py"), "--message", msg]
    print("推送到 GitHub Pages…")
    rc = subprocess.call(cmd)
    return rc


if __name__ == "__main__":
    sys.exit(main())
