# -*- coding: utf-8 -*-
"""
裁员人数分层汇总
================
把 layoffs.json 里带 scale_num 的条目按「能否加总」分层，输出 data/summary.json。

为什么不直接 sum：105 条里混着四种完全不同的东西，硬加会得到一个假数。

  direct      单次事件的裁员人数，口径「某主体某一轮裁掉多少人」→ 可相加
  net12       近 12 个月内的人数净减（含主动离职）→ 与 direct 同属 2026 年度，可相加
  netmulti    跨 2—5 年的人数净减（如隆基两年减 4.2 万、万科五年减 1.25 万）
              → 时间跨度超出统计年度，绝不能折进年度数字
  plan        计划值 / 上限值 / 目标值 / 分年度执行，尚未完成 → 只能单列
  industry    行业汇总口径，内部已包含上面个别公司 → 只能单列
  global      区域标中国区但人数是全球口径（亚马逊 1.6 万）→ 不进「中国境内」合计
"""
import json
import io
import os
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

# ---- 人工判定表（宁可少算，不可错算）----
LAYER = {
    # 行业汇总：内部已含个别公司，单列不叠加
    "pv-industry-20260930": "industry",
    "broker-industry-20260603": "industry",
    "bank-industry-20260430": "industry",
    # 近 12 个月净减：与 2026 年度可比
    "li-auto-20261015": "net12",      # 2025-06 → 2026-06，整 12 个月
    "nio-20261009": "net12",          # 一年减员 1.06 万
    "xiaomi-20260331": "net12",       # 2025 年末 → 2026-06，半年
    # 跨多年净减：跨度 2—5 年，只作量级参照
    "longi-20260930": "netmulti",     # 2023 末 → 2026-09，约 2.7 年
    "dongfang-risheng-20260930": "netmulti",  # 两年
    "yonyou-20260630": "netmulti",    # 2023 末 → 2026-06，两年半
    "vanke-20260831": "netmulti",     # 2020 末 → 2025 末，五年，不含 2026
    # 计划值 / 上限值 / 目标值
    "vw-group-20260626": "plan",
    "zf-20260630": "plan",
    "dazhong-jituan-20261025": "plan",
    "porsche-20261008": "plan",
    "porsche-20260705": "plan",
    "bmw-20261022": "plan",
    "takeda-20260513": "plan",
    "gsk-20261014": "plan",
    "gsk-rd-20260202": "plan",
    "wangwang-20260831": "plan",
    "ebay-global-20261022": "plan",
    # 区域标中国区、实为全球口径
    "amazon-cn-20260126": "global",
}

POLICY_IDS = {"miit-ai-employment-20261023"}
CN_REGIONS = ("国内", "中国区", "中国香港", "中国台湾")
ESTIMATE_SKIP_INDUSTRY = {"政策 / 人力资源"}

# 细分行业 49 个太碎，推算时归到 9 个大类，否则样本永远不够
INDUSTRY_GROUP = {
    "社交": "互联网科技", "互联网 / 电商": "互联网科技", "游戏": "互联网科技",
    "软件": "互联网科技", "科技 / 软件": "互联网科技", "支付": "互联网科技",
    "云安全": "互联网科技", "人工智能": "互联网科技", "本地生活": "互联网科技",
    "电商": "互联网科技", "电商 / 物流": "互联网科技", "电商 / 云计算": "互联网科技",
    "流媒体 / 文娱": "互联网科技", "机器人 / 具身智能": "互联网科技",
    "半导体": "电子半导体", "面板 / 半导体": "电子半导体", "消费电子": "电子半导体",
    "消费电子 / 汽车": "电子半导体", "通信设备": "电子半导体",
    "线路板制造": "电子半导体", "电子代工": "电子半导体", "电子制造": "电子半导体",
    "辐照加工 / 检测服务": "电子半导体",
    "汽车": "汽车", "汽车零部件": "汽车",
    "医药": "医药健康", "生物医药": "医药健康", "医疗器械": "医药健康",
    "光伏": "新能源", "储能 / 新能源": "新能源", "石油 / 能源": "新能源",
    "房地产": "地产建筑", "建筑 / 基建": "地产建筑", "建筑设计": "地产建筑",
    "银行": "金融", "证券": "金融", "金融": "金融",
    "零售 / 商超": "消费零售", "零售": "消费零售", "零售百货": "消费零售",
    "服饰零售": "消费零售", "奢侈品零售": "消费零售", "餐饮": "消费零售",
    "食品": "消费零售", "食品 / 调味品": "消费零售",
    "轮胎制造": "工业制造",
    "航空": "交通运输", "教育培训": "其他",
}


