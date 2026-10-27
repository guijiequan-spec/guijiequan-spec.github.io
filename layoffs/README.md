# 国内裁员动态日报 · 在线看板

每日汇总国内企业裁员、组织瘦身、关厂停产、用工政策调整的公开信息看板。全部条目附原始来源链接，可逐条回溯。

## 在线地址

- 主站（WorkBuddy 托管）：由 `发布为应用` 生成，见仓库顶部说明或部署记录
- GitHub Pages（如需自建）：`https://<用户名>.github.io/layoffs/`

## 目录结构

```
index.html              看板页面
assets/style.css        样式
assets/app.js           渲染与筛选逻辑
data/layoffs.json       主数据（每日更新）
data/layoffs.js         同源静态副本，供 file:// 与 Pages 兜底加载
data/auto_feed.json     RSS 自动抓取的待核实线索（可选）
scripts/update.py       合并当日新增条目 -> 重新生成 JSON/JS
scripts/fetch_feed.py   抓取 RSS 关键词线索 -> auto_feed.json
config/sources.json     RSS 源与关键词配置
```

## 每日更新流程

1. 检索当日公开信息（财经/行业媒体、公众号、公司公告、监管备案），按字段整理成 `new_items.json`
2. 合并入库：

```bash
python scripts/update.py --input new_items.json
```

3. 重新发布（WorkBuddy 托管站）或 `git push`（GitHub Pages，1–2 分钟生效）

## 字段规范

| 字段 | 说明 |
| --- | --- |
| id | 唯一标识，建议 `公司拼音-日期` |
| date | 事件日期 `YYYY-MM-DD` |
| region | `国内` / `中国区` / `中国台湾` / `境外` |
| status | `confirmed`（官方确认）/ `rumor`（媒体消息、传闻）/ `denied`（公司否认） |
| scale_num | 明确披露人数填数字，未披露填 `null`，不做估算 |
| source_url | 原始报道链接，必填 |

## 收录与可信度口径

- 优先中国大陆境内事件，全球性裁员标注为「境外」，默认不参与统计，可手动勾选查看
- 传闻类条目必须同时记录企业回应状态；被否认的保留为舆情记录
- 涉及人数严格区分全球 / 中国区 / 单一工厂口径，不做跨口径加总误导
