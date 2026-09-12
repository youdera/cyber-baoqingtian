"""Reviewed western official listing adapters; no detail or attachment fetches."""
import hashlib
import re
from datetime import date
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup


def _source(id_, region, owner, label, url, kind='', *, pages=100, history=True,
            note='', provenance=None):
    result = dict(id=id_, name=f'{region} · {label}', owner=owner, url=url,
                  kind=kind, region=region, area_scope='province', max_pages=pages,
                  history=history,
                  note='仅本官方栏目现存公告元数据；不包含未汇集到栏目或已移除的公告。' + note)
    if not history:
        result['history_note'] = note
    if provenance:
        result['provenance'] = provenance
    return result


EXPANSION_WEST_SOURCES = [
    _source('gz_hr_recruit', '贵州', '贵州省人力资源和社会保障厅', '事业单位公开招聘',
            'https://rst.guizhou.gov.cn/zwgk/zdlyxx/sydwgkzp/', '事业单位', pages=180,
            history=False, note='本栏目含站外转载链接；仅纳入同站公告，外链及其历史不在本适配范围。'),
    _source('yn_hr_recruit', '云南', '云南省人力资源和社会保障厅', '事业单位招聘',
            'https://hrss.yn.gov.cn/NewsLsit.aspx?ClassID=602', '事业单位', pages=120),
    _source('yn_gov_civil', '云南', '云南省人民政府办公厅', '省政府公务员招录',
            'https://www.yn.gov.cn/zwgk/zfxxgkpt/fdzdgknr/ptrsxx/gwyzl/', '省考', pages=30,
            note='省政府栏目转载范围有限，不等同于云岭先锋招录专栏或全省各招录机关。'),
    _source('xz_hr_notices', '西藏', '西藏自治区人力资源和社会保障厅', '通知公告中的招录信息',
            'https://hrss.xizang.gov.cn/xwzx/tzgg/', pages=30, history=False,
            note='混合通知栏目，按标题保留招录信息；分页只给出20页，脚本总记录数为1456，较早档案未获完整访问证明。'),
    _source('sn_hr_notices', '陕西', '陕西省人力资源和社会保障厅', '通知公告中的招录信息',
            'https://rst.shaanxi.gov.cn/sy/tzgg/', pages=60, history=False,
            note='混合通知栏目，按标题保留同站招录信息；省政府专题等外链未纳入，当前展示1000条，较早档案范围未获证明。'),
    _source('qh_hr_recruit', '青海', '青海省人力资源和社会保障厅', '事业单位招聘考录动态',
            'https://rst.qinghai.gov.cn/ztzl/kldt/index.html', '事业单位', pages=30,
            note='现存目录更新较稀疏；不替代青海省人事考试信息网及各州、市招录单位。'),
    _source('gs_exam_recruit', '甘肃', '甘肃人事考试网', '公务员、事业单位考试',
            'https://ks.rst.gansu.gov.cn/ncms/wzlb.shtml?mkbh=gwysydwks', pages=30,
            note='考试组织信息栏目，包含本省考区信息；不等同于甘肃组工网或各招聘单位录聘公示。'),
    _source('nx_exam_civil', '宁夏', '宁夏回族自治区人事考试中心', '公务员考试',
            'https://www.nxpta.com/gwyks/', '省考', pages=60,
            history=False, note='仅同站HTML公告；栏目直接指向附件的条目及站外转载未纳入。',
            provenance='https://hrss.nx.gov.cn/'),
    _source('nx_exam_recruit', '宁夏', '宁夏回族自治区人事考试中心', '事业单位招考',
            'https://www.nxpta.com/sydwzk/', '事业单位', pages=40,
            history=False, note='仅同站HTML公告；栏目直接指向附件的条目及站外转载未纳入。',
            provenance='https://hrss.nx.gov.cn/'),
    _source('xj_hr_civil', '新疆', '新疆维吾尔自治区人力资源和社会保障厅', '公务员招录',
            'https://rst.xinjiang.gov.cn/xjrst/c112678/zfxxgk_gknrz.shtml', '省考', pages=30,
            note='本栏目更新较稀疏，部分本省考区公告属于中央考试。'),
    _source('xj_hr_recruit', '新疆', '新疆维吾尔自治区人力资源和社会保障厅', '事业单位',
            'https://rst.xinjiang.gov.cn/xjrst/c112746/list.shtml', '事业单位', pages=90,
            note='栏目内另有公务员招录转载，按标题明确类别；含目录当前提供的历史分页。'),
    _source('bt_exam_civil', '兵团', '兵团考试信息网', '公务员招录考试',
            'https://btpta.xjbt.gov.cn/gwyzl/', '省考', pages=10,
            history=False, note='仅同站公告及最多10个静态目录页；站外转载未纳入，目录10页之后切换另一分页接口，尚未接入。'),
    _source('bt_exam_recruit', '兵团', '兵团考试信息网', '事业单位招聘考试',
            'https://btpta.xjbt.gov.cn/wjgb/', '事业单位', pages=10,
            history=False, note='仅已验证的前10个静态目录页；目录10页之后切换另一分页接口，尚未接入。'),
]