def load():
    with io.open(os.path.join(DATA, "layoffs.json"), encoding="utf-8") as f:
        return json.load(f)


def layer_of(it):
    if it.get("id") in POLICY_IDS:
        return "policy"
    if it.get("id") in LAYER:
        return LAYER[it["id"]]
    if it.get("aggregate"):
        return "industry"
    return "direct"


def fmt(n):
    return "{:,}".format(int(n))


def median(vals):
    v = sorted(vals)
    n = len(v)
    if not n:
        return None
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def build():
    d = load()
    items = d["items"]
    for it in items:
        it["_layer"] = layer_of(it)

    def pick(layers, cn=None, confirmed=False):
        out = []
        for it in items:
            if it["_layer"] not in layers or not it.get("scale_num"):
                continue
            if cn is True and it["region"] not in CN_REGIONS:
                continue
            if cn is False and it["region"] in CN_REGIONS:
                continue
            if confirmed and it.get("status") != "confirmed":
                continue
            out.append(it)
        return out

    def total(lst):
        return sum(int(x["scale_num"]) for x in lst)

    # 中国境内
    dir_cn = pick({"direct"}, cn=True, confirmed=True)
    dir_cn_r = pick({"direct"}, cn=True)
    n12_cn = pick({"net12"}, cn=True)
    nmul_cn = pick({"netmulti"}, cn=True)
    plan_cn = pick({"plan"}, cn=True)
    ind_cn = pick({"industry"}, cn=True)
    # 境外
    dir_out = pick({"direct"}, cn=False, confirmed=True)
    n12_out = pick({"net12"}, cn=False)
    nmul_out = pick({"netmulti"}, cn=False)
    plan_out = pick({"plan"}, cn=False)
    ind_out = pick({"industry"}, cn=False)
    amazon = [x for x in items if x["_layer"] == "global" and x.get("scale_num")]

    S_dir_cn, S_n12_cn = total(dir_cn), total(n12_cn)
    S_core_cn = S_dir_cn + S_n12_cn
    S_nmul_cn, S_plan_cn, S_ind_cn = total(nmul_cn), total(plan_cn), total(ind_cn)

    S_dir_out, S_n12_out, S_nmul_out = total(dir_out), total(n12_out), total(nmul_out)
    S_core_ww = S_core_cn + S_dir_out + S_n12_out
    S_ind_ww = S_ind_cn + total(ind_out)
    S_amazon = total(amazon)

    # ---------- 未披露条目的区间推算 ----------
    # 锚点分两级：先只用中国境内同大类样本；样本不足才借境外样本放大，
    # 并在依据里注明「含境外样本」，避免拿苹果 60 人去锚定一家国内工厂。
    by_ind_cn = {}
    by_ind_all = {}
    for it in items:
        if it["_layer"] in ("direct", "net12") and it.get("scale_num"):
            g = INDUSTRY_GROUP.get(it["industry"], it["industry"])
            n = int(it["scale_num"])
            by_ind_all.setdefault(g, []).append(n)
            if it["region"] in CN_REGIONS:
                by_ind_cn.setdefault(g, []).append(n)

    MIN_SAMPLES = 4

    miss = [it for it in items
            if not it.get("scale_num")
            and it["_layer"] in ("direct", "net12", "netmulti", "plan")
            and it["region"] in CN_REGIONS
            and it["industry"] not in ESTIMATE_SKIP_INDUSTRY]
    est_rows = []
    est_low = est_high = est_mid = 0
    n_est = 0
    for it in miss:
        g = INDUSTRY_GROUP.get(it["industry"], it["industry"])
        pool = by_ind_cn.get(g) or []
        scope = "国内"
        if len(pool) < MIN_SAMPLES:
            pool_all = by_ind_all.get(g) or []
            if len(pool_all) >= MIN_SAMPLES:
                pool, scope = pool_all, "含境外"
        if len(pool) < MIN_SAMPLES:
            est_rows.append({"id": it["id"], "company": it["company"],
                             "industry": it["industry"], "n": len(pool),
                             "low": None, "high": None,
                             "reason": "「%s」已披露样本仅 %d 个（少于 %d），样本不足，不估算"
                                       % (g, len(pool), MIN_SAMPLES)})
            continue
        m = median(pool)
        # 保守假设：真正的大额裁员基本藏不住，未披露人数的多为中小规模事件，
        # 因此区间取中位数的 0.4—1.2 倍，而非对称外扩。
        lo, hi = int(m * 0.4), int(m * 1.2)
        lo, hi = max(lo, 1), max(hi, 2)
        est_low += lo
        est_high += hi
        est_mid += (lo + hi) // 2
        n_est += 1
        est_rows.append({"id": it["id"], "company": it["company"],
                         "industry": it["industry"], "group": g, "n": len(pool),
                         "low": lo, "high": hi,
                         "reason": "%s「%s」%d 个已披露样本，中位数 %s 人，取 0.4—1.2 倍"
                                   % (scope, g, len(pool), fmt(m))})
    est_rows.sort(key=lambda x: -(x.get("high") or 0))

    tiers = [
        {
            "key": "cn_core", "tone": "main",
            "label": "2026 年中国境内 · 可确认减员",
            "num": S_core_cn, "count": len(dir_cn) + len(n12_cn),
            "desc": "由「单次裁员公告」%s 人（%d 起）与「近 12 个月财报净减」%s 人（%d 起）相加。"
                    "这是本年度中国境内唯一可被公开信息直接支撑的减员规模。"
                    % (fmt(S_dir_cn), len(dir_cn), fmt(S_n12_cn), len(n12_cn)),
        },
        {
            "key": "cn_direct", "tone": "sub",
            "label": "　└ 其中：单次裁员公告",
            "num": S_dir_cn, "count": len(dir_cn),
            "desc": "公司公告 / 官方回应 / WARN 类申报直接披露的裁员人数。中国大陆 %d 起、"
                    "外企中国区 %d 起、港澳台 %d 起。"
                    % (len([x for x in dir_cn if x["region"] == "国内"]),
                       len([x for x in dir_cn if x["region"] == "中国区"]),
                       len([x for x in dir_cn if x["region"] in ("中国香港", "中国台湾")])),
        },
        {
            "key": "cn_net12", "tone": "sub",
            "label": "　└ 其中：近 12 个月财报净减",
            "num": S_n12_cn, "count": len(n12_cn),
            "desc": "由财报/年报员工总数对比得出，含主动离职与自然流失，是「裁了多少」的上界。"
                    "国内大厂普遍不发裁员公告，规模只体现在这里。",
        },
        {
            "key": "cn_plan", "tone": "sub",
            "label": "另：目标值 / 上限值（尚在执行）",
            "num": S_plan_cn, "count": len(plan_cn),
            "desc": "公司公开的目标数或上限数，尚未执行完毕，与已发生人数分列。",
        },
        {
            "key": "cn_netmulti", "tone": "warn",
            "label": "另：跨多年净减（2—5 年，不并入年度）",
            "num": S_nmul_cn, "count": len(nmul_cn),
            "desc": "隆基两年减 4.2 万（2023 末→2026.9）、万科五年减 1.25 万（2020→2025，不含 2026）、"
                    "东方日升两年减 9,712、用友两年半减 7,451。时间跨度超出统计年度，只能作量级参照。",
        },
        {
            "key": "global_core", "tone": "sub",
            "label": "全球口径 · 可确认减员",
            "num": S_core_ww, "count": len(dir_cn) + len(n12_cn) + len(dir_out) + len(n12_out),
            "desc": "把境外主体一并计入（境外单次裁员 %s 人 / %d 起）。亚马逊 %s 人因是全球口径"
                    "（中国区未单列），未计入中国境内合计，但含在本行内。"
                    % (fmt(S_dir_out + S_n12_out), len(dir_out) + len(n12_out), fmt(S_amazon)),
        },
        {
            "key": "industry_ref", "tone": "ref",
            "label": "行业汇总口径（仅供参考，禁止相加）",
            "num": S_ind_ww, "count": len(ind_cn) + len(ind_out),
            "desc": "光伏 139 家两年多累计减 22.0 万、证券经纪人半年减 5,621 等统计口径。"
                    "内部已包含隆基、东方日升等个别公司，与上面任何数字相加都会重复。",
        },
    ]

    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source_updated_at": d.get("updated_at"),
        "basis": {
            "period": "%s 至 %s" % (d["coverage"]["from"], d["coverage"]["to"]),
            "items_total": len(items),
            "items_with_num": sum(1 for x in items if x.get("scale_num")),
            "items_no_num": sum(1 for x in items if not x.get("scale_num")),
        },
        "tiers": tiers,
        "layers": {
            "direct_cn": [x["id"] for x in dir_cn],
            "net12_cn": [x["id"] for x in n12_cn],
            "netmulti_cn": [x["id"] for x in nmul_cn],
            "plan_cn": [x["id"] for x in plan_cn],
            "industry_cn": [x["id"] for x in ind_cn],
            "global_basis": [x["id"] for x in amazon],
            "rumor_cn": [x["id"] for x in dir_cn_r if x.get("status") != "confirmed"],
        },
        # 榜单只收中国境内，排除行业汇总（22 万的汇总会把所有个体压成一条线）
        "top_cn": [
            {"company": x["company"], "date": x["date"], "num": x["scale_num"],
             "region": x["region"], "layer": x["_layer"]}
            for x in sorted([y for y in items if y.get("scale_num")
                             and y["_layer"] not in ("industry", "global")
                             and y["region"] in CN_REGIONS],
                            key=lambda y: -int(y["scale_num"]))[:12]
        ],
        "top_global": [
            {"company": x["company"], "date": x["date"], "num": x["scale_num"],
             "region": x["region"], "layer": x["_layer"]}
            for x in sorted([y for y in items if y.get("scale_num")
                             and y["_layer"] != "industry"
                             and y["region"] not in CN_REGIONS],
                            key=lambda y: -int(y["scale_num"]))[:5]
        ],
        "estimate": {
            "miss_count": len(miss),
            "est_count": n_est,
            "base": S_core_cn,
            "low": S_core_cn + est_low,
            "mid": S_core_cn + est_mid,
            "high": S_core_cn + est_high,
            "added_low": est_low,
            "added_mid": est_mid,
            "added_high": est_high,
            "method": "以「2026 年中国境内可确认减员 %s 人」为底，对 %d 条未披露人数的条目做推算，"
                      "其中 %d 条有足够行业样本（同大类已披露 ≥4 个）。区间取大类中位数的 0.4—1.2 倍："
                      "真正的大额裁员基本藏不住，未披露人数的多为中小规模事件，故不作对称分布假设。"
                      "这是推算值，不是事实值；样本不足的条目一律不估，因此结果偏保守。"
                      % (fmt(S_core_cn), len(miss), n_est),
            "rows": est_rows,
        },
    }

    out = os.path.join(DATA, "summary.json")
    with io.open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with io.open(os.path.join(DATA, "summary.js"), "w", encoding="utf-8") as f:
        f.write("window.__SUMMARY__ = ")
        json.dump(summary, f, ensure_ascii=False, indent=1)
        f.write(";\n")

    print("=" * 66)
    for t in tiers:
        print("%-34s %11s  (%d 起)" % (t["label"], fmt(t["num"]), t["count"]))
    print("-" * 66)
    print("%-34s %11s ~ %s" % ("叠加未披露条目后的推算区间",
                               fmt(summary["estimate"]["low"]),
                               fmt(summary["estimate"]["high"])))
    print("写入", out)
    return summary


if __name__ == "__main__":
    build()
