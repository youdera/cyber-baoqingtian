# GitHub政府网站采集项目核验

核验日期：2026-09-12。检查仓库元数据、文件树和代码，未运行第三方爬虫、未采集名单或下载仓库中的数据文件。代码存在不等于目前官网接口可用。

## 1. SuperJJ2333/Crawler_of_China_govern_website

- [仓库](https://github.com/SuperJJ2333/Crawler_of_China_govern_website)：最近push为2025-03-06，未归档。
- 文件树有451个Python文件；其中province_web_src有28个、total_city_src有274个。这些是文件数，不是可用来源数或覆盖率。
- [省级广东样例](https://github.com/SuperJJ2333/Crawler_of_China_govern_website/blob/main/src/scraper_src/province_web_src/Guangdong_pro.py)使用政府站搜索接口，关键词、条数上限和会话请求头固定；[浙江样例](https://github.com/SuperJJ2333/Crawler_of_China_govern_website/blob/main/src/scraper_src/total_city_src/Zhejiang_city/Zhejiang_pro.py)使用jsearchfront，默认关键词为学习考察，不是录聘公示目录。
- [主入口](https://github.com/SuperJJ2333/Crawler_of_China_govern_website/blob/main/src/main.py)仍含path_to_your_folder占位，README所列部分运行路径与实际树不一致，不能按README认定开箱即用。
- README写MIT，但实际[LICENSE](https://github.com/SuperJJ2333/Crawler_of_China_govern_website/blob/main/LICENSE)是Apache-2.0；引入前按许可证文件核对。个别样例关闭TLS或依赖本地代理，不能原样放进本项目。
- 价值：较丰富的官方接口/不同站点模板线索，适合逐个重验后重新适配。不能直接补齐58个招录来源，也没有证明全国拟录聘公示完整性。

## 2. SmartDataLab/Policy_crawler

- [仓库](https://github.com/SmartDataLab/Policy_crawler)：最近push为2020-12-27，未归档；[LICENSE](https://github.com/SmartDataLab/Policy_crawler/blob/master/LICENSE)为MIT。
- [crawl_all.sh](https://github.com/SmartDataLab/Policy_crawler/blob/master/src/crawl_data/crawl_all.sh)确实调度多省Scrapy适配器，不只是概念README。
- [浙江适配](https://github.com/SmartDataLab/Policy_crawler/blob/master/src/crawl_data/crawl_data/spiders/ZhejiangSpider.py)是办公厅公文目录，页数固定509，随后抓取正文并保存HTML。原配置ROBOTSTXT_OBEY=False，不能原样使用。
- 价值：历史政府站结构参考和模块拆分；网站模板多年变化、业务是政策公文，不能替代当前人社/公务员招录目录逐站验证。

## 3. zou-you/goverment_spider

- [仓库](https://github.com/zou-you/goverment_spider)：最近push为2025-03-12，未归档；GitHub API没有识别到许可证，根目录也未发现LICENSE文件。
- codes目录有140个Python文件，主要工信、发改、商务、科技部门政策采集。
- [浙江经信厅样例](https://github.com/zou-you/goverment_spider/blob/main/codes/7001.%E6%B5%99%E6%B1%9F%E7%9C%81%E7%BB%8F%E4%BF%A1%E5%8E%85.py)读取当前目录后明确break，不做历史翻页，并进入详情匹配政策关键词；请求关闭TLS校验。[utils.py](https://github.com/zou-you/goverment_spider/blob/main/utils.py)默认筛昨天，超时实现依赖SIGALRM。
- 价值：官方部门入口和部分DOM选择器线索；无明确授权时不复制源码，窗口化策略也不满足任意考试年度的历史检索。

## 对当前项目的判断

找到了可研究的代码和接口线索，但没有在这些仓库中验证到一个“全国公务员＋事业单位全部拟录聘公示、历史完整、持续维护”的即用系统。最有效的方向是按政府站模板复用解析思路，保留现有固定来源、TLS/robots、未知字段和partial记录，再逐站验证具体招录栏目。现有6个正式来源不因本次研究而增加。
