"""Verified southern and central directories; no article or attachment requests."""
import hashlib
import re
from datetime import date
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


def _source(id, name, owner, url, kind='', region='广东', history=True, note='', provenance=''):
    return dict(id=id, name=name, owner=owner, url=url, kind=kind, region=region,
                area_scope='province' if region else 'national', max_pages=500 if history else 100,
                history=history, history_note=note, note=note,
                provenance=provenance or url)


_WINDOW = '仅官网当前开放的20页目录窗口；更早历史未由当前导航提供，不代表该市所有发布单位。'
EXPANSION_SOUTH_SOURCES = [
    _source('gdzz_civil', '广东省委组织部 · 公务员录用', '中共广东省委组织部',
            'https://www.gdzz.gov.cn/gwygz/lypytzgg/', '省考',
            note='仅公务员录用栏目，含选调及工作信息；各招录机关的拟录用公示仍可能另行发布。'),
    _source('foshan_recruitment', '佛山人社局 · 机关事业单位招录', '佛山市人力资源和社会保障局',
            'https://hrss.foshan.gov.cn/zwgk/jgsydwzl/', history=False, note=_WINDOW,
            provenance='https://hrss.foshan.gov.cn/'),
    _source('foshan_public', '佛山人社局 · 招录结果公示', '佛山市人力资源和社会保障局',
            'https://hrss.foshan.gov.cn/zwgk/zljggs/', history=False, note=_WINDOW,
            provenance='https://hrss.foshan.gov.cn/'),
    _source('zhanjiang_recruitment', '湛江人社局 · 公职招考', '湛江市人力资源和社会保障局',
            'https://www.zhanjiang.gov.cn/zjsfw/bmdh/rsj/zwgk/ztlm/gkzl/', history=False,
            note=_WINDOW, provenance='https://www.zhanjiang.gov.cn/rsj/'),
    _source('dongguan_recruitment', '东莞人社局 · 公开招聘', '东莞市人力资源和社会保障局',
            'https://dghrss.dg.gov.cn/xwzx/gsgg/gkzp/', history=False,
            note='仅该局当前目录的同域公告；目录含大量其他部门外链及编外招聘，外链未接入，编制性质按标题无法确认时保留未知。',
            provenance='https://dghrss.dg.gov.cn/'),
    _source('moe_civil', '教育部 · 机关公务员招录', '中华人民共和国教育部',
            'https://hudong.moe.gov.cn/s78/A04/gongzuo/moe_450/', '国考', region='', history=False,
            note='教育部官方可读入口，当前栏目仅5条2026招考相关信息，既往年度动态历史未接入；仅教育部机关。',
            provenance='https://www.moe.gov.cn/s78/A04/gongzuo/'),
]
_IDS = {s['id'] for s in EXPANSION_SOUTH_SOURCES}


def _official_url(raw, source, current):
    p, base = urlsplit(urljoin(current, raw)), urlsplit(source['url'])
    if (p.scheme not in ('https', 'http') or p.hostname != base.hostname
            or p.port not in (None, 443) or p.username or p.password or p.query or p.fragment):
        raise ValueError('目录链接离开已核验官方范围')
    return urlunsplit(('https', base.netloc, p.path, '', ''))


def _page(url, source):
    canonical = _official_url(url, source, source['url'])
    path, base = urlsplit(canonical).path, urlsplit(source['url']).path
    if path in (base, base+'index.html'): return 1
    m = re.fullmatch(re.escape(base)+r'index_([2-9]|[1-9]\d+)\.html', path)
    if not m: raise ValueError('请求不是已核验的目录分页')
    return int(m[1])


