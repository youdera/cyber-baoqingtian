# GitHub 政府公告爬虫研究

核验日期：2026-09-12。范围：广东政府目录模板、招录信息采集的既有实现。已读取当前 `HANDOFF.md`、最新日志与项目约定。用户补充“看一下别的 github 有没有”后，本轮转为代码研究，未继续逐站官网探测，未运行第三方程序、下载公告详情或人员附件，也未改动正式来源与采集程序。

## 结论

有可参考的现成代码。对广东来源扩展，最有价值的是 **gkmlpt 目录模板**：从官网公开配置识别站点和栏目，再按栏目读取分页 JSON。它可以减少多个广东站点重复写解析器的工作，但不能把几十个人社门户直接视为几十个已接入招录栏目。本轮没有找到能直接替换本项目、覆盖全国全部录聘公示并保证历史完整的成品。

深查了三个仓库。三个仓库当前树均未找到许可证文件，GitHub 仓库 API 的 `license` 均为 `null`；本轮只研究接口和结构，不引入其源码。最新提交日期来自提交记录，不能把 GitHub 的 `updated_at` 当作最近维护时间。

| 仓库 | 最近提交（UTC） | 实际采集对象 | 与本项目的关系 |
|---|---|---|---|
| [hulelan/china-governance](https://github.com/hulelan/china-governance) | 2026-09-09 | 政策与政府文档；包含广东多站 gkmlpt 适配 | 最值得参考目录发现与解析机制；必须重新核验招录栏目和访问条件 |
| [gangchenxi/Crawler-written-test](https://github.com/gangchenxi/Crawler-written-test) | 2024-06-09 | 广东省政府政策目录 | 较小的 gkmlpt JSON 读取示例，不是招录爬虫 |
| [dpc761218914/ShiYeDanWei](https://github.com/dpc761218914/ShiYeDanWei) | 2017-09-14 | 第三方事业编网站的江西招聘信息 | 可参考定时更新流程，不提供广东/全国官方来源适配 |

## 1. china-governance：最有价值的模板线索

已核验 [README](https://github.com/hulelan/china-governance/blob/e7aa3cf6f1fec4f6db99899ecb213bddcc6ce5dd/README.md)、[gkmlpt.py](https://github.com/hulelan/china-governance/blob/e7aa3cf6f1fec4f6db99899ecb213bddcc6ce5dd/crawlers/gkmlpt.py)、[trs.py](https://github.com/hulelan/china-governance/blob/e7aa3cf6f1fec4f6db99899ecb213bddcc6ce5dd/crawlers/trs.py) 和 [base.py](https://github.com/hulelan/china-governance/blob/e7aa3cf6f1fec4f6db99899ecb213bddcc6ce5dd/crawlers/base.py)。

- `discover_site()` 从 `/gkmlpt/index` 中的 `window._CONFIG` 提取 `SID` 和 `TREE`。栏目树包括栏目名称、ID、子栏目和跳转项；代码跳过有 `jump_url` 的节点。
- `crawl_category()` 请求 `/gkmlpt/api/all/{栏目ID}?page={页码}&sid={站点ID}`，从 `articles` 读取条目，并参考 `classify.post_count`。配置中包括广东省人社厅和深圳人社局，也包含广东多个市政府门户。
- 存在 `--metadata-only` 模式；默认流程仍读取正文和保存原始 HTML。目录 JSON 自身也带有较多字段，若本项目适配，应仅保留当前允许的公告元数据。
- `trs.py` 中有 `<record><![CDATA[...]]></record>` 列表解析，以及跟随公开 `<nextgroup>` 翻页链接的示例。**“TRS”是该仓库命名，不能据此认定目标网站实际使用的 CMS 品牌。** 适配应按真实响应格式区分，而非按文件名猜测。
- 这两条目录路径的代码不依赖 OCR 或浏览器执行；项目整体另有 AI 分类和全文分析能力，这些不是我们当前采集所需功能。

不能直接照搬的部分：

1. `base.py` 两种 SSL context 都关闭证书及主机名验证；与本项目 TLS 约定不符。配置还包含大量 HTTP 地址。我们仍需通过现有 HTTPS `Fetcher` 核验，每站遇访问限制就记录失败。
2. 范围默认包括全部叶子栏目和正文，不是限定的招录目录。需要人工审核并固定招录栏目 ID、来源归属和类型，防止把政策、新闻当作招录公示。
3. `crawl_category()` 遇请求错误会退出并返回已有条目；`sync_site()` 随后把旧库中但本次列表缺失的 ID 记作 `deleted`。本项目不能在部分采集或失败时据此判断官网撤稿。
4. 该仓库文档及代码自己记录了一些站点失败、历史窗口和翻页问题。其“覆盖数量”和历史搜索描述是上游作者的报告，本轮未复测，不能成为我们宣称接入成功或完整覆盖的依据。

仓库状态证据：[最新提交](https://github.com/hulelan/china-governance/commit/e7aa3cf6f1fec4f6db99899ecb213bddcc6ce5dd)、[仓库元数据](https://api.github.com/repos/hulelan/china-governance)、[完整文件树](https://api.github.com/repos/hulelan/china-governance/git/trees/e7aa3cf6f1fec4f6db99899ecb213bddcc6ce5dd?recursive=1)。

## 2. Crawler-written-test：简短的广东政策目录示例

[main.py](https://github.com/gangchenxi/Crawler-written-test/blob/008f155bccf7fc4df2a4b4301afdb65d2d621148/main.py) 固定读取广东省政府 `gkmlpt/api/all/5`，页码写死为 1 至 49，提取标题、发布日期、发布机构及原文 URL，随后读取正文和附件链接。它使用 `urllib`、BeautifulSoup 和 SQLite，没有浏览器或 OCR 依赖。

可参考 JSON 字段映射；不能据固定 49 页认定完整，也不能直接把政策栏目 ID 用在人社招录栏目上。代码未实现本项目需要的 robots、固定域名校验和按来源保留 partial 原因；数据库写入使用字符串拼接，亦不适合复用。

[Inquire.py](https://github.com/gangchenxi/Crawler-written-test/blob/008f155bccf7fc4df2a4b4301afdb65d2d621148/Inquire.py) 查询的是已入库的发布日期，未提供独立考试年度。它把结束日拼为 `00:00:00`，本项目“包含结束月最后一日”的现有语义应保持不变。

仓库状态证据：[最新提交](https://github.com/gangchenxi/Crawler-written-test/commit/008f155bccf7fc4df2a4b4301afdb65d2d621148)、[元数据](https://api.github.com/repos/gangchenxi/Crawler-written-test)、[文件树](https://api.github.com/repos/gangchenxi/Crawler-written-test/git/trees/008f155bccf7fc4df2a4b4301afdb65d2d621148?recursive=1)。没有下载其中的数据库文件。

## 3. ShiYeDanWei：第三方江西招聘聚合的旧示例

[app.js](https://github.com/dpc761218914/ShiYeDanWei/blob/66d1e34352b5255fb8e4d7b150e0b4402df0d103/app.js) 每小时第 40 分钟调度，固定抓取第三方 `shiyebian.net` 的 11 个江西城市首页。[采集代码](https://github.com/dpc761218914/ShiYeDanWei/blob/66d1e34352b5255fb8e4d7b150e0b4402df0d103/config/ShiYeDanWeiOnePage.js) 使用 superagent、cheerio 和 MongoDB；提取列表后逐篇抓正文，并以发布时间判断重复。没有浏览器或 OCR 路径，也未实现历史列表翻页。

“定时拉取—去重—提供查询接口”的结构与我们的方向相近，但数据并非直接来自官方，发布时间去重会混淆同一时刻发布的多条公告，也不足以识别公告修改。当前项目已有定时、URL 去重和版本提醒机制，采用这个旧程序不会补齐剩余官方入口。[package.json](https://github.com/dpc761218914/ShiYeDanWei/blob/66d1e34352b5255fb8e4d7b150e0b4402df0d103/package.json) 还未声明 app.js 使用的 `node-schedule` 与 `moment`，不能视为无需修复即可运行的方案。

仓库状态证据：[最新提交](https://github.com/dpc761218914/ShiYeDanWei/commit/66d1e34352b5255fb8e4d7b150e0b4402df0d103)、[元数据](https://api.github.com/repos/dpc761218914/ShiYeDanWei)、[文件树](https://api.github.com/repos/dpc761218914/ShiYeDanWei/git/trees/66d1e34352b5255fb8e4d7b150e0b4402df0d103?recursive=1)。没有下载仓库中的 APK。

## 对本项目的实现建议

1. **先独立实现 gkmlpt 元数据适配器。** 使用现有 Fetcher、robots、TLS 和限速；从经核验的官方目录或公开加载脚本获得栏目配置，只允许固定招录栏目，保存标题、发布日期、官方 URL 等现有字段。
2. **把“模板可识别”和“栏目已接入”分开。** 每个入口记录门户证据、招录栏目、首页/第二页样本、分页终点依据、招录范围及具体缺口。没有目录样本或分页证据就保留待适配/partial。
3. **元数据足够时不引入浏览器、OCR 或 AI。** 列表字段解析采用确定性规则；动态目录优先使用官网公开目录接口。遇验证码或访问限制不换工具绕过。
4. **验证历史与增量的不同问题。** 脱敏测试应覆盖空页但总数未满足、重复页、置顶乱序、栏目迁移、发布日期缺失以及部分失败。增量缺失只能表示本轮未出现，不能自动标记撤销。

这些是基于已读代码形成的工程建议，不是已完成接入的声明。本轮正式可采集来源仍以程序当前 SOURCES 为准。
