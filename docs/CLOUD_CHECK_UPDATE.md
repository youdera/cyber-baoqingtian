# 云端检查与时间条件兼容性核验

核验时间：2026-09-12 13:17（北京时间）。本次只读取 GitHub 运行状态；未触发新采集、创建 Issue 或发送提醒。

## 已发布代码的核验

公开仓库 [youdera/cyber-baoqingtian](https://github.com/youdera/cyber-baoqingtian) 的 `main` 在核验时指向 `36a91b67a19d43e491057f63ab9b74b6a029d972`。GitHub 返回仓库 `private=false`，About 中的项目名、MIT 开源与欢迎收藏／参与更新描述已保存。

- [CI 运行 34675059048](https://github.com/youdera/cyber-baoqingtian/actions/runs/34675059048)：由上述提交的 push 触发，状态 `completed`，结论 `success`；UTC 05:14:09 开始、05:14:25 更新为完成。
- Job `103503327600` 的 Python 脱敏测试、三份 JavaScript 语法检查及指南材料检查步骤全部成功。原始日志明确显示 **26 项 Python 测试通过**。这个数量是公开快照的测试数，不是包含历史兼容模块的本地测试总数。
- [全部 Actions 运行](https://github.com/youdera/cyber-baoqingtian/actions) 的官方 API 在核验时返回共 4 条记录：3 次代码 CI 成功，1 次手动公告检查成功；没有 `.github/workflows/source-audit.yml` 的运行记录。因此，每周来源巡检已配置，但其云端执行仍未验收，不能当作已经运行。
- [首次手动公告检查 34674112402](https://github.com/youdera/cyber-baoqingtian/actions/runs/34674112402) 的成功记录仍存在。此次没有重新采集，也没有验证未来定时触发或用户邮箱／手机实际送达。

状态通过 GitHub 连接器读取官方 Actions REST API，并核对 job 步骤与日志。旧式 commit status 接口返回空列表，不能据此断言 CI 未运行。未使用只返回 pull request 触发记录的接口判断 push CI。

## 本次时间筛选兼容性

云端配置继续调用与网页共用的 `validate_filters`，公告发布时间和招考年度分别处理：

- 至少填写其中一种。只写开始或结束一端时，按一个月或一个招考年度补齐。
- 只填公告月份：不限制招考年度。
- 只填招考年度：不限制公告发布时间，跨年发布的公告仍可匹配。
- 两者都填：同时满足两个范围；不能把招考年度当作公告发布年份。
- GitHub 报告分别显示两种时间，未选维度显示“不限”，并显示省内／全国中央范围。没有任何符合条件的记录，仍不等于已完成全国检索。

`cloud-watch.json` 可采用以下任一时间配置，并保留所需的地区、类型、来源和公示阶段条件：

```json
{"month_from": "2026-09", "notice_scope": "public"}
```

```json
{"year_from": 2025, "notice_scope": "public"}
```

```json
{"month_from": "2026-01", "month_to": "2026-12", "year_from": 2025, "notice_scope": "public"}
```

本机网页关注条件与 GitHub 配置仍分别保存，网页操作不会自动改变仓库的云端筛选条件。

本地运行 `python -m unittest tests.test_cloud_watch -v`，3 项测试全部通过，使用脱敏虚构目录和临时数据库，不访问公告网站。验证包括 2025 招考在 2026 发布的跨年样例、只选月份／年度、单侧端点补齐、双条件交集、首次基线静默、等价条件不重置基线、变更提醒与确认去重。新增代码的云端 CI 需在统一发布后另行核验；以上旧提交的成功状态不代表新增代码已在云端执行。


### 2026-09-12 · 云端最终验收

- 代码提交5a2be32ffeec30793f5bec1b685295afbe154107的CI运行34675531128，Windows与Ubuntu均成功；启动入口、Python测试、前端语法及材料下载检查通过。
- 首次云端来源巡检运行34675582832成功，audit任务2分49秒。报告列出64个入口；6个正式栏目首页均sample_ok，其余门户/候选分别保留失败或待适配结果。报告及artifact已生成；巡检成功不等于64个来源全部可用或历史完整。
- 此次手动运行验证云端执行路径，不代表未来定时触发或邮箱手机提醒送达已经实测。本机服务保持运行，原关注仍暂停。

完整验收见[VERIFICATION_0_2.md](VERIFICATION_0_2.md)。
