# 北方及华南十地区目录接入核验

核验跨北京时间 2026-09-12 至 2026-09-13。新增 14 个固定官方目录适配，涉及北京、天津、河北、内蒙古、辽宁、吉林、黑龙江、广西、海南。河北、内蒙古的集中入口本机访问失败，后续小轮补入各一个可读的独立省级部门栏目；山西沿用上一轮 3 个已验收来源。这里的栏目数、分页数和日期跨度均不能证明省级、全国或全年完整覆盖。

实现位于 `wuzhong/expansion_north.py`，导出 `EXPANSION_NORTH_SOURCES` 和 `parse_expansion_north`，由主应用统一注册；适配器本身不发网络请求。核验使用现有 Fetcher，保留 robots、HTTPS、同域、TLS 证书验证和每主机至少 2 秒间隔。只读取目录和公开分页脚本，不请求公告详情、附件，不下载或检索人员名单。只保存元数据统计，没有保存页面正文。

## 新增目录的实测结果

“样本条数”依次为首页、第二页、末页；第二页恰为末页时只列一次。混合栏目条数是标题过滤后的招录公告数。非混合栏目也可能包含考试流程公告，不能当作录用名单或人数。共完成 33 个目录样本的解析验收，没有执行完整历史入库。

|来源|官方目录及可见分页|样本条数|分页和范围说明|
|---|---|---|---|
|北京人社事业招聘|[栏目](https://rsj.beijing.gov.cn/xxgk/gkzp/)，83 页|12 / 12 / 11|`currentPage/countPage`，零起算 `index_N.html`；末页发布日期 2024-10-14 至 2024-11-13。只覆盖当前招聘目录。|
|天津人社事业招聘|[栏目](https://hrss.tj.gov.cn/ztzl/ztzl1/sydwgkzp/)，6 页|20 / 20 / 12|官网 `pager_options`，已读同域 `images/page.js`；`parseInt('6}')` 按官方 JavaScript 语义取 6。多为汇总公告，不展开其中的单位链接；样本标题大量不含考试年份，保留未知。|
|吉林人社招聘|[栏目](https://hrss.jl.gov.cn/rsrc/sydwrsgl/gkzp/index.html)，35 页|10 / 10 / 9|零起算静态目录，末页发布日期 2013-08-26 至 2013-10-29；不表示各市县及各单位全部公示。|
|吉林人社综合公示|[栏目](https://hrss.jl.gov.cn/gs/index.html)，1 页|0|当前 10 个目录项中 9 个 HTML 链接均非招录，另 1 个附件不读取。搜索缓存曾显示拟聘公示，当前目录已无该条，保留 `history=False` 和明确历史缺口。|
|辽宁公务员公示|[栏目](https://www.lnrsks.com/html/gwy_gongshixinxi/)，4 页|10 / 10 / 2|跟随官方 `119_N.html` 下一页，核对当前页标记和末页禁用标记；发布日期使用独立年/月日元素。|
|辽宁事业单位公示|[栏目](https://www.lnrsks.com/html/sydw_gongshixinxi/)，可见 30 页|10 / 10 / 10|官方 `80_N.html`；可见末页仍满 10 条，日期 2026-03-30 至 2026-04-03，更早历史未证实，`history=False`，仍允许遍历已证实分页。|
|辽宁事业单位招聘|[栏目](https://www.lnrsks.com/html/sydw_zhaopingonggao/)，可见 30 页|10 / 10 / 10|官方 `78_N.html`；末页仍满 10 条，日期 2025-03-06 至 2025-03-21，保留历史缺口。|
|广西 2026 公务员录用公示|[栏目](https://www.gxpta.com.cn/ksxm/gwyzlks/gx2026ndkslygwyxdszt/2026nlygs/)，2 页|15 / 12|官方 `createPageHTML` 零起算分页，同域公开 `assets/lib/page.js` 证实；仅此年度专题。|
|广西 2025 公务员录用公示|[栏目](https://www.gxpta.com.cn/ksxm/gwyzlks/gx2025ndkslygwyxdszt/2025nlygs/)，3 页|15 / 15 / 9|部分 2025 招考公告发布于 2026，发布日期与考试年份分别保存。2022–2024 及 2027 以后专题未接入。|
|广西区直事业单位招聘|[栏目](https://www.gxpta.com.cn/ksxm/sydwzpks/)，34 页|15 / 15 / 5|首页有 2023 置顶公告，不能据此推断历史日期连续；末页普通条目为 2025-05-13 至 2025-05-16。|
|黑龙江人社通知公告|[栏目](https://hrss.hlj.gov.cn/hrss/c111741/list.shtml)，仅静态首页|2|当前首页原始 15 条。公开 `listpage.js` 指向目录查询接口；一次接口结构核验发现 `content/contentHtml` 等正文字段，未保存、读取这些字段值，最终适配器不调用接口，只接静态首页，保留 `partial`。|
|海南政府综合公示|[栏目](https://www.hainan.gov.cn/hainan/0101/list3_1.shtml)，38 页|2 / 3 / 0|公开 `page.js` 确认一基页码 `list3_1_N.shtml`；官网总数 451 为综合栏目所有事项数。末页有效非招录条目不能误报抓取失败。|
|河北省委网信办招录|[栏目](https://www.caheb.gov.cn/xxgk/gwyzl/index.shtml)，仅当前静态页|20|同域 `/system/YYYY/MM/DD/ID.shtml` 官方链接，发布日期 2019-06-11 至 2026-08-24；包含公务员、所属事业单位招聘。未发现可核验分页，`history=False`，仅本部门局部范围。|
|内蒙古医保局招录结果|[栏目](https://ylbzj.nmg.gov.cn/zwgk/zfxxgk/fdzdgknr/rsxx/gwyzkjlyjgxx/)，仅当前两张表|9|招考信息/录用结果表的同域链接，发布日期 2024-06-12 至 2026-09-07；3 个外部考试网链接排除。未核验历史分页，`history=False`，仅医保局局部范围。|

官网检索证据仅用于定位，实时结果来自 Fetcher。辽宁考试网首页导航列出公务员/事业考试及其公示子栏目，省政府发布的[招录公告](https://www.fuxin.gov.cn/content/2026/1038905.html)明确辽宁人事考试网是公示渠道。广西的[公务员专题导航](https://www.gxpta.com.cn/ksxm/gwyzlks/)和[政府站发布的招录公告](https://jyj.gxzf.gov.cn/xxgk/fdzdgknr/rsxx/1224125_hytbght/t27145844.shtml)提供官方网站证据；没有打开该招录公告详情或附件用于采集。

## 尚未接入及本机访问失败

以下都发生在 `robots.txt` 阶段，目标目录未请求。不能把本机一次失败推断为网站永久不可用，也未关闭 TLS 或改用 HTTP。

|地区|官方入口|本机失败|
|---|---|---|
|河北|[省人社厅](https://rst.hebei.gov.cn/)|TLS `SSLV3_ALERT_HANDSHAKE_FAILURE`。|
|河北|[省人事考试网](https://www.hebpta.com.cn/)|robots 返回 HTML 而非规则。|
|内蒙古|[人社厅事业招聘专题](https://rst.nmg.gov.cn/zhuantizhuanlan/ssdwzp/index.html)|robots 返回 HTML 而非规则。|
|内蒙古|[人事考试网](https://www.impta.com.cn/)|TLS `UNEXPECTED_EOF_WHILE_READING`。|
|辽宁|[人社厅公示公告](https://rst.ln.gov.cn/rst/zxzx/gsgg/index.shtml)|robots 返回 HTML；独立考试网目录成功。|
|广西|[人社厅](https://rst.gxzf.gov.cn/)|TLS `TLSV1_UNRECOGNIZED_NAME`；独立考试网成功。|
|海南|[人社厅](https://hrss.hainan.gov.cn/)|HTTP 502；独立省政府目录成功。|

山西沿用人社厅公务员考试、事业单位考试及省直事业单位招聘三个栏目，本轮未重复采集。各市县、各招录单位、已撤下公示仍有缺口。天津、吉林、黑龙江、海南的公务员专门公示栏目仍待补充；综合公示标题过滤也会漏掉标题未说明招录性质的公告。

备用小轮还核验了[河北市场监管局人事目录](https://scjg.hebei.gov.cn/node/915)首页和第二页/末页（官网总数 26，部分旧条目为 HTTP），以及[河北文旅厅招录目录](https://whly.hebei.gov.cn/zwgk/fdzdgknr/gwyzl/)首页；两者没有注册，保留待适配。内蒙古政府[社会保障通知目录](https://www.nmg.gov.cn/zwfw/cjh/shbzly/tzgg_26895/)仍因 robots 返回 HTML 停止。新增部门目录成功不表示集中入口恢复，更不表示河北或内蒙古已整体覆盖。

逐地区清单保存在不提交 Git 的 `data/expansion-north-inventory.json`，包含 10 地区的栏目、状态、失败阶段、证据 URL、适配器 ID 和剩余缺口；`data/expansion-north-verification.json` 只保存样本页 URL、条数、日期范围与未知数量。

## 脱敏验证

`python -m unittest discover -s tests -p test_expansion_north.py -v`：14 项通过。覆盖全部 14 固定目录、不同分页起点、请求与返回页码不符、分页上限保留下一页、独立发布时间/考试年份、未知日期、混合栏目零匹配、外链/附件/异常 URL 排除、短标题和去重，以及备用目录固定范围、双表结构漂移和移动版重复链接。实际调用使用项目 `.venv/Scripts/python.exe`，没有安装依赖或修改主程序、数据库、共享交接及发布配置。
