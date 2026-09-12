"""Fixed official examination directories, parsed without article requests."""
import hashlib
import re
from datetime import date
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


EAST_SOURCES = [
    dict(id='shanxi_gwy', name='山西省人社厅 · 公务员考试',
         owner='山西省人力资源和社会保障厅',
         url='https://rst.shanxi.gov.cn/rsks/gwyks/', kind='省考',
         region='山西', area_scope='province', max_pages=120, history=True,
         note='山西人事考试公务员栏目，含选调与遴选相关公告；只覆盖官网现存分页，不代表全省所有发布主体或已撤下历史。'),
    dict(id='shanxi_sydw', name='山西省人社厅 · 事业单位考试',
         owner='山西省人力资源和社会保障厅',
         url='https://rst.shanxi.gov.cn/rsks/sydwks/', kind='事业单位',
         region='山西', area_scope='province', max_pages=120, history=True,
         note='山西人事考试事业单位栏目，主要为省直统考信息；只覆盖官网现存分页，不代表各市县及各单位全部拟聘公示。'),
    dict(id='shanxi_sydw_jobs', name='山西省人社厅 · 省直事业单位招聘公告',
         owner='山西省人力资源和社会保障厅',
         url='https://rst.shanxi.gov.cn/ztzl/zpxx/szsydwzpgg/', kind='事业单位',
         region='山西', area_scope='province', max_pages=120, history=True,
         note='省直事业单位公开招聘公告栏目，含医院、高校等单位的招聘信息；并非拟聘公示专栏，不代表各市县及全部历史。'),
]
_SOURCE_IDS = frozenset(s['id'] for s in EAST_SOURCES)
_ARTICLE = re.compile(r'^/(?:rsks/|ztzl/zpxx/).*/\d{6}/t\d{8}_\d+\.shtml$')


def _next_directory(html, source, url):
    base = urlparse(source['url'])
    requested = urlparse(url)
    if (requested.scheme != 'https' or requested.hostname != base.hostname
            or requested.port not in (None, 443) or requested.username or requested.password
            or requested.query or requested.fragment):
        raise ValueError('山西目录请求地址无效，需要维护来源')
    path_match = re.fullmatch(re.escape(base.path) + r'(?:index(?:_([1-9]\d*))?\.shtml)?', requested.path)
    current = re.findall(r'\bvar\s+currentPage\s*=\s*(\d+)\s*;', html)
    total = re.findall(r'\bvar\s+countPage\s*=\s*(\d+)\s*;', html)
    if not path_match or len(current) != 1 or len(total) != 1:
        raise ValueError('山西目录分页结构已变化，需要维护来源')
    page, pages = int(current[0]), int(total[0])
    expected = int(path_match[1]) if path_match[1] else 0
    if not 1 <= pages <= 10000 or not 0 <= page < pages or page != expected:
        raise ValueError('山西官网返回页码与请求不一致，历史目录未查完')
    # Do not suppress the next page at our cap: the engine must report partial.
    return urljoin(source['url'], f'index_{page + 1}.shtml') if page + 1 < pages else None


def parse_east(html, source, url):
    """Return official metadata and the next directory URL; fail on drift."""
    if source['id'] not in _SOURCE_IDS:
        raise ValueError('未知的山西目录来源')
    from .notices import exam_year_from_title, stage

    next_url = _next_directory(html, source, url)
    soup = BeautifulSoup(html, 'html.parser')
    containers = soup.select('ul.second_right_ul')
    if len(containers) != 1:
        raise ValueError('山西公告目录容器已变化，需要维护来源')
    host = urlparse(source['url']).hostname
    items = {}
    for li in containers[0].find_all('li', recursive=False):
        a = li.find('a', href=True)
        if a is None:
            continue
        target = urljoin(url, a['href'].strip()).split('#')[0]
        try:
            parsed = urlparse(target)
            allowed = (parsed.scheme == 'https' and parsed.hostname == host
                       and parsed.port in (None, 443) and not parsed.username and not parsed.password
                       and not parsed.query and _ARTICLE.fullmatch(parsed.path))
        except ValueError:
            allowed = False
        if not allowed:
            continue
        title = (a.get('title') or '').strip() or a.get_text(' ', strip=True).strip()
        if not title or len(title) > 500:
            raise ValueError('山西目录公告标题为空或长度异常，不能跳过后当作采集完成')
        published = None
        date_node = li.select_one('span.pull-right')
        stamp = re.fullmatch(r'(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})',
                             date_node.get_text(strip=True) if date_node else '')
        if stamp:
            try:
                published = date(*map(int, stamp.groups())).isoformat()
            except ValueError:
                pass
        items[target] = dict(id=hashlib.sha256(target.encode()).hexdigest(),
                             source_id=source['id'], source=source['name'], owner=source['owner'],
                             title=title, url=target, published=published,
                             exam_year=exam_year_from_title(title), kind=source['kind'],
                             region=source['region'], stage=stage(title))
    if not items:
        raise ValueError('未识别到有效山西公告目录，不能当作零条公告')
    return list(items.values()), next_url
