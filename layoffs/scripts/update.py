# -*- coding: utf-8 -*-
"""
每日更新脚本：把当日新增条目合并进 data/layoffs.json，并同步生成 data/layoffs.js。

用法：
    python scripts/update.py --input new_items.json          # 合并新条目（数组）
    python scripts/update.py --input new_items.json --insights insights.json
    python scripts/update.py --touch                          # 只刷新 updated_at

new_items.json 结构（数组，字段同 data/layoffs.json 的 items）：
[
  {
    "id": "company-20261027",            # 唯一标识，必填
    "date": "2026-10-27",                # 事件日期 YYYY-MM-DD，必填
    "company": "某某公司",
    "region": "国内",                     # 国内 / 中国区 / 中国台湾 / 境外
    "industry": "汽车",
    "kind": "结构性裁员",
    "scale_text": "约 1000 人",
    "scale_num": 1000,                    # 无明确人数填 null
    "status": "confirmed",               # confirmed / rumor / denied
    "summary": "事实描述，带关键数据",
    "source_name": "媒体名",
    "source_url": "https://...",
    "note": "可选备注"
  }
]
"""
import argparse
import io
import json
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data', 'layoffs.json')
DATA_JS = os.path.join(ROOT, 'data', 'layoffs.js')


def load(path):
    with io.open(path, encoding='utf-8') as f:
        return json.load(f)


def save(data):
    with io.open(DATA, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    with io.open(DATA_JS, 'w', encoding='utf-8') as f:
        f.write('window.__LAYOFFS__ = ')
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write(';\n')


VERIFY_BY_STATUS = {
    'confirmed': '已核实',
    'rumor': '未核实',
    'denied': '已核实（企业否认）',
}
PLACEHOLDER = ('未披露', '未公开', '不适用', '未量化')


def _blank(v):
    if v is None:
        return True
    s = str(v).strip()
    return (not s) or any(s == p or s.startswith(p) for p in PLACEHOLDER)


def normalize(it):
    """补齐 2026 全年版新增字段，保证前端渲染与缺失标注一致。"""
    for k in ('scope', 'dept', 'reason', 'pct_text'):
        it.setdefault(k, None)
    it.setdefault('pct_num', None)
    it.setdefault('aggregate', False)
    if not it.get('verify'):
        it['verify'] = VERIFY_BY_STATUS.get(it.get('status'), '未核实')
    miss = []
    if not it.get('scale_num'):
        miss.append('人数')
    if _blank(it.get('pct_text')):
        miss.append('占比')
    if _blank(it.get('dept')):
        miss.append('部门')
    if _blank(it.get('scope')):
        miss.append('地区')
    if _blank(it.get('reason')):
        miss.append('原因')
    it['missing'] = miss
    return it


def merge(data, new_items, insights=None):
    items = data.get('items', [])
    index = {it.get('id'): i for i, it in enumerate(items)}
    added, updated = 0, 0
    for it in new_items:
        if not it.get('id') or not it.get('date'):
            print('[skip] 缺少 id 或 date：%s' % it.get('company'))
            continue
        it = normalize(it)
        if it['id'] in index:
            items[index[it['id']]] = it
            updated += 1
        else:
            items.append(it)
            added += 1
    items.sort(key=lambda x: x.get('date', ''), reverse=True)
    data['items'] = items
    if insights:
        data['insights'] = insights
    data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    return added, updated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', help='当日新增条目 JSON 文件路径')
    ap.add_argument('--insights', help='趋势观察 JSON 文件路径（可选）')
    ap.add_argument('--touch', action='store_true', help='仅刷新 updated_at')
    args = ap.parse_args()

    data = load(DATA)
    before = len(data.get('items', []))

    if args.touch or not args.input:
        data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        added = updated = 0
    else:
        new_items = load(args.input)
        insights = load(args.insights) if args.insights else None
        added, updated = merge(data, new_items, insights)

    save(data)
    print('条目：%d → %d（新增 %d，更新 %d）' % (before, len(data['items']), added, updated))
    print('更新时间：%s' % data['updated_at'])


if __name__ == '__main__':
    main()
