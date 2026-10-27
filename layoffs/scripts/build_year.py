# -*- coding: utf-8 -*-
"""把 2026 年全年条目合并进看板数据集。

用法：python scripts/build_year.py
"""
import io
import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "layoffs.json")
DATA_JS = os.path.join(ROOT, "data", "layoffs.js")

sys.path.insert(0, os.path.join(ROOT, "scripts"))
from year_2026_items import ITEMS as NEW_ITEMS  # noqa: E402

# 行业/群体汇总条目：计入条目统计，但不与单个企业人数相加
AGGREGATE_IDS = {
    "pv-industry-20260930",
    "broker-industry-20260603",
    "bank-industry-20260430",
}

# 既有 29 条（旧 schema）补齐 涉及地区 / 部门 / 原因 / 占比
ENRICH = {
    "netflix-20261027": dict(
        scope="全球（美国为主）",
        dept="内容制作与电影业务；首席内容官、电影业务负责人",
        reason="第三财季营收增速创三年新低；720 亿美元竞购华纳兄弟探索流媒体资产失利；YouTube 日均观看时长反超",
        pct_text="未披露", pct_num=None),
    "volvo-20261026": dict(
        scope="全球（其中 2000 个岗位在瑞典）",
        dept="间接支出与可变成本相关岗位、行政与支持职能",
        reason="三季度营收 669 亿瑞典克朗（-22.6%）、营业利润由盈转亏；大中华区交付 -40.6%；目标 2027 年底间接支出较 2024 财年降近 25%",
        pct_text="约占员工 6%", pct_num=6),
    "bayerr-china-20261026": dict(
        scope="全国（新设 12 位区域总经理，一人统管一省全品类）",
        dept="可申达、核心产品、女性健康三条产品线；大区经理岗取消",
        reason="三条产品线合并为一个大单元，管理层级由 12 层压至 7—8 层",
        pct_text="未披露", pct_num=None),
    "dispatch-20261026": dict(
        scope="全国（国企、央企）",
        dept="劳务派遣、外包用工",
        reason="用工合规整改：普通企业派遣占比不得超 10%，央国企更严，超标/超岗/假外包真派遣须 2026 年底前整改到位",
        pct_text="普通企业派遣占比上限 10%（政策阈值）", pct_num=None),
    "laoganma-20261026": dict(
        scope="贵州贵阳昌明基地",
        dept="辣椒分拣（拣椒工）",
        reason="网传 AI 视觉质检替代人工；公司否认网传调整规模，但确认 AI 质检已上线",
        pct_text="未披露", pct_num=None),
    "weijing-chuneng-20261026": dict(
        scope="上海总部及部分生产基地",
        dept="销售、生产",
        reason="长期欠薪、部分基地停产、人员解散；公司称「内部统筹处理，暂无对外披露信息」",
        pct_text="未披露", pct_num=None),
    "microsoft-veo-20261026": dict(
        scope="美国、加拿大、印度、英国部分团队",
        dept="Xbox、Windows、Copilot、财务、人力资源、AI 体验；不含数据中心、销售、市场、网络安全、量子计算",
        reason="自愿离职方案（VEO），精简组织并配合 AI 转型",
        pct_text="约 27%（符合申请资格口径，非实际离职比例）", pct_num=27),
    "pfizer-20261026": dict(
        scope="美国密歇根 Portage、北卡 Rocky Mount/Sanford；意大利西西里",
        dept="制造网络（无菌注射剂、生物制剂、基因疗法）",
        reason="按患者需求重新配置产能，后疫情产能过剩",
        pct_text="西西里基地约 60%；Portage 约 150 岗，其余未披露", pct_num=60),
    "zhongjin-fuzhao-20261026": dict(
        scope="公司总部及子公司",
        dept="内部组织机构（全公司）",
        reason="「十五五」战略部署、适配业务板块规模化、提高运营效率",
        pct_text="未披露", pct_num=None),
    "wujing-dongli-20261025": dict(
        scope="江苏南京",
        dept="研发等全部门",
        reason="实控人失联；8 月起停发工资、9 月停缴公积金、10 月停缴社保，全面停工",
        pct_text="未披露", pct_num=None),
    "gaoxin-lingshou-20261025": dict(
        scope="全国（大卖场、中型超市、M 会员店）",
        dept="经营承压门店",
        reason="半年预亏 5—5.5 亿元，推进门店资产组合优化、对承压门店择机退出",
        pct_text="未披露", pct_num=None),
    "dazhong-jituan-20261025": dict(
        scope="德国（大众股份公司 Volkswagen AG 范围）",
        dept="汽车业务、零部件业务、集团职能部门",
        reason="「2030 未来计划」降本，以自愿离职、提前退休等温和方式推进，11 月 24 日启动谈判",
        pct_text="未披露（累计口径见 6 月「最高 10 万」条）", pct_num=None),
    "ebay-cn-20261024": dict(
        scope="中国区（上海办公室）",
        dept="研发与运营",
        reason="全球人员调整，中国为其中一部分；全球比例约 9%",
        pct_text="中国区 80% 属传闻，公司已否认", pct_num=None),
    "autocar-unknown-20261023": dict(
        scope="中国区",
        dept="在编人员（全公司）",
        reason="在华销量持续下滑、营收利润双降；裁员前已完成一轮 10%—15% 降薪",
        pct_text="年内 10% 以上", pct_num=10),
    "guoban-ai-employment-20261023": dict(
        scope="全国",
        dept="全行业（政策文件，非企业行为）",
        reason="建立 AI 应用就业风险评估机制，减缓 AI 应用对就业的替代影响",
        pct_text="不适用", pct_num=None),
    "ebay-global-20261022": dict(
        scope="全球",
        dept="全职能；战略优先赛道招聘不受影响",
        reason="重组，把资源投向增长最快的板块",
        pct_text="约 9%", pct_num=9),
    "top5-realestate-20261022": dict(
        scope="集团总部及城市公司",
        dept="非一线生产类职能部门、营销条线；工程与运营反向补强",
        reason="年初撤区域公司改集团直管城市后，进一步组织瘦身",
        pct_text="未披露", pct_num=None),
    "bmw-20261022": dict(
        scope="全球（主要德国）",
        dept="研发及行政等非生产岗位（白领）",
        reason="降本，2028 年起每年节省约 10 亿欧元；约 4 万员工登录 HR 门户查额度致系统瘫痪",
        pct_text="未披露（约 4 万员工申请）", pct_num=None),
    "qualcomm-20261022": dict(
        scope="未披露",
        dept="未披露",
        reason="智能手机市场走弱（三季度全球出货 -22%）、存储涨价、苹果自研基带；重心转向汽车/IoT/AI 数据中心",
        pct_text="未披露", pct_num=None),
    "zhongyuan-youtian-20261022": dict(
        scope="河南（中原油田）",
        dept="全油田岗位；人力资源池（周转、培训、待岗、病养四个小池）",
        reason="「三定」管理压减岗位、机构撤并、项目结束及落聘；池内薪酬随入池时间梯次降低",
        pct_text="累计压减岗位 40.1%", pct_num=40.1),
    "eyepoint-20261021": dict(
        scope="美国",
        dept="全公司（研发与支持）",
        reason="EYP-1901 第二项关键 III 期 LUCIA 未达主要终点，股价单日 -85.28%，提前终止 wAMD 试验",
        pct_text="约 53%", pct_num=53),
    "crec-20261020": dict(
        scope="全国",
        dept="区域总部、分公司、总部部门",
        reason="建筑央企机构撤并与编制压减；基建投资放缓",
        pct_text="中国铁建总部编制 397→308 人；中国建筑区域总部 12→8 个", pct_num=None),
    "cseoc-20261017": dict(
        scope="中建系多家工程局（全国）",
        dept="项目与职能岗位",
        reason="变相裁员：先降薪再按降薪后基数核算 N+1；以「人才沉淀池」待岗压低成本",
        pct_text="薪资降至原 4—5 成", pct_num=None),
    "muth-wuxi-20261016": dict(
        scope="江苏无锡",
        dept="全厂（汽车后视镜系统）",
        reason="业务下滑、严重亏损；母公司审计出现「持续经营重大疑虑」，可转债违约",
        pct_text="全厂 100%", pct_num=100),
    "lg-huizhou-20261016": dict(
        scope="广东惠州",
        dept="全厂（生产拟转移越南海防）",
        reason="产能转移与成本优化",
        pct_text="未披露", pct_num=None),
    "gsk-20261014": dict(
        scope="比利时",
        dept="研发、生产与支持业务",
        reason="三年重组计划，目标节省 19 亿英镑，简化研发与生产",
        pct_text="未披露", pct_num=None),
    "nio-20261009": dict(
        scope="全国",
        dept="普通员工减 7318 人、中级管理及专业人员减 3264 人",
        reason="组织优化提升人效，全年组织优化费用 7.38 亿元（人均补偿约 7 万元）",
        pct_text="23.2%", pct_num=23.2),
    "porsche-20261008": dict(
        scope="全球（德国为主）",
        dept="管理岗中期目标 -40%、职能岗 -25%",
        reason="中国市场失速（2025 年在华 41938 辆，较 2021 年峰值缩水约 56%）；出售 Rimac 股权、关闭 Cellforce",
        pct_text="约占全球员工 1/5", pct_num=20),
    "innolux-20261008": dict(
        scope="中国台湾（台南 Fab2、Fab5、Fab3）",
        dept="厂区与产线人员",
        reason="厂区缩减、旧世代产线整并；资源转向车用（CarUX）与 FOPLP 封装",
        pct_text="逾一成", pct_num=10),
}

