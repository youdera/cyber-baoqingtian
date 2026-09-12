# GitHub 公告采集框架与现成路由研究

核验日期：2026-09-12。本轮读取项目交接后，检查了三个上游仓库的真实代码、许可证、当前提交与官方文档。未安装框架、运行上游爬虫、访问人员名单详情或下载附件；下列路由属于待官网复核的技术线索，不是本项目新增接入数。

**建议先利用 RSSHub 找栏目和接口线索，继续完善本项目的目录适配器。changedetection.io 可供提醒功能参考，Scrapy 可供后续调度重构参考。没有一个框架能把登记的六十多个门户自动变成全国完整公示索引。**

## 对本项目的价值

| 项目 | 可直接补充的东西 | 仍需自己完成 | 当前建议 |
| --- | --- | --- | --- |
| [RSSHub](https://github.com/DIYgod/RSSHub) | 已存在的浙江、山西、四川、重庆等考试栏目地址和请求参数线索 | 官网现状复核、HTTPS支持、历史分页、日期、稳定原文链接、元数据范围、失败状态 | 优先研究具体路由，独立实现所需适配 |
| [changedetection.io](https://github.com/dgtlmoon/changedetection.io) | 页面变化监测、选择器、定时和通知管理 | 官方来源目录、招录类型与年度识别、分页、公告级别的去重 | 暂不引入第二套常驻服务 |
| [Scrapy](https://github.com/scrapy/scrapy) | 请求调度、限速、重试、断点续跑、抓取统计 | 每个站点的栏目/接口适配、公告持久化和提醒规则 | 来源规模扩大后再评估迁移成本 |

## 1. RSSHub：确实有相关路由，价值主要是发现栏目

在核验提交 [0a4ecdb](https://github.com/DIYgod/RSSHub/commit/0a4ecdb02390fb047bb675a1764e1dedbf5cf9bc) 中，找到并逐一阅读以下代码。它们属于一个项目的不同路由；不是六个全国数据库。

| 代码与路由 | 代码实际访问范围 | 可借鉴线索和缺口 |
| --- | --- | --- |
| [浙江公务员](https://github.com/DIYgod/RSSHub/blob/0a4ecdb02390fb047bb675a1764e1dedbf5cf9bc/lib/routes/gov/zhejiang/gwy.ts) `/gov/zhejiang/gwy/:category?/:column?` | 分类 `5` 为录用公示专栏；`column` 区分浙江省、各市和省级单位；向 `gwy.zjks.gov.cn/zjgwy/website/queryMore.htm` 提交栏目参数 | 最贴近需求。默认最多50条，代码没有历史翻页；根地址为HTTP；详情使用POST，所有条目的 `link` 指向同一个详情入口，另以 `guid` 区分。不能只抄链接作为唯一ID，更不能当作完整历史 |
| [山西人社厅](https://github.com/DIYgod/RSSHub/blob/0a4ecdb02390fb047bb675a1764e1dedbf5cf9bc/lib/routes/gov/shanxi/rst.ts) `/gov/shanxi/rst/:category` | `rst.shanxi.gov.cn/rsks/` 下公务员、事业单位等五类栏目 | 给出了准确栏目路径与列表选择器；原实现使用HTTP、读取详情正文，未提供发布日期字段和历史翻页 |
| [四川人事考试](https://github.com/DIYgod/RSSHub/blob/0a4ecdb02390fb047bb675a1764e1dedbf5cf9bc/lib/routes/scpta/news.ts) `/scpta/news/:category` | `https://www.scpta.com.cn/front/News/List/`，`56` 公务员、`67` 事业单位 | 列表可提取标题、日期、链接。代码不翻历史页；详情失败时仍返回条目并写入“公告内容获取失败”。本项目可独立验证目录，无需执行详情读取 |
| [重庆人事考试通知](https://github.com/DIYgod/RSSHub/blob/0a4ecdb02390fb047bb675a1764e1dedbf5cf9bc/lib/routes/gov/chongqing/rsks.ts) `/gov/chongqing/rsks` | `https://rlsbj.cq.gov.cn/ywzl/rsks/tzgg_109374/` | HTTPS政府栏目，列表含标题日期。原实现再进详情校准日期、提取正文；未实现历史分页 |
| [德阳人事考试](https://github.com/DIYgod/RSSHub/blob/0a4ecdb02390fb047bb675a1764e1dedbf5cf9bc/lib/routes/dykszx/news.ts) `/dykszx/news/:newsType?` | `https://www.dykszx.cn` 首页不同模块；`gwy`、`sydw` 分别为公务员和事业单位 | 地市补充线索。采用依赖页面位置的选择器，日期从详情读取；首页模块不等于整个栏目历史 |
| [中国人事考试网](https://github.com/DIYgod/RSSHub/blob/0a4ecdb02390fb047bb675a1764e1dedbf5cf9bc/lib/routes/cpta/handler.ts) `/cpta/:category` | `notice` 通知、`performance` 成绩公布 | 代码排序后仅保留最新10条、读取详情正文，且标记反爬风险。它不是中央公务员拟录用公示总库，优先级低于上面直接相关栏目 |

所有上述路由都有详情正文读取，浙江路由还提取附件地址。**不应直接执行这些路由并将RSS全文入库。** 本项目只需要目录标题、日期、来源和原文链接；可以把代码中的地址作为线索，再根据官方当前列表独立实现。第三方提供的 `.com.cn`/`.cn` 站点还需要从官方部门页面核实主办关系。

RSSHub 的缓存支持内存、Redis和HTTP后端，`tryGet` 按键缓存且有过期时间。这能减少重复请求，但不是本项目需要的跨采集轮次公告版本档案或历史完整性判断。RSS消费者仍要处理同一公告重复出现、撤销、更正及抓取失败；现成路由也不能把“返回零条”自动解释为“没有公示”。[缓存代码](https://github.com/DIYgod/RSSHub/blob/0a4ecdb02390fb047bb675a1764e1dedbf5cf9bc/lib/utils/cache/index.ts)

部署涉及 Node 应用；官方 Compose 示例同时配置 Redis 与浏览器服务，并给出健康检查。上述六组路由并不要求浏览器。定时拉取RSS和面向本项目关注条件的推送仍需外层调度，使用RSS不会自然获得历年归档。[Compose配置](https://github.com/DIYgod/RSSHub/blob/0a4ecdb02390fb047bb675a1764e1dedbf5cf9bc/docker-compose.yml)

许可证必须按当前版本核实：该提交的 [LICENSE](https://github.com/DIYgod/RSSHub/blob/0a4ecdb02390fb047bb675a1764e1dedbf5cf9bc/LICENSE) 已是 **AGPL-3.0**，网上仍有旧资料写MIT。本轮没有复制路由源码；不能把上游代码复制后仅贴本项目MIT声明。若以后实际集成代码，应记录具体提交、保留版权并按该版本许可证处理。

## 2. changedetection.io：提醒成熟，来源仍要自己登记

它能定时检查指定页面，用CSS/XPath/JSON选择器缩小监测区域，通过HTTP抓取或浏览器渲染动态页面，比较变化并发送通知；还提供可管理监测项的API。这适合已知栏目更新提醒，但不会自动发现全国各级招聘站点，也不提供考试年度、地区、历史分页模型。[官方说明](https://github.com/dgtlmoon/changedetection.io/blob/5842e7a15849b819da2146309fcc703e55522193/README.md)、[API](https://changedetection.io/docs/api_v1/)

状态接口有 `last_checked`、`last_changed`、`last_error`，可区分最后检查与最后变化；后台也记录空内容或浏览器步骤失败。这值得本项目借鉴。页面变化去重与“同一公告换位置、置顶、跨栏目转发”的公告去重仍是两回事。[搜索状态API代码](https://github.com/dgtlmoon/changedetection.io/blob/5842e7a15849b819da2146309fcc703e55522193/changedetectionio/api/Search.py)、[worker代码](https://github.com/dgtlmoon/changedetection.io/blob/5842e7a15849b819da2146309fcc703e55522193/changedetectionio/worker.py)

自托管需常驻进程和持久化数据目录；浏览器模式另外占用浏览器服务资源。若直接监测正文，其快照和差异存储范围会超过本项目当前的元数据要求。因此更适合独立运维工具或设计参考，暂不替代已经工作的本地闹钟与GitHub定时采集。[Compose配置](https://github.com/dgtlmoon/changedetection.io/blob/5842e7a15849b819da2146309fcc703e55522193/docker-compose.yml)

核验提交 [5842e7a](https://github.com/dgtlmoon/changedetection.io/commit/5842e7a15849b819da2146309fcc703e55522193)，许可证 **Apache-2.0**。[LICENSE](https://github.com/dgtlmoon/changedetection.io/blob/5842e7a15849b819da2146309fcc703e55522193/LICENSE)

## 3. Scrapy：适合扩大采集调度，不负责替你找齐来源

Scrapy 是Python抓取框架。`AutoThrottle` 按响应延迟调整速度，并遵守并发和最小延迟限制；错误响应不会让限速加快。`JOBDIR` 可保存请求队列、已访问请求和爬虫状态，便于同一任务中断后恢复。[AutoThrottle](https://docs.scrapy.org/en/latest/topics/autothrottle.html)、[断点续跑](https://docs.scrapy.org/en/latest/topics/jobs.html)

请求指纹去重只能避免重复调度请求，不等于公告业务去重。对每日重新检查的目录，不能不加区分地沿用“已经访问”状态；公告仍需按稳定来源ID和规范化链接保存，并比较标题、日期等元数据变化。超时、重试和HTTP错误可以交给中间件，但“官网只有首页”“达到官网页数上限”“年度未知”等 `partial` 原因还要由适配器生成。[中间件](https://docs.scrapy.org/en/latest/topics/downloader-middleware.html)

动态目录优先找网站实际公开的数据请求；必要时才评估浏览器渲染。官方文档也提醒直接绕开Scrapy下载器调用浏览器，会失去部分中间件和去重行为。迁移必须重新验证固定域名、TLS、robots、访问限制、停止按钮和状态报告，不能只换一个库名。[动态内容处理](https://docs.scrapy.org/en/latest/topics/dynamic-content.html)

Scrapy本身不是定时任务托管服务，仍可由现有GitHub Actions按天启动。它与项目同属Python，适合日后把按域名并发、增量与历史回补队列分离；当前来源缺口主要是栏目适配，立即整体迁移未必更快。核验提交 [a527168](https://github.com/scrapy/scrapy/commit/a527168ad0888a54b665a6d00a45c720a956e1c0)，许可证 **BSD-3-Clause**。[LICENSE](https://github.com/scrapy/scrapy/blob/a527168ad0888a54b665a6d00a45c720a956e1c0/LICENSE)

## 维护情况与落地顺序

GitHub元数据显示三个项目均未归档；本次读取的最新默认分支提交日期分别为：RSSHub 2026-09-11、changedetection.io 2026-09-11、Scrapy 2026-09-10。日期只能证明主项目有近期维护，不能证明每个地方路由仍然有效；本轮未实测第三方RSS服务。

建议顺序是：先复核四川与重庆的HTTPS目录；再复核山西栏目HTTPS情况及日期；浙江另做POST目录和可分享原文链接研究；德阳作为地市补充。每项完成目录样本、后续页、边界日期和失败场景验证后，才计入“已接入”。中国人事考试网应先确认类别与招录目标相关，再决定是否纳入。

这份研究不修改现有64个登记入口和6个已接入栏目的统计。框架可以省去部分工程工作，来源完整性仍应逐栏目给出证据，不能以GitHub项目宣传或站点数量代替验收。
