"""Verified eastern/central official directories; no article or attachment requests."""
import hashlib
import json
import re
from datetime import date
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup


def _source(sid, name, owner, url, region, kind='事业单位', pages=120, history=True, note=''):
    return dict(id=sid, name=name, owner=owner, url=url, region=region,
                kind=kind, area_scope='province', max_pages=pages, history=history,
                note=note, history_note=note if not history else '')


EXPANSION_EAST_SOURCES = [
    _source('shanghai_hires', '上海市人社局 · 拟聘人员公示', '上海市人力资源和社会保障局',
            'https://rsj.sh.gov.cn/tnprygs_17409/index.html', '上海', history=False,
            note='上海事业单位拟聘目录；最多读取120页。官网标称第322页、321页实测404，历史目录存在缺口，不代表全部招录主体。'),
    _source('shanghai_jobs', '上海市人社局 · 招聘公告', '上海市人力资源和社会保障局',
            'https://rsj.sh.gov.cn/tzpgg_17408/index.html', '上海',
            note='上海事业单位招聘公告目录；最多120页，当前官网标称224页，更早历史未覆盖。'),
    _source('jiangsu_jobs', '江苏省人社厅 · 省属事业单位招聘', '江苏省人力资源和社会保障厅',
            'https://jshrss.jiangsu.gov.cn/col/col78506/index.html', '江苏', pages=1, history=False,
            note='只读取首页内嵌60条目录；历史动态分组尚未接通，部分官网标题已截短，不读取详情补全。'),
    _source('anhui_jobs', '安徽省人社厅 · 省直事业单位公开招聘', '安徽省人力资源和社会保障厅',
            'https://hrss.ah.gov.cn/zxzx/ztzl/ahssydwgkzp/index.html', '安徽',
            note='省直招聘公告及专业测试等目录，含当前官网现存分页；不等同各单位拟聘公示汇总。'),
    _source('anhui_college', '安徽省人社厅 · 省属高校公开招聘', '安徽省人力资源和社会保障厅',
            'https://hrss.ah.gov.cn/zxzx/ztzl/ahsszsydwgkzpzl/ssgxgkzp/index.html', '安徽',
            note='省人社厅汇集的高校招聘目录，不代表高校网站全部拟聘公告。'),
    _source('anhui_city', '安徽省人社厅 · 各市及省直管县公开招聘', '安徽省人力资源和社会保障厅',
            'https://hrss.ah.gov.cn/zxzx/ztzl/ahsszsydwgkzpzl/gsszgxgkzp/index.html', '安徽', history=False,
            note='省人社厅转载的市县招聘栏目，大量站外公告被排除，末页可全部为站外链接；这些市县原站及其公示仍未接入。'),
    _source('hubei_gwy_notice', '湖北人事考试网 · 公务员考试重要通知', '湖北省人事考试院',
            'https://rst.hubei.gov.cn/hbrsksw/zlplks/jglyks/hbsgwyks/zytz/', '湖北', kind='省考', history=False,
            note='湖北公务员栏目现存目录；直接链接的人员名单附件不索引，末页可因全部为附件而返回零条网页链接。'),
    _source('hubei_jobs', '湖北省人社厅 · 省直事业单位招聘公告', '湖北省人力资源和社会保障厅',
            'https://rst.hubei.gov.cn/bmdt/ztzl/ywzl/hbsszsydwgkzp/zpgg/', '湖北',
            note='省直事业单位招聘公告目录，含现存历史分页；并非全部拟聘公示。'),
    _source('hubei_hires', '湖北省人社厅 · 省直事业单位招聘人员公示', '湖北省人力资源和社会保障厅',
            'https://rst.hubei.gov.cn/bmdt/ztzl/ywzl/hbsszsydwgkzp/zprygs/', '湖北',
            note='此官网栏目实测仅3条、最新为2025年10月，2026年及各单位另行发布的公示仍有缺口。'),
    _source('zhejiang_huzhou_hires', '湖州组织工作 · 公务员录用公示', '中共湖州市委组织部',
            'https://zzb.huzhou.gov.cn/gbgz/gwykl/lygs/index.html', '浙江', kind='省考', pages=1, history=False,
            note='仅湖州公务员录用及遴选公示，读取当前HTML内嵌目录；更大目录的远程分页尚未接通，不能代表浙江全省。'),
    _source('henan_hr_recruit', '河南省人社厅 · 招考录用', '河南省人力资源和社会保障厅',
            'https://hrss.henan.gov.cn/zwgk/xxgk/yfygkdqtxx/zkly/', '河南', kind='', pages=1, history=False,
            note='仅省人社厅及所属单位招考录用首页24条；历史分页脚本跨域，本轮未接通，类型不明确的保留未知。'),
    _source('shandong_jobs', '山东省人社厅 · 省属事业单位公开招聘服务平台', '山东省人力资源和社会保障厅',
            'https://hrss.shandong.gov.cn/channels/ch00232/', '山东', pages=1,
            note='当前470条目录全部内嵌在一个HTML，页面内按20条切换；校验记录总数，若增长到需远程分页则报错提示维护。'),
    _source('fujian_forest_recruit', '福建省林业局 · 考录招聘', '福建省林业局',
            'https://lyj.fj.gov.cn/zwgk/rsgl/klzp/', '福建', kind='', pages=1, history=False,
            note='仅林业局考录招聘栏目内嵌目录；动态历史及筛选未接通，过滤与招聘无关的人事任免，不代表全省。'),
    _source('hunan_jobs', '湖南省人社厅 · 事业单位招聘', '湖南省人力资源和社会保障厅',
            'https://rst.hunan.gov.cn/rst/xxgk/zpzl/sydwzp/', '湖南',
            note='省人社厅事业单位招聘及拟聘公示目录，官网现存25页500条；不代表各市县、全部用人单位或已撤下历史。'),
    _source('jiangxi_jingdezhen_recruit', '景德镇市政府 · 招考录用', '景德镇市人民政府办公室',
            'https://www.jdz.gov.cn/zwgk/fdzdgknr/rsxx/zkly/', '江西', kind='', history=False,
            note='仅景德镇市政府招考录用目录，包含事业单位招聘、公示和省公务员考试转载；站外公告未纳入，不是江西省人社厅目录，也不代表全省。'),
]
_SOURCES = {s['id']: s for s in EXPANSION_EAST_SOURCES}
_ANHUI = {'anhui_jobs': '6791573', 'anhui_college': '6791574', 'anhui_city': '6791575'}
_ATTACHMENT = re.compile(r'\.(?:pdf|docx?|xlsx?|zip|rar|png|jpe?g|gif)$', re.I)
_RECRUITMENT = re.compile(r'公务员|招考|招录|招聘|遴选|选调|拟.*(?:录用|聘用|聘人员|聘人选)|(?:录用|聘用).*公示')