# 仅有月份 / 报道日、无确切公告日的条目：在 missing 中标注「日期」
DATE_APPROX = {
    "netflix-20261027", "bayerr-china-20261026", "li-auto-20261015",
    "hongguang-20260731", "benoy-hk-20260131", "hologic-cn-20260531",
    "xibei-20260115", "lg-yantai-20260131",
}

VERIFY_BY_STATUS = {
    "confirmed": "已核实",
    "rumor": "未核实",
    "denied": "已核实（企业否认）",
}

FIELD_CN = {
    "人数": "人数", "占比": "人数占比", "部门": "涉及部门",
    "地区": "涉及地区", "原因": "原因", "日期": "具体日期",
}


PLACEHOLDER = ("未披露", "未公开", "不适用", "未量化", "无")


def _is_blank(v):
    if v is None:
        return True
    s = str(v).strip()
    if not s:
        return True
    return any(s == p or s.startswith(p) for p in PLACEHOLDER)


def compute_missing(it):
    miss = []
    if not it.get("scale_num"):
        miss.append("人数")
    if _is_blank(it.get("pct_text")) or it.get("pct_text") in ("不适用",):
        miss.append("占比")
    if _is_blank(it.get("dept")):
        miss.append("部门")
    if _is_blank(it.get("scope")):
        miss.append("地区")
    if _is_blank(it.get("reason")):
        miss.append("原因")
    return miss


