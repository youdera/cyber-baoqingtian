# 东中部官方公告目录接入验收

本轮于 2026-09-12 启动，2026-09-13 完成目录抽样和适配器验收。负责上海、江苏、浙江、安徽、福建、江西、山东、河南、湖北、湖南 10 个地区，新增 **15 个已实现并通过目录样本检查的固定来源**。是否已经出现在应用，以主任务注册和整体验收结果为准。

这里的“地区有来源”只表示该地区至少有一个局部官方栏目，不能表述为该省或全国覆盖完整。浙江补的是湖州公务员目录，江西补的是景德镇市政府目录。官方目录本身没有发布、已经撤下、仅放在其他单位网站、直接链接附件的内容仍可能缺失。

## 真实目录样本

全部通过项目现有 `notices.Fetcher` 读取。仅请求官方目录及用于确认分页的公开脚本，没有进入公告详情、下载人员名单、修改数据库或运行全历史采集。共解析 **33 个目录样本**；表中数量是采纳的网页公告链接数，不是人数、附件数或完整年份总量。

| 来源 ID / 官方目录 | 首页 | 第二页 | 末页或本地上限样本 | 已知边界 |
| --- | ---: | ---: | --- | --- |
| `shanghai_hires` · [上海拟聘人员公示](https://rsj.sh.gov.cn/tnprygs_17409/index.html) | 16 | 16 | 第 120 页 16 条 | 标称 322 页，第 322、321 页均 404；最多读取 120 页并保留 partial |
| `shanghai_jobs` · [上海招聘公告](https://rsj.sh.gov.cn/tzpgg_17408/index.html) | 16 | 16 | 第 120 页 16 条 | 官网标称 224 页，本地上限 120 页；后续页面保留未查完 |
| `jiangsu_jobs` · [江苏省属事业单位招聘](https://jshrss.jiangsu.gov.cn/col/col78506/index.html) | 60 | 同一 HTML 包含前 3 个显示页 | 动态后续未请求 | 官网声明 2742 条，仅读取内嵌 60 条；部分标题原本已截短 |
| `anhui_jobs` · [安徽省直事业单位招聘](https://hrss.ah.gov.cn/zxzx/ztzl/ahssydwgkzp/index.html) | 20 | 20 | 第 66 页 2 条 | 官网声明 1302 条；末页日期 2012-04-10，仅证明当前目录分页终点 |
| `anhui_college` · [安徽省属高校招聘](https://hrss.ah.gov.cn/zxzx/ztzl/ahsszsydwgkzpzl/ssgxgkzp/index.html) | 20 | 20 | 第 29 页 6 条 | 官网声明 566 条；末页日期 2020-04-13 至 2020-04-20 |
| `anhui_city` · [安徽市县招聘](https://hrss.ah.gov.cn/zxzx/ztzl/ahsszsydwgkzpzl/gsszgxgkzp/index.html) | 5 | 20 | 第 5 页 0 条同域链接 | 首页 20 项中的 15 项外域，末页 17 项全外域，均明确排除；`history=False`，保留 partial 及市县原站尚未接入的原因 |
| `hubei_gwy_notice` · [湖北公务员重要通知](https://rst.hubei.gov.cn/hbrsksw/zlplks/jglyks/hbsgwyks/zytz/) | 15 | 13 | 第 17 页 0 条网页链接 | 第二页含 2 个名单附件，末页 10 项全部附件；不索引附件，`history=False` 并保留 partial |
| `hubei_jobs` · [湖北省直招聘公告](https://rst.hubei.gov.cn/bmdt/ztzl/ywzl/hbsszsydwgkzp/zpgg/) | 15 | 15 | 第 55 页 4 条 | 官网声明 814 条，末页日期 2015-08-18 至 2016-04-12 |
| `hubei_hires` · [湖北省直招聘人员公示](https://rst.hubei.gov.cn/bmdt/ztzl/ywzl/hbsszsydwgkzp/zprygs/) | 3 | 无第二页 | 官网声明 1 页 3 条 | 最新 2025-10-27；不能据此声称 2026 年没有公示 |
| `zhejiang_huzhou_hires` · [湖州公务员录用公示](https://zzb.huzhou.gov.cn/gbgz/gwykl/lygs/index.html) | 46 | 当前 HTML 内嵌 5 个显示页 | 10/10/10/10/6 条内嵌分组 | 仅湖州；更大目录的远程分页没有实现，保留 partial |
| `henan_hr_recruit` · [河南人社厅招考录用](https://hrss.henan.gov.cn/zwgk/xxgk/yfygkdqtxx/zkly/) | 24 | 未接通 | `pageDec` 声明 51 页 | 分页脚本在 `file.henan.gov.cn`，未跨域请求；仅本厅及所属单位 |
| `shandong_jobs` · [山东省属事业单位公开招聘服务平台](https://hrss.shandong.gov.cn/channels/ch00232/) | 470 | HTML 内已含全部 24 个显示页 | 内嵌末项日期 2024-01-15 | 当前声明总数与 470 个 `pagedContent` 节点一致；不是全省所有公告 |
| `fujian_forest_recruit` · [福建林业局考录招聘](https://lyj.fj.gov.cn/zwgk/rsgl/klzp/) | 15 | HTML 内嵌 24 项、3 个显示页 | 过滤 9 项非招录人事信息 | 仅林业局，动态后续与筛选未接通，保留 partial |
| `hunan_jobs` · [湖南事业单位招聘](https://rst.hunan.gov.cn/rst/xxgk/zpzl/sydwzp/) | 20 | 20 | 第 25 页 20 条 | 当前官网声明 500 条；末页 2024-04-26 至 2024-05-14，非历史完整保证 |
| `jiangxi_jingdezhen_recruit` · [景德镇市政府招考录用](https://www.jdz.gov.cn/zwgk/fdzdgknr/rsxx/zkly/) | 20 | 19 | 第 7 页 16 条 | 当前声明 136 项，第二页 1 项外域排除；`history=False`，保留 partial；仅景德镇及该栏目转载，不能替代江西省级来源 |

所有采纳的 33 个样本中的网页链接均取得了目录明确提供的完整发布日期。发布日期来自目录日期节点或湖州 `daytime` 字段，不从 URL、标题中的考试年份或当前时间反推。例如上海一个 URL 日期段为 2026-09-07，但目录日期为 2026-09-08，保存目录的 2026-09-08。

山东存在“特聘人员公示名单”标题；它们已经作为网页公告链接保留。阶段分类由核心统一负责，不能把某个阶段分类计数为零解释为官网不存在公示。

## 分页依据与实现

- 上海读取 `.pagination("setPage", current, total)`，页码从 1 开始，第二页是 `index_2.html`。第 120 页仍返回下一页链接，使引擎报告上限导致的 partial。拟聘来源另有 `history=False` 和具体的末页 404 提示。
- 安徽读取 `Ls.pagination` 的公开配置，分页是同域 GET：`/content/column/6791573?pageIndex=2`；高校与市县分别使用 `6791574`、`6791575`。参数来自官网脚本，不需要 POST。源码校验请求栏目 ID、返回页码和总页数。
- 湖北与景德镇读取 `createPageHTML(total, current, "index", "shtml", "black2", count)`，页码从 0 开始，第二页是 `index_1.shtml`。只有目录中明确标为附件或外域链接的条目可以过滤后返回空列表，模板缺失或普通条目异常会报错。
- 安徽市县、湖北公务员重要通知、景德镇招考录用均设置 `history=False`，并在 `history_note` 保留上述排除原因。它们仍按已验证的分页继续采集；到达当前目录终点或遇到全部条目被明确排除的有效末页后，结果仍为 partial，不能据此声称附件、站外公告或地方独立来源已经覆盖。
- 湖南使用另一种 `createPageHTML('paging', total, current, 'index', 'html', count)`。已检查[官网分页脚本](https://rst.hunan.gov.cn/rst/xhtml/js/page.js)，页码从 1 开始，第二页是 `index_2.html`，末页为 `index_25.html`。
- 江苏只解析 `script[type=text/xml]` 中的 `<record><![CDATA[...]]></record>`，没有执行脚本，也没有请求动态历史接口。核验 HTML 条目数量与记录数量一致。
- 湖州从 `dataList` 读取现有目录分组，使用 JSON 解析，不执行任意 JavaScript。[官网脚本](https://zzb.huzhou.gov.cn/ui/boshan/ajaxpage/ajaxpage.js)确认前 10 个显示页直接从内嵌数据取值，更多页面才请求远程接口；本轮没有实现后者。
- 山东页面提供 `totalCount/perSize/startPage/endPage/logicTotalPage`，前端对已存在节点进行切片。适配器核对全部参数和节点数量；如果未来分批加载或缺少部分目录，报错而不是返回“已完成”。
- 福建只使用 `ul.gl-ul` 中已渲染的目录，排除无数据的 Avalon 模板，以及非招录人事信息。
- 部分官网目录仍输出本域 HTTP 原文地址。只在固定同域、标准端口、已识别的网页路径中将链接升级为 HTTPS；不会发出 HTTP 请求或访问正文。外域、附件、查询式链接与异常路径不作为已核验网页公告索引。

## 失败与局部替代

| 地址/阶段 | 实测结果 | 本轮处理 |
| --- | --- | --- |
| `rst.hunan.gov.cn/robots.txt` | 初始 `BAD_ECPOINT` | 主任务为现有 Fetcher 加入限定错误触发的 P-256 兼容重试后，首页、第二页、末页恢复；`transport_mode=p256_compat`，证书验证未关闭 |
| `rst.jiangxi.gov.cn/robots.txt` | `UNSAFE_LEGACY_RENEGOTIATION_DISABLED` | 保留省人社厅失败；未启用旧式 TLS 重协商，改用独立景德镇市政府目录作局部补充 |
| `www.jxpta.com/robots.txt` | `UNSAFE_LEGACY_RENEGOTIATION_DISABLED` | 江西人事考试网同样未启用；官方身份可由[景德镇转载的江西省考公告](https://www.jdz.gov.cn/zwgk/fdzdgknr/rsxx/zkly/t1077272.shtml)确认 |
| [南昌事业单位目录](https://rsj.nc.gov.cn/ncsrsj/sydwzp/bmxxgk_list.shtml) | Fetcher 报“重定向离开已核验官方来源” | 未跨域跟随，保留失败，首跳阶段由主任务另行诊断 |
| `rsj.sh.gov.cn/tnprygs_17409/index_322.html` 与 `index_321.html` | 目录 HTTP 404 | 首页、第二页、第 120 页正常；这是官网分页发布不一致，不归为整体网络失败 |
| [浙江人社拟聘公示](https://rlsbt.zj.gov.cn/col/col1229743684/index.html) | 上轮 HTML 可读，但动态脚本跳转外域被阻止 | 本轮不绕过；湖州为独立官方来源，不是对原站限制的绕过 |
| [浙江公务员系统](https://gwy.zjks.gov.cn/zjgwy/website/init.htm) | 上轮 robots 请求 `SSLEOFError` | 本轮未重新测试，不当作当前成功来源 |

同一地区出现一个可用栏目，不会清除其他栏目原有失败。江西省级栏目和南昌候选仍失败；景德镇仅填补局部来源。湖南的恢复经过实际同一 Fetcher 验证，未将其他 TLS 错误自动归为同一种原因。

## 逐地区交接与测试

`data/expansion-east-inventory.json` 是包含 10 个地区对象的 JSON 数组；每个对象含 `region`、`official_columns`、`remaining_gaps`。新来源状态为 `adapter_ready`，现有福建来源标为 `existing_enabled`，失败项保留具体 `phase/failed_url/reason`。样本只含 URL、数量、日期范围、下一页和状态，没有人员信息。此文件及 `data/expansion-east/` 下临时目录样本不得提交 Git。

新增代码文件为 `wuzhong/expansion_east.py`，导出 `EXPANSION_EAST_SOURCES` 与 `parse_expansion_east(html, source, url)`。主任务需要把 15 个来源及适配函数注册到现有来源集合和目录适配映射中；本文件没有修改 `notices.py`、Fetcher、数据库、主交接或共享来源目录。

已通过 `python -m unittest tests.test_expansion_east -q` 的 **24 项脱敏测试**，覆盖：首页与分页终点、两种页码起点、请求与返回页码不一致、达到上限保留下一页、跨年发布日期、未知日期、短标题、空标题、缺少普通条目链接、动态模板与分隔线、附件/外域过滤、同域异常 URL、JSON 字段白名单、声明总数不一致和模板变化报错。测试不联网，夹具仅含虚构公告元数据。

本轮没有入库、触发关注、发送提醒、发布 GitHub 或运行全历史扫描。最终端到端注册、浏览器验收及发布由主任务统一完成。
