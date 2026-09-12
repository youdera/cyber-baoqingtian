"""Fixed Sichuan examination directories, parsed from their public list pages.

No announcement detail, attachment, or third-party RSS content is fetched here.
"""
import hashlib
import re
from datetime import date
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from bs4 import BeautifulSoup


_SCOPES = (
    ('scpta_gwy', 56, 117, '公务员招考', '省考'),
    ('scpta_selected', 56, 88, '选调生', '省考'),
    ('scpta_selection', 56, 98, '公开遴选和公开选调', '省考'),
    ('scpta_provincial', 67, 68, '省属事业单位', '事业单位'),
    ('scpta_municipal', 67, 69, '市州事业单位', '事业单位'),
    ('scpta_other', 67, 70, '其他事业单位', '事业单位'),
)
_HOST = 'www.scpta.com.cn'
WEST_SOURCES = [
    dict(id=id_, name=f'四川人事考试 · {label}', owner='四川省人事考试中心',
         url=f'https://{_HOST}/front/News/List/{category}?t={topic}&a=0',
         provenance='https://rst.sc.gov.cn/',
         kind=kind, region='四川', area_scope='province', max_pages=100, history=True,
         note=f'仅四川人事考试专栏的{label}目录；最多读取100页，未涵盖未汇集到本栏目或官网已移除的公告。'
              + ('遴选、选调属专题类别，是否为新录用以原文为准。' if topic == 98 else ''))
    for id_, category, topic, label, kind in _SCOPES
]
for _source in WEST_SOURCES:
    if _source['id'] == 'scpta_selected':
        _source.update(history=False,
                       history_note='选调生目录首页与后续页记录总数不一致；只保留当前可读取目录，历史范围待复核。')
        _source['note'] += _source['history_note']
SOURCE_AREAS = {source['id']: source['area_scope'] for source in WEST_SOURCES}
_CONFIG = {item[0]: item[1:3] for item in _SCOPES}


def _parameters(url, category, topic, *, prefix=False):
    """Validate a same-host list URL and return its one-based page number."""
    try:
        parsed = urlparse(url)
        query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
        allowed = (parsed.scheme == 'https' and parsed.hostname == _HOST
                   and parsed.port in (None, 443) and not parsed.username
                   and not parsed.password and not parsed.fragment
                   and parsed.path == f'/front/News/List/{category}'
                   and set(query) <= {'t', 'a', 'i'}
                   and query.get('t') == [str(topic)] and query.get('a') == ['0'])
        if not allowed:
            raise ValueError
        if prefix:
            if query.get('i') != ['']:
                raise ValueError
            return None
        pages = query.get('i', ['1'])
        if len(pages) != 1 or not re.fullmatch(r'[1-9]\d{0,4}', pages[0]):
            raise ValueError
        return int(pages[0])
    except (ValueError, TypeError):
        raise ValueError('四川目录地址或筛选参数变化，需要维护来源') from None


def _pager(soup, source, url):
    category, topic = _CONFIG[source['id']]
    _parameters(source['url'], category, topic)
    expected = _parameters(url, category, topic)
    script = '\n'.join(node.get_text() for node in soup.find_all('script') if not node.get('src'))
    selected = re.findall(r'''\bvar\s+selId\s*=\s*parseInt\(\s*['"](\d+)['"]\s*\)''', script)
    if selected != [str(topic)] or not soup.select_one(f'#left_item_{topic}.active'):
        raise ValueError('官网返回的选中栏目与请求不一致，不能混入其他招录类别')
    values = {}
    for key in ('listCount', 'pageIndex', 'pageSize', 'pageUrl'):
        matches = re.findall(r'\bvar\s+' + key + r'''\s*=\s*['"]([^'"]*)['"]\s*;''', script)
        if len(matches) != 1:
            raise ValueError('四川目录分页结构变化，不能当作零条公告')
        values[key] = matches[0]
    if any(not re.fullmatch(r'\d+', values[key]) for key in ('listCount', 'pageIndex', 'pageSize')):
        raise ValueError('四川目录分页数值无效，需要维护来源')
    count, current, size = (int(values[key]) for key in ('listCount', 'pageIndex', 'pageSize'))
    if not (0 <= count <= 1_000_000 and 1 <= size <= 200 and current == expected):
        raise ValueError('官网返回页码或记录数与请求不一致，历史目录未查完')
    total = max(1, (count + size - 1) // size)
    if not 1 <= current <= total:
        raise ValueError('四川目录返回越界页码，历史目录未查完')
    prefix = urljoin(source['url'], unquote(values['pageUrl']))
    _parameters(prefix, category, topic, prefix=True)
    if not prefix.endswith('i='):
        raise ValueError('四川目录页码参数位置变化，需要维护来源')
    next_url = prefix + str(current + 1) if current < total else None
    # Leave next_url at the application cap so the engine reports partial.
    return count, current, size, next_url


def _article_url(href, source, category):
    target = urljoin(source['url'], href)
    try:
        parsed = urlparse(target)
        query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
        if (parsed.scheme != 'https' or parsed.hostname != _HOST
                or parsed.port not in (None, 443) or parsed.username or parsed.password
                or parsed.fragment or query != {'t': [str(category)]}
                or not re.fullmatch(r'/front/News/info/[0-9a-fA-F]{32}', parsed.path)):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError('四川目录出现未核验的公告链接，当前页未完成') from None
    return f'https://{_HOST}{parsed.path}?t={category}'


def parse_west(html, source, url):
    """Return announcement metadata and the next verified directory URL."""
    if source['id'] not in _CONFIG:
        raise ValueError('未知的西部扩展来源')
    from .notices import exam_year_from_title, stage

    soup = BeautifulSoup(html, 'html.parser')
    count, current, size, next_url = _pager(soup, source, url)
    containers = soup.select('div.wrap-content')
    if len(containers) != 1 or not soup.select_one('#pagination'):
        raise ValueError('四川公告列表容器变化，需要维护来源')
    nodes = containers[0].find_all('li', recursive=False)
    expected = min(size, max(0, count - (current - 1) * size))
    if not nodes or len(nodes) != expected:
        raise ValueError('四川公告列表条数与分页记录不一致，不能当作零条公告')
    items = {}
    for node in nodes:
        links = node.find_all('a', href=True, recursive=False)
        if len(links) != 1:
            raise ValueError('四川公告条目结构变化，当前页未完成')
        anchor = links[0]
        title = (anchor.get('title') or anchor.get_text(' ', strip=True)).strip()
        if not 1 <= len(title) <= 500:
            raise ValueError('四川公告标题缺失或异常，当前页未完成')
        target = _article_url(anchor['href'], source, _CONFIG[source['id']][0])
        dates = node.find_all('span', recursive=False)
        published = None
        if len(dates) == 1:
            match = re.fullmatch(r'(20\d{2})-(\d{1,2})-(\d{1,2})', dates[0].get_text(strip=True))
            if match:
                try:
                    published = date(*map(int, match.groups())).isoformat()
                except ValueError:
                    pass
        if target in items:
            raise ValueError('四川目录在同页重复返回公告，分页结果需要复核')
        items[target] = dict(id=hashlib.sha256(target.encode()).hexdigest(),
                             source_id=source['id'], source=source['name'], owner=source['owner'],
                             title=title, url=target, published=published,
                             exam_year=exam_year_from_title(title), kind=source['kind'],
                             region=source['region'], stage=stage(title))
    return list(items.values()), next_url