def bucket(label):
    """把自由文本的缺失项归入统一分类。"""
    s = str(label)
    if "日期" in s:
        return "日期"
    if "占比" in s or "比例" in s:
        return "占比"
    if "人数" in s or "规模" in s:
        return "人数"
    if "公司" in s or "名称" in s:
        return "主体"
    return "其他"


def normalize(it, is_new):
    out = dict(it)
    out.pop("_path", None)
    out.setdefault("scope", None)
    out.setdefault("dept", None)
    out.setdefault("reason", None)
    out.setdefault("pct_text", None)
    out.setdefault("pct_num", None)
    out.setdefault("aggregate", it.get("id") in AGGREGATE_IDS)
    if not out.get("verify"):
        out["verify"] = VERIFY_BY_STATUS.get(out.get("status"), "未核实")
    # 合并脚本给出的缺失清单与自动检测结果，取并集（统一归类去重）
    auto = compute_missing(out)
    manual = [bucket(m) for m in (it.get("missing") or [])]
    merged = []
    for m in auto + manual:
        if m not in merged:
            merged.append(m)
    if out["id"] in DATE_APPROX and "日期" not in merged:
        merged.append("日期")
    out["missing"] = merged
    out["date_approx"] = out["id"] in DATE_APPROX
    return out


def main():
    with io.open(DATA, encoding="utf-8") as f:
        old = json.load(f)

    existing = []
    for it in old.get("items", []):
        it = dict(it)
        if it["id"] in ENRICH:
            it.update(ENRICH[it["id"]])
        existing.append(normalize(it, False))

    known = {it["id"] for it in existing}
    added = []
    for it in NEW_ITEMS:
        if it["id"] in known:
            continue
        added.append(normalize(it, True))

    items = existing + added
    # 去重：同公司 + 同日期 + 同类型 视为重复，保留先到的
    seen = set()
    deduped = []
    for it in items:
        key = (it["company"], it["date"], it["kind"])
        if key in seen:
            print("[dedupe] %s %s %s" % key)
            continue
        seen.add(key)
        deduped.append(it)

    deduped.sort(key=lambda x: (x["date"], x["company"]), reverse=True)

    scope_note = (
        "覆盖 2026-01-01 至 2026-10-27 的公开披露信息。收录口径：中国大陆境内企业裁员 / 组织优化 / 关厂停产 / 用工政策，"
        "外企中国区相关动作单列「中国区」，中国香港、中国台湾单列，全球性裁员以「境外」标注并作为参照、不参与国内统计。"
    )
    sources_note = (
        "来源类型：上市公司财报与公告、董事会公告、地方政府与法院公告、公司官方回应、主流财经媒体（新浪财经、界面新闻、澎湃新闻、"
        "第一财经、21 财经、每经、中国经营网、央广网）、行业媒体（医趋势、数字新能源、芯智讯、国际电子商情）、"
        "行业统计口径（黑鹰光伏、Wind、Layoffs.fyi、Business Insider 裁员追踪）。每条均附原始链接。"
    )

    data = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "period_note": "2026 年 1 月 — 10 月 27 日 · 全年汇总（含 10 月每日增量）",
        "coverage": {
            "from": "2026-01-01",
            "to": "2026-10-27",
            "scope_note": scope_note,
            "sources_note": sources_note,
            "count_note": "「人数」仅汇总企业明确披露的数字，行业汇总条目（光伏、证券经纪人、银行网点）单列，不与单个企业相加；"
                          "期末人数差额、自愿买断资格数、参保人数变化均不计入裁员人数。",
        },
        "items": deduped,
        "insights": INSIGHTS,
    }

    with io.open(DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    with io.open(DATA_JS, "w", encoding="utf-8") as f:
        f.write("window.__LAYOFFS__ = ")
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write(";\n")

    print("existing=%d  added=%d  total=%d" % (len(existing), len(added), len(deduped)))
    from collections import Counter
    print("by month:", dict(sorted(Counter(i["date"][:7] for i in deduped).items())))
    print("by region:", dict(Counter(i["region"] for i in deduped)))
    print("by status:", dict(Counter(i["status"] for i in deduped)))
    print("with headcount:", sum(1 for i in deduped if i["scale_num"]))
    print("with pct:", sum(1 for i in deduped if i["pct_text"]))
    print("with dept:", sum(1 for i in deduped if i["dept"]))
    print("with reason:", sum(1 for i in deduped if i["reason"]))


INSIGHTS = [
    dict(
        title="5—7 月是全年最密集的三个月",
        body="5 月与 7 月单月各收录 12 条与 9 条企业级动作，集中在科技与汽车两大行业：Meta 8000 人、思科 4000 人、"
             "PayPal 4800 人、Cloudflare 1100 人扎堆 5 月；微软 4800 人、英特尔 529 人（代工部门计划 8170—10890 人）落在 7 月。"
             "这一节奏与全球科技业「AI 资本开支创纪录、人力同步收缩」的错位一致。"
    ),
    dict(
        title="「去中层」是全年贯穿的主线",
        body="京东 7 月取消 C4、C5 管理者身份并砍掉两级；腾讯试点「负责人制」取消 L1、L2 职级；亚马逊 1.6 万裁员中逾 78% 落在 L5—L7；"
             "微软、Meta 均以「减少层级」作为官方解释。裁撤对象从一线执行岗上移到信息中转型管理岗，是 2026 年区别于前几轮裁员的显著特征。"
    ),
    dict(
        title="光伏与地产是全年「缩表」幅度最大的两个行业",
        body="隆基两年减 4.2 万人（-56.3%）、东方日升减 9712 人（-63.78%），139 家光伏上市企业累计减员 22.04 万人，全产业链两年亏损超千亿；"
             "房企则以架构调整替代单次裁员——万科开发线五年减 63.45%，头部房企缩编集中在 20%—40%，华发出现「进 1 出 2」冻编规则。"
    ),
    dict(
        title="外企中国区从「节流」走到「实体退场」",
        body="诺基亚关停杭州研发中心（1600 人）并计划把在华业务收缩到只剩售后；LG 烟台模组厂 1429 人全员解散、产能迁越南；"
             "豪洛捷中国区裁掉近一半只剩 90—110 人；锐康迪注销退出、科思莫斯移交权益后销售团队解散。"
             "共同背景是中国区收入占比持续下滑，而非单一年度业绩波动。"
    ),
    dict(
        title="医药中国区被集采与医保谈判重塑",
        body="阿斯利康县域团队约 500 人调整、安达唐 BBU 裁 30%；赛诺菲糖尿病事业部优化；礼来转让阿贝西利后全员分流；"
             "辉瑞、GSK、诺华等则以「成熟产品外包 + 创新药聚焦」同步瘦身。2026 年前 5 个月 12 家头部跨国药企全球裁员已超 1.1 万人。"
    ),
    dict(
        title="三条口径纪律，避免把数字用错",
        body="①「期末人数差额」不等于裁员公告数（小米 3655、用友 7451、理想 3970 均含主动离职）；②「自愿买断资格数」不等于实际离职人数"
             "（微软 6 万人仅具申请资格）；③行业汇总口径（光伏 22 万、证券经纪人 5621、银行柜员 -32%）与单个企业条目分列，不做加总。"
    ),
]

if __name__ == "__main__":
    main()
