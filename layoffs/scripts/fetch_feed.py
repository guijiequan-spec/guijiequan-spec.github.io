# -*- coding: utf-8 -*-
"""
RSS 自动线索抓取：从配置源拉取新闻，按关键词过滤出裁员相关线索，
写入 data/auto_feed.json（待核实区）。仅供人工/AI 二次核实后转入正式条目。

用法：
    python scripts/fetch_feed.py
    python scripts/fetch_feed.py --limit 40
"""
import argparse
import io
import json
import os
import re
import ssl
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = os.path.join(ROOT, 'config', 'sources.json')
OUT = os.path.join(ROOT, 'data', 'auto_feed.json')

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36'
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read()


def parse_items(xml_bytes):
    out = []
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return out
    for node in root.iter():
        tag = node.tag.split('}')[-1]
        if tag not in ('item', 'entry'):
            continue
        title = link = date = ''
        for ch in node:
            t = ch.tag.split('}')[-1]
            if t == 'title':
                title = (ch.text or '').strip()
            elif t == 'link':
                link = (ch.text or ch.attrib.get('href', '')).strip()
            elif t in ('pubDate', 'published', 'updated', 'date'):
                date = (ch.text or '').strip()
        if title:
            out.append({'title': title, 'url': link, 'raw_date': date})
    return out


def norm_date(raw):
    if not raw:
        return datetime.now().strftime('%Y-%m-%d')
    m = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', raw)
    if m:
        return '%s-%02d-%02d' % (m.group(1), int(m.group(2)), int(m.group(3)))
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(raw).strftime('%Y-%m-%d')
    except Exception:
        return datetime.now().strftime('%Y-%m-%d')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=60)
    args = ap.parse_args()

    cfg = json.load(io.open(SOURCES, encoding='utf-8'))
    kws = cfg.get('keywords', [])
    hits, errors = [], []

    for src in cfg.get('sources', []):
        try:
            xml = fetch(src['url'])
            for it in parse_items(xml)[:60]:
                title = it['title']
                if any(k in title for k in kws):
                    hits.append({
                        'date': norm_date(it['raw_date']),
                        'title': title,
                        'url': it['url'],
                        'source': src['name']
                    })
        except Exception as e:
            errors.append('%s: %s' % (src.get('name'), e))

    # 去重（按标题）+ 只保留 30 天内
    seen, uniq = set(), []
    cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    for h in sorted(hits, key=lambda x: x['date'], reverse=True):
        if h['title'] in seen or h['date'] < cutoff:
            continue
        seen.add(h['title'])
        uniq.append(h)

    old = []
    if os.path.exists(OUT):
        try:
            old = json.load(io.open(OUT, encoding='utf-8')).get('items', [])
        except Exception:
            old = []
    merged = (uniq + old)[:args.limit]

    json.dump({'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M'), 'items': merged},
              io.open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    print('命中线索 %d 条，去重后写入 %d 条' % (len(uniq), len(merged)))
    for e in errors:
        print('[源失败] ' + e, file=sys.stderr)


if __name__ == '__main__':
    main()