def _fail(message):
    raise ValueError(message + '，不能当作目录已查完')


def _request(source, url):
    p, b = urlparse(url), urlparse(source['url'])
    if (p.scheme != 'https' or p.hostname != b.hostname or p.port not in (None, 443)
            or p.username or p.password or p.fragment):
        _fail('扩展目录请求地址不在固定官方来源内')
    return p, b


def _target(href, source, pattern):
    p = urlparse(urljoin(source['url'], str(href).strip()))
    # Legacy same-host HTTP links are upgraded; no HTTP request is performed.
    if p.scheme not in ('http', 'https') or p.hostname != urlparse(source['url']).hostname:
        return None  # External links and javascript actions are deliberately excluded.
    if p.username or p.password or p.port not in (None, 80 if p.scheme == 'http' else 443):
        _fail('公告链接包含异常认证或端口')
    if _ATTACHMENT.search(p.path):
        return None  # Do not index or request personnel-list attachments.
    if p.query or not re.fullmatch(pattern, p.path):
        _fail('官方目录公告链接格式已变化')
    return f'https://{p.hostname}{p.path}'


def _date(text):
    m = re.fullmatch(r'(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})', str(text).strip())
    if m:
        try:
            return date(*map(int, m.groups())).isoformat()
        except ValueError:
            pass
    return None