def parse_expansion_south(html, source, url):
    if source['id'] not in _IDS: raise ValueError('未知的南方扩展来源')
    page = _page(url, source)
    soup = BeautifulSoup(html, 'html.parser')
    base = urlsplit(source['url'])
    is_moe = source['id'] == 'moe_civil'
    if is_moe:
        if page != 1: raise ValueError('教育部历史目录尚未核验')
        values = [re.search(r'\bvar\s+'+key+r'\s*=\s*(\d+)\s*;', html)
                  for key in ('recordCount', 'pageSize', 'currentPage')]
        if not all(values) or int(values[2][1]) != 1:
            raise ValueError('教育部公开目录分页标记变化')
        total, size = map(lambda v:int(v[1]), values[:2])
        if not 0 < total <= size: raise ValueError('教育部目录出现尚未适配的后续页')
        next_url = None
        pattern = r'/s78/A04/tongzhi/\d{6}/t\d{8}_\d+\.html'
    else:
        current, last, nxt = soup.select_one('a.current'), soup.select_one('a.last'), soup.select_one('a.next')
        if not current or not last or not current.get('href') or not last.get('href'):
            raise ValueError('缺少已核验分页导航，不能当作目录结束')
        last_page = _page(last['href'], source)
        if (_page(current['href'], source) != page or current.get_text(strip=True) != str(page)
                or not page <= last_page <= 10000):
            raise ValueError('官网返回页码与请求不一致')
        next_url = None
        if page < last_page:
            if not nxt or not nxt.get('href') or _page(nxt['href'], source) != page+1:
                raise ValueError('下一页缺失或跳号，历史目录未查完')
            next_url = _official_url(nxt['href'], source, url)
        elif nxt:
            raise ValueError('末页仍含下一页，需复核分页')
        pattern = re.escape(base.path)+r'(?:[\w-]+/)*content/post_\d+\.html'

    from .notices import exam_year_from_title, stage
    rows, found, external_references = {}, 0, 0
    for anchor in soup.select('li a[href]'):
        raw = urljoin(url, anchor['href']); parsed = urlsplit(raw)
        if source['id'] == 'dongguan_recruitment' and re.search(r'/content/post_\d+\.html$', parsed.path):
            if parsed.hostname != base.hostname:
                external_references += 1
                continue
            if not re.fullmatch(pattern, parsed.path):
                raise ValueError('东莞目录同站公告路径发生变化，不能静默排除')
        if not re.fullmatch(pattern, parsed.path): continue
        # External references are intentionally excluded and stated in source notes.
        if parsed.hostname != base.hostname: continue
        target = _official_url(raw, source, url)
        title = BeautifulSoup(anchor.get('title') or anchor.get_text(' ', strip=True), 'html.parser').get_text(' ', strip=True)
        title = re.sub(r'\s+', ' ', title).strip()
        if not 1 <= len(title) <= 500: raise ValueError('目录公告标题缺失或异常')
        parent = anchor.find_parent('li')
        date_node = parent.select_one('span' if is_moe else '.time')
        stamps = re.findall(r'(?<!\d)(20\d{2})[-年./](\d{1,2})[-月./](\d{1,2})(?:日)?', date_node.get_text(' ',strip=True) if date_node else '')
        published = None
        if stamps:
            try: published = date(*map(int,stamps[-1])).isoformat()
            except ValueError: pass
        kind = source['kind']
        if '事业单位' in title and not re.search('编外|非编', title): kind='事业单位'
        elif '公务员' in title: kind='国考' if not source['region'] else '省考'
        if target in rows: raise ValueError('目录页内出现重复公告')
        found += 1
        rows[target] = dict(id=hashlib.sha256(target.encode()).hexdigest(), source_id=source['id'],
            source=source['name'],owner=source['owner'],title=title,url=target,published=published,
            exam_year=exam_year_from_title(title),kind=kind,region=source['region'],stage=stage(title))
    if is_moe and found != total: raise ValueError('教育部公告条数与目录总数不符')
    if not rows:
        if source['id'] != 'dongguan_recruitment' or not external_references:
            raise ValueError('未识别到有效公告目录，不能当作零条公告')
    return list(rows.values()), next_url
