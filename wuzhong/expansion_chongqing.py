"""Seven-One official recruitment directories; only title/date/link metadata."""
import hashlib
import json
import re
from datetime import date
from urllib.parse import urlparse

from bs4 import BeautifulSoup


_HOST = 'www.12371.gov.cn'
_COLUMNS = {'chongqing_qiyi_hires': '5011019', 'chongqing_qiyi_gwy': '5010890'}
EXPANSION_CHONGQING_SOURCES = [
    dict(id=sid, name=name, owner='七一网',
         url=f'https://{_HOST}/web/column/col{_COLUMNS[sid]}.html',
         region='重庆', area_scope='province', kind='', max_pages=50, history=False,
         note='七一网独立官方栏目；地区指发布来源，岗位所在地需看原文。仅索引本站网页公告标题、目录日期和链接，区县外域及附件不索引，不代表重庆全部公示。',
         history_note='官网显示的50页窗口不足以覆盖其声明的全部记录；更早历史未核验，区县外域链接已排除。')
    for sid, name in [('chongqing_qiyi_hires', '七一网 · 公示信息'),
                      ('chongqing_qiyi_gwy', '七一网 · 公务员考试')]
]


def _error(message):
    raise ValueError(message + '，不能当作目录已查完')


def _listing_url(col, page):
    suffix = '' if page == 1 else f'_{page}'
    return f'https://{_HOST}/web/column/col{col}{suffix}.html'


def chongqing_kind(title):
    """Title evidence within these civil-service columns, not employment status."""
    if re.search(r'编外|非编|编制外|非在编|劳务派遣|国有企业|国企', title):
        return ''
    national = bool(re.search(r'国考|中央机关|中央和国家机关', title))
    if re.search(r'公务员|参照公务员法|参公', title):
        return '国考' if national else '省考'
    if re.search(r'事业单位|事业编制|事业编', title):
        return '事业单位'
    return '国考' if national else '省考'


def _pager(soup, col, url):
    p = urlparse(url)
    if (p.scheme != 'https' or p.hostname != _HOST or p.port not in (None, 443)
            or p.username or p.password or p.query or p.fragment):
        _error('七一网目录请求不在固定来源内')
    m = re.fullmatch(r'/web/column/col' + col + r'(?:_([2-9]\d*|1\d+))?\.html', p.path)
    if not m:
        _error('七一网目录页码格式变化')
    requested = int(m[1]) if m[1] else 1
    pagers = []
    for script in soup.find_all('script'):
        text = script.get_text()
        for match in re.finditer(r'\bvar\s+data\s*=\s*(?=\{)', text):
            try:
                data, _ = json.JSONDecoder().raw_decode(text[match.end():])
            except ValueError:
                continue
            if isinstance(data, dict) and all(k in data for k in ('pages', 'current', 'href')):
                pagers.append(data)
    if len(pagers) != 1:
        _error('七一网目录分页数据缺失或重复')
    data = pagers[0]
    pages, current, hrefs = data['pages'], data['current'], data['href']
    if (type(pages) is not int or type(current) is not int or current != requested
            or not 1 <= current <= pages <= 10000 or not isinstance(hrefs, list)
            or len(hrefs) != pages + (current > 1) + (current < pages)):
        _error('七一网返回页码或分页条数不一致')
    # The array includes optional previous/next controls around numbered pages.
    expected = ([_listing_url(col, current - 1)] if current > 1 else [])
    expected += ['javascript:void(0)' if n == current else _listing_url(col, n)
                 for n in range(1, pages + 1)]
    expected += ([_listing_url(col, current + 1)] if current < pages else [])
    if hrefs != expected:
        _error('七一网下一页地址不在已核验栏目内')
    return _listing_url(col, current + 1) if current < pages else None


def parse_expansion_chongqing(html, source, url):
    sid = source['id']
    if sid not in _COLUMNS or source['url'] != _listing_url(_COLUMNS[sid], 1):
        _error('未知的七一网栏目配置')
    from .notices import exam_year_from_title, stage
    soup = BeautifulSoup(html, 'html.parser')
    next_url = _pager(soup, _COLUMNS[sid], url)
    containers = soup.select('.list-page__main-list')
    if len(containers) != 1:
        _error('七一网公告目录容器变化')
    entries = containers[0].find_all('a', recursive=False)
    if not entries:
        _error('七一网公告目录未识别到条目')
    rows = {}
    for anchor in entries:
        if not anchor.has_attr('href'):
            _error('七一网目录条目缺少链接')
        p = urlparse(anchor['href'])
        if p.scheme not in ('https', 'http') or p.hostname != _HOST:
            continue  # Explicitly exclude other official domains; do not request them.
        if p.username or p.password or p.port not in (None, 80 if p.scheme == 'http' else 443):
            _error('七一网公告地址包含异常认证或端口')
        if re.search(r'\.(?:pdf|docx?|xlsx?|zip|rar|jpe?g|png)$', p.path, re.I):
            continue
        m = re.fullmatch(r'/web/article/(?:(\d+)/)?web/content_(\d+)\.html', p.path)
        if p.query or not m or (m[1] and m[1] != m[2]):
            _error('七一网公告网页路径变化')
        # Do not use the anchor's full text or title attribute: those may embed
        # article content. Never inspect .content; only these metadata nodes.
        views = anchor.find_all(class_='content-view', recursive=False)
        if len(views) != 1:
            _error('七一网目录元数据容器变化')
        titles = views[0].find_all(class_='title', recursive=False)
        dates = views[0].find_all(class_='date', recursive=False)
        if len(titles) != 1 or len(dates) > 1:
            _error('七一网目录标题或日期节点变化')
        title = titles[0].get_text(' ', strip=True)
        if not title or len(title) > 500:
            _error('七一网目录标题为空或长度异常')
        published = None
        stamp = re.fullmatch(r'日期[：:]\s*(20\d{2})-(\d{2})-(\d{2})',
                             dates[0].get_text(' ', strip=True) if dates else '')
        if stamp:
            try:
                published = date(*map(int, stamp.groups())).isoformat()
            except ValueError:
                pass
        target = f'https://{_HOST}{p.path}'
        rows[target] = dict(id=hashlib.sha256(target.encode()).hexdigest(),
                            source_id=sid, source=source['name'], owner=source['owner'],
                            title=title, url=target, published=published,
                            exam_year=exam_year_from_title(title), stage=stage(title),
                            kind=chongqing_kind(title), region=source['region'])
    return list(rows.values()), next_url
