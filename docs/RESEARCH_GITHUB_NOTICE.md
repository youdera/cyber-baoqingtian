# GitHub 招录公告项目源码核查

核查日期：2026-09-12。目标是寻找能帮助现有官方公告目录扩展、分页采集和更新提醒的代码；不采集人员名单。本轮读取公开仓库与源代码，没有运行这些项目、安装依赖或触发它们的采集与通知。开工已读取 HANDOFF.md、AGENTS.md 和当前发布能力。

## 结论

找到了相关项目，但本轮深入检查的四个仓库都不能直接把本项目余下约 58 个入口变成可用来源。主要原因分别是：第三方聚合站而非各地官方原站、只查首页、用途是研究生招生，以及把固定示例混入实际采集结果。

建议保留现有采集器，借鉴少量设计并独立核对候选栏目。来源登记、可联网、可解析、历史分页完整和持续更新应分别验收。以下顺序按对本项目的参考价值排列，**不表示建议安装或整套移植**。

| 顺序 | 仓库 | 默认分支最新提交日期（UTC） | 许可核查 | 主要参考价值 | 不能直接采用的原因 |
| --- | --- | --- | --- | --- | --- |
| 1 | [preventive-med-monitor](https://github.com/starlgz/preventive-med-monitor) | [2026-08-23](https://github.com/starlgz/preventive-med-monitor/commit/ba18c84e7eac609a0c315420c4b4594ebb2e4611) | 根目录与 LICENSE 路径未发现许可文件 | 人社、卫健、疾控来源线索 | 抽查发现空实现、固定示例、失败回退示例及关闭 TLS 校验 |
| 2 | [zk-monitor](https://github.com/w1ndys/zk-monitor) | [2026-02-26](https://github.com/w1ndys/zk-monitor/commit/adefd540a85b4e8cf9a237bbe6896d4b80a9ff8c) | 根目录与 LICENSE 路径未发现许可文件 | 小型站点适配器、首次基线、按 URL 去重 | 只有山东和天津研考通知；无历史翻页 |
| 3 | [qgsydw](https://github.com/FlyingOnion/qgsydw) | [2025-05-04](https://github.com/FlyingOnion/qgsydw/commit/de16e1688aa55ed3514f5e52e23cde64fd39dad6) | [Mulan PSL v2](https://github.com/FlyingOnion/qgsydw/blob/de16e1688aa55ed3514f5e52e23cde64fd39dad6/license) | 招聘聚合接口字段与分页参数线索 | 单个第三方网站；当前调用未遍历分页，持久增量逻辑未完成 |
| 4 | [GongKaoLeiDaSpider](https://github.com/Day-Bright/GongKaoLeiDaSpider) | [2023-01-24](https://github.com/Day-Bright/GongKaoLeiDaSpider/commit/05d7b6a0ebe898b889bd639ef81ab5f9c9f0ca6e) | 根目录与 LICENSE 路径未发现许可文件 | 省份、招考类型、最近天数筛选及邮件示例 | 公考雷达第三方来源，默认排除了拟聘和拟录用 |

上述四仓库在核查时均未归档。提交日期只能说明代码更新时间，不能证明官网适配仍有效；本轮未替作者验证其线上服务。未发现许可文件的代码本轮没有复制进本项目。qgsydw 如后续实际引用代码，需保留其许可证及原有声明，不能仅用本项目 MIT 声明覆盖。

## 1. preventive-med-monitor：可找线索，不能相信登记数量

`provinces_pool.py` 有 84 个入口条目，只有 9 个使用 HTTPS，其余原始配置为 HTTP。条目包括人社、卫生健康及疾控中心；不少是门户首页。这是仓库声明的来源池，本轮没有逐站核实主办方、栏目存在性和当前可访问性。[源池配置](https://github.com/starlgz/preventive-med-monitor/blob/ba18c84e7eac609a0c315420c4b4594ebb2e4611/app/sources/provinces_pool.py)

它同时注册第三方 shiyebian.com 的 32 个地区分栏，相关代码支持限定页数的 `index_N.html` 循环。这个数量代表聚合站分栏，不能据此推导各省原站完整覆盖。[聚合来源代码](https://github.com/starlgz/preventive-med-monitor/blob/ba18c84e7eac609a0c315420c4b4594ebb2e4611/app/sources/shiyebian.py)

源码抽查发现以下具体问题：

- 动态省池适配器直接返回空列表；登记该条目并不会抓到公告。[registry.py 第 22 行](https://github.com/starlgz/preventive-med-monitor/blob/ba18c84e7eac609a0c315420c4b4594ebb2e4611/app/sources/registry.py#L22)
- 江苏人社适配器直接返回写在代码中的固定公告，没有联网请求。[jiangsu_rsks.py 第 13 行](https://github.com/starlgz/preventive-med-monitor/blob/ba18c84e7eac609a0c315420c4b4594ebb2e4611/app/sources/jiangsu_rsks.py#L13)
- 浙江、广东适配器会在未获得实际条目时返回示例公告；广东还将抓取当日写为发布日期。这会破坏本项目“未知如实显示”和独立时间筛选的可靠性。[浙江回退](https://github.com/starlgz/preventive-med-monitor/blob/ba18c84e7eac609a0c315420c4b4594ebb2e4611/app/sources/zhejiang_rsks.py#L45)、[广东采集与回退](https://github.com/starlgz/preventive-med-monitor/blob/ba18c84e7eac609a0c315420c4b4594ebb2e4611/app/sources/guangdong_rsks.py#L48)
- 公共 HTTP 客户端设置 `verify=False`，与本项目 TLS 约定冲突。[base.py 第 68 行](https://github.com/starlgz/preventive-med-monitor/blob/ba18c84e7eac609a0c315420c4b4594ebb2e4611/app/sources/base.py#L68)

调度和通知模块确实有实现：APScheduler 定时、逐来源日志、URL 查重、多渠道通知。但静态检查还发现调度入口把 client 传给 `max_pages` 参数，并使用条目模型没有声明的字段；发送失败记录也可能被后续查重当作已处理。没有运行测试，不能断言其整个通知链可用。[调度器](https://github.com/starlgz/preventive-med-monitor/blob/ba18c84e7eac609a0c315420c4b4594ebb2e4611/app/scheduler/manager.py)、[条目模型](https://github.com/starlgz/preventive-med-monitor/blob/ba18c84e7eac609a0c315420c4b4594ebb2e4611/app/sources/base.py)、[通知查重](https://github.com/starlgz/preventive-med-monitor/blob/ba18c84e7eac609a0c315420c4b4594ebb2e4611/app/notifications/service.py)

可用于本项目的候选线索包括北京人社招聘栏目、广东卫健人事栏目和广东疾控通知/人事栏目；应回到官网核实 HTTPS 地址和真实目录结构后，独立编写适配。广东人社事业单位栏目与本项目已有来源重复，不应再计为新增。[北京配置](https://github.com/starlgz/preventive-med-monitor/blob/ba18c84e7eac609a0c315420c4b4594ebb2e4611/app/sources/beijing_rsj.py)、[广东配置](https://github.com/starlgz/preventive-med-monitor/blob/ba18c84e7eac609a0c315420c4b4594ebb2e4611/app/sources/guangdong_rsks.py)、[疾控配置](https://github.com/starlgz/preventive-med-monitor/blob/ba18c84e7eac609a0c315420c4b4594ebb2e4611/app/sources/guangdong_cdc.py)

## 2. zk-monitor：结构清楚，但监控的是考研

实际配置仅山东省招生考试院研招栏目和天津招考资讯网研考栏目。两份适配器都只请求一个列表页，提取标题、链接、日期；没有翻页或历史回补。不能作为公务员、事业单位、教师招聘公示来源加入当前产品。[配置](https://github.com/w1ndys/zk-monitor/blob/adefd540a85b4e8cf9a237bbe6896d4b80a9ff8c/config.yaml)、[山东适配器](https://github.com/w1ndys/zk-monitor/blob/adefd540a85b4e8cf9a237bbe6896d4b80a9ff8c/monitors/sdzk_yzk.py)、[天津适配器](https://github.com/w1ndys/zk-monitor/blob/adefd540a85b4e8cf9a237bbe6896d4b80a9ff8c/monitors/tj_zhaokao_ykxk.py)

值得借鉴的是每站独立适配、首次建立基线、通知器独立。但保存的是当前页面快照，按 URL 对比新增；同一 URL 改标题不算更新。通知发送异常后仍保存当前快照，下一轮可能不再提醒失败条目。本项目已有持久元数据和变更提醒，无需退回这套逻辑。[存储](https://github.com/w1ndys/zk-monitor/blob/adefd540a85b4e8cf9a237bbe6896d4b80a9ff8c/framework/storage.py)、[运行与发送顺序](https://github.com/w1ndys/zk-monitor/blob/adefd540a85b4e8cf9a237bbe6896d4b80a9ff8c/framework/runner.py#L102)

## 3. qgsydw：名称“全国”指第三方平台

Vite 代理目标是 `www.qgsydw.com`，列表来自 `/dwsp/Search/GetPagerData`，不是遍历各省人社/组织部门官网。返回字段有标题、地区分组、发布日期、链接和分页总数。[代理目标](https://github.com/FlyingOnion/qgsydw/blob/de16e1688aa55ed3514f5e52e23cde64fd39dad6/vite.config.ts)、[接口与列表函数](https://github.com/FlyingOnion/qgsydw/blob/de16e1688aa55ed3514f5e52e23cde64fd39dad6/src/alova.ts#L36)

虽然参数定义包含 pageIndex、地区等，当前页面无参数调用 `getRecruitmentList()`，函数只取一次响应，没有根据 pageCount 循环；IndexedDB 与最大 ID 增量逻辑被注释。详情读取后还调用腾讯云模型，超出我们当前“只取目录元数据”的链路。没有看到定时任务或通知模块。[列表函数](https://github.com/FlyingOnion/qgsydw/blob/de16e1688aa55ed3514f5e52e23cde64fd39dad6/src/alova.ts#L81)、[实际页面调用](https://github.com/FlyingOnion/qgsydw/blob/de16e1688aa55ed3514f5e52e23cde64fd39dad6/src/App.vue)

可以了解聚合站的数据字段；不能把它作为官方来源完整覆盖证明。本轮不接入该第三方平台，不复制它的云模型调用。

## 4. GongKaoLeiDaSpider：适合找报名机会，默认恰好排除公示

源地址是公考雷达地区分页，支持省份和公务员、事业单位、教师、医疗等类型。`spider.py` 翻页到超出最近 N 天，并用 QQ SMTP 发送本轮结果；没有持久去重数据库、元数据变更检测或内置 GitHub 定时工作流。[采集与邮件源码](https://github.com/Day-Bright/GongKaoLeiDaSpider/blob/05d7b6a0ebe898b889bd639ef81ab5f9c9f0ca6e/spider.py)

默认过滤词包括“拟聘”“拟录用”“体检”“面试”“成绩”等，这些恰是本项目要保留的招录阶段。按时间提前停页也需要目录日期单调的前提，不能直接搬到有置顶公告的政府目录。[过滤配置](https://github.com/Day-Bright/GongKaoLeiDaSpider/blob/05d7b6a0ebe898b889bd639ef81ab5f9c9f0ca6e/config.py#L1)

## 本项目下一步

1. 使用现有 64 个入口的巡检结果作为主清单，逐项区分“门户待找栏目、栏目待适配、访问失败、已接入”；不为了凑数启用空适配。
2. 对可访问的官方栏目优先按真实模板归类：静态列表、TRS 翻页、政府内容管理平台接口；先证明标题/官方链接/发布日期正确，再补历史翻页与断点恢复。
3. 先完成既有省份入口，再考虑卫健、疾控、教育等新发布主体。第三方仓库只能提供候选地址，候选仍须核查，不能自动写入正式来源。
4. 回归验收应覆盖空页面、置顶旧文、分页重复、模板变化、缺日期、TLS/robots 失败和提醒重试；失败不能生成示例公告，也不能伪造当日发布日期。

补充排除记录：搜索命中 [yimig/scrapyTest](https://github.com/yimig/scrapyTest)，页面已标明 2023-07-04 归档，本轮未深入；`gaofeibilly-maker/oriole-job-engine` 搜索摘要尚存在，但仓库页面及 GitHub 读取均返回 404，故未作为可复用项目推荐。本轮检索不是 GitHub 全库穷举，没有发现可验证且能直接补齐当前约 58 个入口的现成适配库。
