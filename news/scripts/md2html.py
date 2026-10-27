#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
极简 Markdown -> HTML 片段转换器。
只覆盖日报类文档实际用到的语法：标题 / 段落 / 无序有序列表 / 表格 /
引用 / 分隔线 / 代码块 / 粗体斜体删除线 / 行内代码 / 链接。

刻意不追求 CommonMark 完备性：不引第三方依赖，行为可预测。
"""

import html
import re


def _inline(s):
    """行内元素。先做 HTML 转义，再还原我们自己的标记。"""
    s = html.escape(s, quote=False)
    # 行内代码优先，避免其内部被当成强调
    parts = re.split(r"(`[^`]+`)", s)
    out = []
    for p in parts:
        if len(p) > 1 and p.startswith("`") and p.endswith("`"):
            out.append("<code>%s</code>" % p[1:-1])
            continue
        p = re.sub(
            r"\[([^\]]+)\]\(([^)\s]+)\)",
            r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
            p,
        )
        p = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", p)
        p = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", p)
        p = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", p)
        out.append(p)
    return "".join(out)


def _cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _aligns(sep):
    res = []
    for c in _cells(sep):
        c = c.strip()
        if c.startswith(":") and c.endswith(":"):
            res.append("center")
        elif c.endswith(":"):
            res.append("right")
        elif c.startswith(":"):
            res.append("left")
        else:
            res.append("")
    return res


def _table(header, rows, aligns):
    def style(i):
        return ' style="text-align:%s"' % aligns[i] if i < len(aligns) and aligns[i] else ""

    h = "".join("<th%s>%s</th>" % (style(i), _inline(c)) for i, c in enumerate(header))
    body = []
    for r in rows:
        tds = "".join("<td%s>%s</td>" % (style(i), _inline(c)) for i, c in enumerate(r))
        body.append("<tr>%s</tr>" % tds)
    return (
        '<div class="tbl-wrap"><table><thead><tr>%s</tr></thead>'
        "<tbody>%s</tbody></table></div>" % (h, "".join(body))
    )


RE_HR = re.compile(r"^\s*([-*_])\s*(\1\s*){2,}$")
RE_UL = re.compile(r"^\s*[-*+]\s+")
RE_OL = re.compile(r"^\s*\d+\.\s+")
RE_HEAD = re.compile(r"^(#{1,6})\s+(.*)$")
RE_CN_HEAD = re.compile(r"^[一二三四五六七八九十]+、")   # 中文报告常见的一级小节


def _is_block_start(line):
    s = line.strip()
    return bool(
        not s
        or RE_HR.match(line)
        or RE_HEAD.match(line)
        or RE_CN_HEAD.match(s)
        or RE_UL.match(line)
        or RE_OL.match(line)
        or s.startswith(("|", ">", "```"))
    )


def convert(md):
    lines = md.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = []
    i, n = 0, len(lines)

    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        # 代码块
        if line.lstrip().startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].lstrip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>%s</code></pre>" % html.escape("\n".join(buf)))
            continue

        # 分隔线
        if RE_HR.match(line):
            out.append("<hr>")
            i += 1
            continue

        # 标题
        m = RE_HEAD.match(line)
        if m:
            lv = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (lv, _inline(m.group(2).strip()), lv))
            i += 1
            continue

        # 独立成行的中文小节标题（docx 转出的报告常见）
        if RE_CN_HEAD.match(line.strip()) and len(line.strip()) < 40:
            out.append("<h3>%s</h3>" % _inline(line.strip()))
            i += 1
            continue

        # 表格
        if line.strip().startswith("|") and i + 1 < n and re.match(
            r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]
        ):
            header = _cells(line)
            aligns = _aligns(lines[i + 1])
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            out.append(_table(header, rows, aligns))
            continue

        # 引用
        if line.lstrip().startswith(">"):
            buf = []
            while i < n and lines[i].lstrip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>%s</blockquote>" % convert("\n".join(buf)))
            continue

        # 无序列表
        if RE_UL.match(line):
            items = []
            while i < n and RE_UL.match(lines[i]):
                item = re.sub(r"^\s*[-*+]\s+", "", lines[i])
                i += 1
                while i < n and lines[i].strip() and not _is_block_start(lines[i]):
                    item += " " + lines[i].strip()
                    i += 1
                items.append("<li>%s</li>" % _inline(item))
            out.append("<ul>%s</ul>" % "".join(items))
            continue

        # 有序列表
        if RE_OL.match(line):
            items = []
            while i < n and RE_OL.match(lines[i]):
                item = re.sub(r"^\s*\d+\.\s+", "", lines[i])
                i += 1
                while i < n and lines[i].strip() and not _is_block_start(lines[i]):
                    item += " " + lines[i].strip()
                    i += 1
                items.append("<li>%s</li>" % _inline(item))
            out.append("<ol>%s</ol>" % "".join(items))
            continue

        # 段落
        buf = []
        while i < n and lines[i].strip() and not _is_block_start(lines[i]):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append("<p>%s</p>" % _inline(" ".join(buf)))
        else:
            i += 1

    return "\n".join(out)


def plain(md, limit=200):
    """提取纯文本摘要，用于列表卡片。"""
    txt = re.sub(r"```.*?```", " ", md, flags=re.S)
    txt = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", txt)
    txt = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", txt)
    txt = re.sub(r"^\s*\|.*$", " ", txt, flags=re.M)      # 表格行
    txt = re.sub(r"^\s{0,3}#{1,6}\s*", "", txt, flags=re.M)  # 标题标记
    txt = re.sub(r"^\s*>\s?", "", txt, flags=re.M)         # 引用标记
    txt = re.sub(r"^\s*[-*+]\s+", "", txt, flags=re.M)     # 列表标记
    txt = re.sub(r"[*_`~]", "", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    if len(txt) > limit:
        txt = txt[:limit].rstrip() + "…"
    return txt


def first_heading(md, default=""):
    for line in md.split("\n"):
        m = RE_HEAD.match(line.strip())
        if m:
            return re.sub(r"[*_`]", "", m.group(2)).strip()
    return default
