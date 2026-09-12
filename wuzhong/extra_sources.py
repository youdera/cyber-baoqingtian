"""Reviewed static announcement directories; never follow announcement links."""
import hashlib
import re
from datetime import date
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


EXTRA_SOURCES = [
    dict(id='beijing', name='首都之窗 · 公务员招考', owner='北京市人民政府',
         url='https://www.beijing.gov.cn/gongkai/rsxx/gwyzk/', kind='省考',
         region='北京', area_scope='province', max_pages=60, history=True,
         note='北京市政府公务员招考栏目；只覆盖官网当前提供的分页目录，不代表北京所有招录单位。'),
    dict(id='beijing_jxj', name='北京经信局 · 招录相关人事公告', owner='北京市经济和信息化局',
         url='https://jxj.beijing.gov.cn/zwgk/rsxx/', kind='',
         region='北京', area_scope='province', max_pages=60, history=True,
         note='仅经信局人事栏目中标题可识别的招录公告；任免等无关人事信息不纳入，未知招录类型保留待核对。'),
    dict(id='fujian_hr', name='福建省人社厅 · 事业单位招聘公示', owner='福建省人力资源和社会保障厅',
         url='https://rst.fujian.gov.cn/zw/ztzl/zxzt/sydwrczp/zpgs/', kind='事业单位',
         region='福建', area_scope='province', max_pages=1, history=False,
         note='仅读取官网当前页面内嵌的招聘公示目录；动态历史分页尚未接入，不代表福建全部招聘公示。'),
]

SOURCE_AREAS = {s['id']: s['area_scope'] for s in EXTRA_SOURCES}
_RECRUITMENT = re.compile(r'公务员|招考|招录|招聘|遴选|选调|拟.*(?:录用|聘用|聘人员|聘人选)|(?:录用|聘用).*公示')


def _pager(html, source, url):
    if source['id'] == 'fujian_hr':
        count = re.search(r'''\brecordCount\s*:\s*['"](\d+)['"]''', html)
        static = re.search(r'\bmaxStaticIndex\s*:\s*(\d+)', html)
        size = re.search(r'\bprepage\s*:\s*(\d+)', html)
        if not all((count, static, size)) or not all(int(x[1]) > 0 for x in (count, static, size)) or 'list2.trsapi' not in html:
            raise ValueError('福建招聘公示目录结构已变化，需要维护来源')
        # The HTML embeds several displayed pages. Older pages use a separate
        # dynamic service; history=False makes the engine preserve partial.
        return None
    configs = re.findall(r'\bPager\s*\(\s*\{([^{}]+)\}\s*\)', html)
    if len(configs) != 1:
        raise ValueError('北京目录分页结构已变化，需要维护来源')
    config = configs[0]
    size = re.search(r'\bsize\s*:\s*(\d+)\b', config)
    current = re.search(r'\bcurrent\s*:\s*(\d+)\b', config)
    prefix = re.search(r'''\bprefix\s*:\s*['"]index['"]''', config)
    suffix = re.search(r'''\bsuffix\s*:\s*['"]html['"]''', config)
    if not all((size, current, prefix, suffix)):
        raise ValueError('北京目录分页参数已变化，需要维护来源')
    total, page = int(size[1]), int(current[1])
    base = source['url']
    requested = re.fullmatch(re.escape(urlparse(base).path) + r'(?:index(?:_(\d+))?\.html)?', urlparse(url).path)
    if not requested or not 1 <= total <= 10000 or not 0 <= page < total:
        raise ValueError('北京目录页码无效，需要维护来源')
    expected_page = int(requested[1]) if requested[1] else 0
    if page != expected_page:
        raise ValueError('官网返回页码与请求不一致，历史目录未查完')
    return urljoin(base, f'index_{page+1}.html') if page + 1 < total else None


def parse_extra(html, source, url):
    """Return listing metadata and the next *directory* URL, with drift checks."""
    if source['id'] not in SOURCE_AREAS:
        raise ValueError('未知的扩展来源')
    # Delayed import avoids a cycle when notices registers these fixed adapters.
    from .notices import exam_year_from_title, stage

    next_url = _pager(html, source, url)
    soup = BeautifulSoup(html, 'html.parser')
    base = urlparse(source['url'])
    items, recognized = {}, 0
    for a in soup.select('a[href]'):
        target = urljoin(url, a['href']).split('#')[0]
        try:
            parsed = urlparse(target)
            allowed = (parsed.scheme == 'https' and parsed.hostname == base.hostname
                       and parsed.port in (None, 443) and not parsed.username and not parsed.password
                       and not parsed.query and parsed.path.startswith(base.path)
                       and re.search(r'/\d{6}/t\d{8}_\d+\.html?$', parsed.path))
        except ValueError:
            allowed = False
        if not allowed:
            continue
        title = (a.get('title') or a.get_text(' ', strip=True)).strip()
        if not 6 <= len(title) <= 500:
            continue
        recognized += 1
        if source['id'] == 'beijing_jxj' and not _RECRUITMENT.search(title):
            continue
        parent = a.find_parent('li') or a.parent
        dates = re.findall(r'(?<!\d)(20\d{2})[-年./](\d{1,2})[-月./](\d{1,2})(?:日)?', parent.get_text(' ', strip=True))
        published = None
        if dates:
            try:
                published = date(*map(int, dates[-1])).isoformat()
            except ValueError:
                pass
        kind = '事业单位' if '事业单位' in title else source['kind']
        if not kind and '公务员' in title:
            kind = '省考'
        items[target] = dict(id=hashlib.sha256(target.encode()).hexdigest(), source_id=source['id'],
                             source=source['name'], owner=source['owner'], title=title, url=target,
                             published=published, exam_year=exam_year_from_title(title),
                             kind=kind, region=source['region'], stage=stage(title))
    if not recognized:
        raise ValueError('未识别到有效公告目录，不能当作零条公告')
    return list(items.values()), next_url