# These two official columns also repost other exam categories. Keep collection
# eligible for each selected category, while retaining their default row type.
for _source_item in EXPANSION_WEST_SOURCES:
    if _source_item['id'] in {'xj_hr_civil','xj_hr_recruit'}:
        _source_item['default_kind'] = _source_item['kind']
        _source_item['kind'] = ''

_SOURCES = {s['id']: s for s in EXPANSION_WEST_SOURCES}
_TRS_ARTICLE = r'/\d{6}/t\d{8}_\d+\.html?$'
_LAYOUTS = {
    'gz_hr_recruit': ('trs0', '.right-list-box li', 'a[href]', 'span', _TRS_ARTICLE),
    'yn_hr_recruit': ('yn', '.listBox ul.ul13 > li', 'a[href]', 'span', r'^/NewsView\.aspx$'),
    'yn_gov_civil': ('trs0', '.wjer_list > li', 'a[href]', 'span:last-child', _TRS_ARTICLE),
    'xz_hr_notices': ('trs0', '.gl-list > .gl-list-item', 'a.nm', '.date', _TRS_ARTICLE),
    'sn_hr_notices': ('trs0', 'ul.list > li.list-item', 'a[href]', '.time', _TRS_ARTICLE),
    'qh_hr_recruit': ('qh', 'ul.list > li', 'a[href]', 'span', r'^/ztzl/kldt/query/\d+\.html$'),
    'gs_exam_recruit': ('gs', 'ul.ap > li', 'a[href]', '.you', r'^/ncms/article_(?:[a-f0-9]{32}|N\d{12})\.shtml$'),
    'nx_exam_civil': ('trs0', '.content > p.title-li', 'a[href]', 'span', _TRS_ARTICLE),
    'nx_exam_recruit': ('trs0', '.content > p.title-li', 'a[href]', 'span', _TRS_ARTICLE),
    'xj_hr_civil': ('trs1', '.gknr_list dl > dd', 'a[href]', 'span', r'^/xjrst/c\d+/\d{6}/[a-f0-9]{32}\.shtml$'),
    'xj_hr_recruit': ('trs1', '.com-pic-news-list > li', 'a.cpn-title', '.cpn-date', r'^/xjrst/c\d+/\d{6}/[a-f0-9]{32}\.shtml$'),
    'bt_exam_civil': ('bt', '.right_wrap .con > ul > li', 'a[href]', '.fr', r'^/c/\d{4}-\d{2}-\d{2}/\d+\.shtml$'),
    'bt_exam_recruit': ('bt', '.right_wrap .con > ul > li', 'a[href]', '.fr', r'^/c/\d{4}-\d{2}-\d{2}/\d+\.shtml$'),
}
_MIXED = {'xz_hr_notices', 'sn_hr_notices'}
_RECRUITMENT = re.compile(r'公务员|招考|招录|招聘|遴选|选调|引进.{0,8}人才|拟.{0,8}(?:录用|聘)')


def _same_host(url, base):
    try:
        p, b = urlparse(url), urlparse(base)
        return (p.scheme == 'https' and p.hostname == b.hostname
                and p.port in (None, 443) and not p.username and not p.password
                and not p.fragment)
    except ValueError:
        return False


def _static_page(url, base, prefix, suffix, first):
    """Read a known list path only; announcement paths cannot be pagination."""
    if not _same_host(url, base) or urlparse(url).query:
        raise ValueError('目录请求已离开固定官方栏目')
    folder = urlparse(urljoin(base, './')).path
    match = re.fullmatch(re.escape(folder) + re.escape(prefix)
                         + r'(?:_([1-9]\d*))?\.' + re.escape(suffix), urlparse(url).path)
    if url == base and urlparse(base).path.endswith('/'):
        return first
    if not match:
        raise ValueError('目录路径或页码格式变化')
    return int(match[1]) if match[1] else first