def _title(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 500:
        _fail('公告标题为空或长度异常')
    return re.sub(r'\s+', ' ', value.strip())


def _item(source, target, title, published):
    from .notices import exam_year_from_title, stage
    title = _title(title)
    kind = source['kind']
    if not kind:
        kind = '省考' if '公务员' in title else ('事业单位' if '事业单位' in title else '')
    return dict(id=hashlib.sha256(target.encode()).hexdigest(), source_id=source['id'],
                source=source['name'], owner=source['owner'], url=target, title=title,
                published=_date(published), exam_year=exam_year_from_title(title),
                region=source['region'], kind=kind, stage=stage(title))


def _anchor_title(anchor, date_selector):
    if anchor.get('title', '').strip():
        return _title(anchor['title'])
    copy = BeautifulSoup(str(anchor), 'html.parser')
    for stamp in copy.select(date_selector):
        stamp.decompose()
    return _title(copy.get_text(' ', strip=True))


def _rows(soup, selector, source, pattern, date_selector, row_tag='li', filter_recruit=False):
    containers = soup.select(selector)
    if not containers:
        _fail('公告目录容器已变化')
    candidates = [row for container in containers for row in container.find_all(row_tag, recursive=False)]
    if not candidates:
        _fail('公告目录为空或结构已变化')
    items = {}
    for row in candidates:
        if (row.get('class') == ['lm_line'] and not row.get_text(strip=True) and not row.find('a')):
            continue  # Anhui's empty separator after each five actual rows.
        if row.has_attr('ms-repeat'):
            continue  # Fujian's unrendered Avalon template has no announcement.
        a = row.find('a', href=True)
        if a is None:
            _fail('已识别的公告条目缺少链接')
        href = a['href']
        if '{{' in href:  # Unrendered dynamic template is not an announcement.
            continue
        target = _target(href, source, pattern)
        if target is None:
            continue
        title = _anchor_title(a, date_selector)
        if filter_recruit and not _RECRUITMENT.search(title):
            continue
        stamp = row.select_one(date_selector)
        items[target] = _item(source, target, title, stamp.get_text(strip=True) if stamp else '')
    return list(items.values()), len(candidates)


def _static_pager(html, source, url, family):
    p, b = _request(source, url)
    root = b.path.rsplit('/', 1)[0] + '/' if b.path.endswith('index.html') else b.path
    if family == 'shanghai':
        m = re.fullmatch(re.escape(root) + r'index(?:_([2-9]\d*|1\d+))?\.html', p.path)
        matches = re.findall(r'\.pagination\(\s*["\']setPage["\']\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', html)
        expected = int(m[1]) if m and m[1] else 1
        if not m or p.query or len(matches) != 1:
            _fail('上海目录页码结构已变化')
        current, total = map(int, matches[0])
        totals = re.findall(r'\btotalPage\s*:\s*(\d+)', html)
        if totals != [str(total)] or current != expected or not 1 <= current <= total <= 10000:
            _fail('上海返回页码或总页数与请求不一致')
        return urljoin(source['url'], f'index_{current + 1}.html') if current < total else None
    m = re.fullmatch(re.escape(root) + r'(?:index(?:_([1-9]\d*))?\.shtml)?', p.path)
    matches = re.findall(r'createPageHTML\(\s*(\d+)\s*,\s*(\d+)\s*,\s*["\']index["\']\s*,\s*["\']shtml["\']\s*,\s*["\']black2["\']\s*,\s*(\d+)\s*\)', html)
    if not m or p.query or len(matches) != 1:
        _fail(f"{source['region']}目录分页结构已变化")
    total, current, _ = map(int, matches[0])
    if current != (int(m[1]) if m[1] else 0) or not 0 <= current < total <= 10000:
        _fail(f"{source['region']}返回页码与请求不一致")
    return urljoin(source['url'], f'index_{current + 1}.shtml') if current + 1 < total else None


def _anhui(html, soup, source, url):
    p, _ = _request(source, url)
    cid = _ANHUI[source['id']]
    scripts = [x.get_text() for x in soup.find_all('script') if f'Ls.pagination("#page_{cid}"' in x.get_text()]
    if len(scripts) != 1:
        _fail('安徽目录分页配置缺失')
    script = scripts[0]
    current = re.search(r'currPage:\s*\((\d+)\+1\)', script)
    total = re.search(r'pageCount:\s*(\d+)', script)
    prefix = f'https://hrss.ah.gov.cn/content/column/{cid}?pageIndex='
    if not current or not total or prefix not in script:
        _fail('安徽目录分页参数变化')
    page, pages = int(current[1]) + 1, int(total[1])
    if url == source['url']:
        expected = 1
    elif p.path == f'/content/column/{cid}' and re.fullmatch(r'pageIndex=[1-9]\d*', p.query):
        expected = int(parse_qs(p.query)['pageIndex'][0])
    else:
        _fail('安徽目录请求页码无效')
    if page != expected or not 1 <= page <= pages <= 10000:
        _fail('安徽返回页码与请求不一致')
    root = re.escape(urlparse(source['url']).path.rsplit('/', 1)[0])
    rows, _ = _rows(soup, f'ul.doc_list.list-{cid}', source, root + r'/\d+\.html', '.date')
    return rows, prefix + str(page + 1) if page < pages else None


def _inline_json(html, name):
    matches = list(re.finditer(r'\bvar\s+' + re.escape(name) + r'\s*=\s*', html))
    if len(matches) != 1:
        _fail('内嵌公告目录数据缺失或重复')
    try:
        data, _ = json.JSONDecoder().raw_decode(html[matches[0].end():])
        return data
    except (ValueError, TypeError):
        _fail('内嵌公告目录JSON无效')


def parse_expansion_east(html, source, url):
    if source['id'] not in _SOURCES:
        _fail('未知的东中部官方来源')
    # Keep source IDs bound to their registered official URL.
    if source['url'] != _SOURCES[source['id']]['url']:
        _fail('来源网址与固定配置不一致')
    _request(source, url)
    soup = BeautifulSoup(html, 'html.parser')
    sid = source['id']
    if sid in _ANHUI:
        return _anhui(html, soup, source, url)
    if sid.startswith('shanghai_'):
        next_url = _static_pager(html, source, url, 'shanghai')
        root = re.escape(urlparse(source['url']).path.rsplit('/', 1)[0])
        rows, _ = _rows(soup, 'ul.uli14.list-date', source, root + r'/\d{8}/t\d+_\d+\.html', '.time')
        return rows, next_url
    if sid.startswith('hubei_'):
        next_url = _static_pager(html, source, url, 'hubei')
        root = re.escape(urlparse(source['url']).path)
        rows, _ = _rows(soup, 'ul.list-t', source, root + r'\d{6}/t\d{8}_\d+\.shtml', '.date')
        return rows, next_url
    if sid == 'jiangxi_jingdezhen_recruit':
        next_url = _static_pager(html, source, url, 'trs')
        root = re.escape(urlparse(source['url']).path)
        rows, _ = _rows(soup, 'ul.info-list', source, root + r't\d+\.shtml', 'span[name="PushDate"]')
        return rows, next_url
    if sid == 'hunan_jobs':
        p, b = _request(source, url)
        requested = re.fullmatch(re.escape(b.path) + r'(?:index(?:_([2-9]\d*|1\d+))?\.html)?', p.path)
        matches = re.findall(r"createPageHTML\(\s*['\"]paging['\"]\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*['\"]index['\"]\s*,\s*['\"]html['\"]\s*,\s*(\d+)\s*\)", html)
        if not requested or p.query or len(matches) != 1:
            _fail('湖南目录分页结构已变化')
        pages, page, _ = map(int, matches[0])
        if page != (int(requested[1]) if requested[1] else 1) or not 1 <= page <= pages <= 10000:
            _fail('湖南目录返回页码与请求不一致')
        rows, _ = _rows(soup, '.xxgkzd-box > .box > ul', source,
                        re.escape(b.path) + r'\d{6}/t\d{8}_\d+\.html', 'span')
        return rows, urljoin(source['url'], f'index_{page + 1}.html') if page < pages else None
    if url != source['url']:
        _fail('仅支持已核验的内嵌目录首页')
    if sid == 'jiangsu_jobs':
        blocks = [s.get_text() for s in soup.find_all('script', type='text/xml') if '<datastore>' in s.get_text()]
        if len(blocks) != 1 or 'columnid:78506' not in html or 'unitid:' not in html:
            _fail('江苏内嵌目录标识已变化')
        records = re.findall(r'<record><!\[CDATA\[(.*?)\]\]></record>', blocks[0], re.S)
        if not records:
            _fail('江苏内嵌目录记录为空')
        fragment = BeautifulSoup('<ul>' + ''.join(records) + '</ul>', 'html.parser')
        if len(fragment.select('ul > li')) != len(records):
            _fail('江苏目录记录与HTML条目数量不一致')
        rows, _ = _rows(fragment, 'ul', source, r'/art/\d{4}/\d{1,2}/\d{1,2}/art_78506_\d+\.html', 'i')
        return rows, None
    if sid == 'zhejiang_huzhou_hires':
        groups, pages = _inline_json(html, 'dataList'), _inline_json(html, 'pagesData')
        if (not isinstance(groups, list) or not groups or not isinstance(pages, dict)
                or pages.get('curPageNo') != 1 or not isinstance(pages.get('pageTotal'), int)
                or not len(groups) <= pages['pageTotal'] <= 10000):
            _fail('湖州目录分组结构异常')
        rows = {}
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get('infolist'), list) or not group['infolist']:
                _fail('湖州目录分组记录为空或异常')
            for entry in group['infolist']:
                if not isinstance(entry, dict) or entry.get('channelid') != 68873 or not isinstance(entry.get('url'), str):
                    _fail('湖州公告条目结构变化')
                target = _target(entry['url'], source, r'/gbgz/gwykl/lygs/\d{8}/i\d+\.html')
                if target:
                    rows[target] = _item(source, target, entry.get('title'), entry.get('daytime', ''))
        return list(rows.values()), None
    if sid == 'henan_hr_recruit':
        pager = soup.select_one('#pageDec[pagesize][pagecount]')
        if not pager or not str(pager.get('pagecount')).isdigit():
            _fail('河南目录分页标记缺失')
        rows = {}
        for a in soup.select('td.xin2zuo table a[href]'):
            target = _target(a['href'], source, r'/\d{4}/\d{2}-\d{2}/\d+\.html')
            if target:
                row = a.find_parent('tr')
                stamps = re.findall(r'20\d\d-\d\d-\d\d', row.get_text(' ', strip=True))
                rows[target] = _item(source, target, a.get('title') or a.get_text(' ', strip=True), stamps[-1] if stamps else '')
        if not rows:
            _fail('河南目录未识别到公告')
        return list(rows.values()), None
    if sid == 'shandong_jobs':
        values = {}
        for field in ('totalCount', 'perSize', 'startPage', 'endPage', 'logicTotalPage'):
            m = re.findall(r'\bvar\s+' + field + r'\s*=\s*(\d+)\s*;', html)
            if len(m) != 1:
                _fail('山东内嵌分页参数变化')
            values[field] = int(m[0])
        nodes = soup.select('.pagedContent')
        if (not nodes or len(nodes) != values['totalCount'] or values['perSize'] < 1
                or values['startPage'] != 1 or values['endPage'] != values['logicTotalPage']
                or (len(nodes) + values['perSize'] - 1) // values['perSize'] != values['logicTotalPage']):
            _fail('山东HTML未包含全部声明目录或需要远程分页')
        rows = {}
        for node in nodes:
            a, stamp = node.find('a', href=True), node.select_one('a > span:not(.news_box01_title)')
            if not a:
                _fail('山东公告条目缺少链接')
            target = _target(a['href'], source, r'/(?:rsks/)?articles/ch\d+/\d{6}/[a-fA-F0-9-]+\.shtml')
            if target:
                rows[target] = _item(source, target, _anchor_title(a, 'span:not(.news_box01_title)'), stamp.get_text(strip=True) if stamp else '')
        return list(rows.values()), None
    if sid == 'fujian_forest_recruit':
        if 'list2.trsapi' not in html or not re.search(r"recordCount:\s*['\"]\d+['\"]", html):
            _fail('福建考录招聘内嵌目录结构变化')
        rows, _ = _rows(soup, 'ul.gl-ul', source,
                        r'/(?:zwgk|xxgk)/.*/\d{6}/t\d{8}_\d+\.html?', '.li-btn', filter_recruit=True)
        return rows, None
    _fail('东中部目录适配器未配置')
