# 无终恨意 · 公告浏览与更新提醒

官方招录公告元数据索引。支持公告日期、招考年度、地区、类型及栏目筛选，提供官方链接和新公示提醒。

当前仅接入统计局、福建科技厅及广东人社厅三个栏目，不能代表全国完整覆盖。不下载或索引人员名单，不做身份关联。

Windows安装Python 3.10+后运行start.cmd。也可安装requirements.txt后运行python notice_app.py --open。

GitHub Actions每天北京时间09:17检查cloud-watch.json中的范围，也可手动触发。网页关注不会同步到云端。通过仓库Issue提醒仓库所有者，邮件及手机通知取决于GitHub设置；首次运行建立基线。详见[使用与限制](docs/CLOUD_WATCH.md)和[覆盖核验](docs/SOURCE_COVERAGE.md)。

本仓库为当前应用的独立发布快照，未包含本机数据或旧版个人匹配模块。