def _one(pattern, text, message):
    values = re.findall(pattern, text)
    if len(values) != 1:
        raise ValueError(message)
    return values[0]


def _pager(html, soup, source, url, style):
    script = '\n'.join(n.get_text() for n in soup.find_all('script') if not n.get('src'))
    if style in ('trs0', 'trs1'):
        if style == 'trs0':
            count, current, prefix, ext = _one(
                r'''\bcreatePage(?:HTML)?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*["'](index)["']\s*,\s*["'](html)["'](?:\s*,\s*\d+)?\s*\)''',
                script, '官方目录分页参数变化，不能视为零条或完整历史')
            first = 0
        else:
            count, current, prefix, ext = _one(
                r'''\bcreatePageHTML\(\s*["']page[_-]div["']\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*["'](list|zfxxgk_gknrz)["']\s*,\s*["'](shtml)["']\s*,\s*\d+\s*\)''',
                script, '新疆目录分页参数变化，不能视为完整历史')
            first = 1
        count, current = int(count), int(current)
        requested = _static_page(url, source['url'], prefix, ext, first)
        if not 1 <= count <= 10000 or current != requested or not first <= current < count + first:
            raise ValueError('官网返回页码与请求不一致或目录总数无效')
        return urljoin(source['url'], f'{prefix}_{current+1}.{ext}') if current + 1 < count + first else None
    if style == 'yn':
        q = parse_qs(urlparse(url).query)
        if (not _same_host(url, source['url']) or urlparse(url).path != '/NewsLsit.aspx'
                or q.get('ClassID') != ['602'] or set(q) - {'ClassID', 'page'}):
            raise ValueError('云南请求目录或类别无效')
        requested = q.get('page', ['1'])
        pager = soup.select_one('#Body_AspNetPager1')
        if not pager or len(requested) != 1 or not requested[0].isdigit():
            raise ValueError('云南目录页码结构变化')
        current, count = _one(r'第\s*(\d+)\s*页\s*共\s*(\d+)\s*页', pager.get_text(' ', strip=True), '云南目录页码缺失')
        current, count = int(current), int(count)
        if current != int(requested[0]) or not 1 <= current <= count <= 10000:
            raise ValueError('云南官网返回页码与请求不一致')
        # Validate the actual next link as well as the displayed current page.
        if current < count:
            a = next((a for a in pager.select('a[href]') if a.get_text(strip=True) == '下一页'), None)
            target = urljoin(url, a['href']) if a else ''
            expected = source['url'] + f'&page={current+1}'
            if target != expected:
                raise ValueError('云南下一页目录地址变化')
            return target
        return None
    if style == 'qh':
        if not _same_host(url, source['url']) or urlparse(url).query:
            raise ValueError('青海目录地址无效')
        m = re.fullmatch(r'/ztzl/kldt/(?:index\.html|list/([1-9]\d*)\.html)', urlparse(url).path)
        cur = soup.select_one('span.current')
        if not m or not cur or not cur.get_text(strip=True).isdigit():
            raise ValueError('青海目录分页结构变化')
        current = int(cur.get_text(strip=True))
        tail = next((a for a in cur.parent.select('a[href]') if a.get_text(strip=True) == '尾页'), None)
        target = urljoin(url, tail['href']) if tail else ''
        last = re.fullmatch(r'https://rst\.qinghai\.gov\.cn/ztzl/kldt/list/([1-9]\d*)\.html', target)
        if not last or current != int(m[1] or '1') or not 1 <= current <= int(last[1]) <= 10000:
            raise ValueError('青海官网返回页码或尾页地址变化')
        return urljoin(source['url'], f'list/{current+1}.html') if current < int(last[1]) else None
    if style == 'gs':
        q = parse_qs(urlparse(url).query)
        if (not _same_host(url, source['url']) or urlparse(url).path != '/ncms/wzlb.shtml'
                or q.get('mkbh') != ['gwysydwks'] or set(q) - {'mkbh', 'begin', 'pagenum'}):
            raise ValueError('甘肃目录类别或地址变化')
        count = int(_one(r'''\bvar\s+dataTotal\s*=\s*parseInt\(["'](\d+)["']\)''', script, '甘肃目录总数缺失'))
        current = int(_one(r'''\bvar\s+pagenum\s*=\s*parseInt\(["'](\d+)["']\)''', script, '甘肃目录当前页缺失'))
        if (not 1 <= count <= 150000 or q.get('pagenum', ['1']) != [str(current)]
                or q.get('begin', ['0']) != [str((current-1)*15)]
                or not 1 <= current <= (count+14)//15
                or 'wzlb.shtml?mkbh=gwysydwks&begin=' not in script):
            raise ValueError('甘肃目录页码或分页接口变化')
        return source['url'] + f'&begin={current*15}&pagenum={current+1}' if current*15 < count else None
    if style == 'bt':
        current = _static_page(url, source['url'], 'index', 'shtml', 1)
        page_input, page_count = soup.select_one('#PageInp'), soup.select_one('.pageCount')
        if not page_input or not page_count or page_input.get('value') != str(current):
            raise ValueError('兵团目录返回页码与请求不一致')
        count = page_count.get_text(strip=True)
        limits = re.findall(r'PageIndex=PageIndex>(\d+)\?(\d+):PageIndex', script)
        if (not count.isdigit() or limits != [(count, count)]
                or not 1 <= current <= int(count) <= 10000
                or "'index_${PageIndex}.shtml'" not in script):
            raise ValueError('兵团目录分页总数或格式变化')
        # The registered source explicitly reports partial once it reaches this
        # verified static segment. Do not fabricate an unverified dynamic URL.
        return urljoin(source['url'], f'index_{current+1}.shtml') if current < min(int(count), 10) else None
    raise ValueError('未登记的西部目录分页类型')


def parse_expansion_west(html, source, url):
    """Return known-directory metadata rows and the next directory URL."""
    registered = _SOURCES.get(source.get('id'))
    if not registered or source['url'] != registered['url']:
        raise ValueError('未登记或已变更的西部官方来源')
    from .notices import exam_year_from_title, stage

    style, selector, anchor_selector, date_selector, article_pattern = _LAYOUTS[source['id']]
    soup = BeautifulSoup(html, 'html.parser')
    next_url = _pager(html, soup, source, url, style)
    rows, recognized = {}, 0
    for node in soup.select(selector):
        a = node.select_one(anchor_selector)
        if not a or not a.get('href'):
            continue
        target = urljoin(url, a['href']).split('#')[0]
        if not _same_host(target, source['url']):
            continue
        parsed = urlparse(target)
        if not re.search(article_pattern, parsed.path):
            continue
        if style == 'yn':
            q = parse_qs(parsed.query)
            if (set(q) != {'NewsID', 'ClassID'} or q['ClassID'] != ['602']
                    or len(q['NewsID']) != 1 or not q['NewsID'][0].isdigit()):
                continue
        elif parsed.query:
            continue
        elif style == 'trs0' and not parsed.path.startswith(urlparse(source['url']).path):
            continue
        title_node = a.select_one('.text') if source['id'] == 'sn_hr_notices' else None
        title = (a.get('title') or (title_node or a).get_text(' ', strip=True)).strip()
        if not 1 <= len(title) <= 500:
            raise ValueError('官方目录公告标题缺失或异常，需要维护来源')
        recognized += 1
        if source['id'] in _MIXED and not _RECRUITMENT.search(title):
            continue
        date_node = node.select_one(date_selector)
        found = re.search(r'(?<!\d)(20\d{2})[-年./](\d{1,2})[-月./](\d{1,2})(?:日)?', date_node.get_text(' ', strip=True) if date_node else '')
        published = None
        if found:
            try:
                published = date(*map(int, found.groups())).isoformat()
            except ValueError:
                pass
        kind = source.get('default_kind', source['kind'])
        if '事业单位' in title:
            kind = '事业单位'
        elif '公务员' in title:
            kind = '国考' if re.search(r'中央(?:机关|国家机关)|国家公务员', title) else '省考'
        rows[target] = dict(id=hashlib.sha256(target.encode()).hexdigest(), source_id=source['id'],
                            source=source['name'], owner=source['owner'], title=title, url=target,
                            published=published, exam_year=exam_year_from_title(title), kind=kind,
                            region=source['region'], stage=stage(title))
    if not recognized:
        raise ValueError('未识别到有效官方公告目录，不能视为零条公告或完整历史')
    return list(rows.values()), next_url
