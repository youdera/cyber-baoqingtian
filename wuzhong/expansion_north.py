"""Reviewed official directory adapters; never request announcement details."""
import hashlib
import re
from datetime import date
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def _source(sid, name, owner, url, region, kind, history=True, note='', **extra):
    return dict(id=sid, name=name, owner=owner, url=url, region=region,
                kind=kind, area_scope='province', max_pages=120 if history else 1,
                history=history, note=note, **extra)


EXPANSION_NORTH_SOURCES = [
    _source('beijing_hr_jobs', '北京市人社局 · 事业单位公开招聘', '北京市人力资源和社会保障局',
            'https://rsj.beijing.gov.cn/xxgk/gkzp/', '北京', '事业单位',
            note='只覆盖市人社局当前公开招聘目录；不代表各区、各单位全部拟聘公示及已撤下历史。'),
    _source('tianjin_hr_jobs', '天津市人社局 · 事业单位公开招聘', '天津市人力资源和社会保障局',
            'https://hrss.tj.gov.cn/ztzl/ztzl1/sydwgkzp/', '天津', '事业单位',
            note='本栏目多为招聘信息汇总公告；不展开汇总正文中的单位链接，不代表全部拟聘公示。'),
    _source('jilin_hr_jobs', '吉林省人社厅 · 公开招聘公告', '吉林省人力资源和社会保障厅',
            'https://hrss.jl.gov.cn/rsrc/sydwrsgl/gkzp/index.html', '吉林', '事业单位',
            note='只覆盖省人社厅公开招聘公告栏目；各市县及各招聘单位另行发布的公示仍有缺口。'),
    _source('jilin_hr_notices', '吉林省人社厅 · 招录相关公示', '吉林省人力资源和社会保障厅',
            'https://hrss.jl.gov.cn/gs/index.html', '吉林', '', False,
            note='综合公示栏目中仅收录标题可识别的招录公告；本次当前页无匹配，搜索缓存中的旧招录公示已不在当前目录。',
            history_note='吉林综合公示仅有一页；搜索缓存曾列出的招录公示已不在当前目录，历史缺口明确，不能把当前零条理解为没有招录。'),
    _source('liaoning_gwy_notices', '辽宁人事考试网 · 公务员公示', '辽宁省人事考试中心',
            'https://www.lnrsks.com/html/gwy_gongshixinxi/', '辽宁', '省考',
            note='仅公务员考试公示信息栏目现存分页；各市另行发布的拟录用公示仍需独立接入。'),
    _source('liaoning_sydw_notices', '辽宁人事考试网 · 事业单位公示', '辽宁省人事考试中心',
            'https://www.lnrsks.com/html/sydw_gongshixinxi/', '辽宁', '事业单位', False,
            note='仅现存事业单位公示栏目；官网可见第30页仍满10条，更早历史未经证实。',
            history_note='辽宁事业单位公示官网可见分页止于第30页且末页仍满10条；更早历史未核验。'),
    _source('liaoning_sydw_jobs', '辽宁人事考试网 · 事业单位招聘公告', '辽宁省人事考试中心',
            'https://www.lnrsks.com/html/sydw_zhaopingonggao/', '辽宁', '事业单位', False,
            note='仅现存招聘公告栏目；官网可见第30页仍满10条，更早历史未经证实。',
            history_note='辽宁事业单位招聘官网可见分页止于第30页且末页仍满10条；更早历史未核验。'),
    _source('guangxi_gwy_2026_notices', '广西人事考试网 · 2026公务员录用公示', '广西壮族自治区人事考试院',
            'https://www.gxpta.com.cn/ksxm/gwyzlks/gx2026ndkslygwyxdszt/2026nlygs/', '广西', '省考',
            note='只覆盖2026年度专题的录用公示栏目；2027及后续年度需核验新栏目后接入，不代表各市全部公告。'),
    _source('guangxi_gwy_2025_notices', '广西人事考试网 · 2025公务员录用公示', '广西壮族自治区人事考试院',
            'https://www.gxpta.com.cn/ksxm/gwyzlks/gx2025ndkslygwyxdszt/2025nlygs/', '广西', '省考',
            note='只覆盖2025年度专题的录用公示栏目；更早年度及各市另行发布公告尚未接入。'),
    _source('guangxi_sydw_jobs', '广西人事考试网 · 区直事业单位招聘', '广西壮族自治区人事考试院',
            'https://www.gxpta.com.cn/ksxm/sydwzpks/', '广西', '事业单位',
            note='仅自治区直属事业单位招聘栏目现存分页；不代表各市县事业单位、医院高校全部公告。'),
    _source('heilongjiang_hr_notices', '黑龙江省人社厅 · 招录相关通知公告', '黑龙江省人力资源和社会保障厅',
            'https://hrss.hlj.gov.cn/hrss/c111741/list.shtml', '黑龙江', '', False,
            note='仅静态首页中标题可识别的招录公告；公开分页接口夹带正文字段，本适配器未接该接口。',
            history_note='黑龙江通知公告仅接入静态首页；历史分页未接入，标题未明确招录的公告不纳入。'),
    _source('hainan_gov_notices', '海南省政府 · 招录相关公示公告', '海南省人民政府办公厅',
            'https://www.hainan.gov.cn/hainan/0101/list3_1.shtml', '海南', '',
            note='省政府综合公示公告目录中仅收录标题可识别的招录公告；不代替省人社厅、公务员局及各市县目录。'),
    _source('hebei_cyberspace_recruitment', '河北省委网信办 · 公务员及事业单位招录', '中共河北省委网络安全和信息化委员会办公室',
            'https://www.caheb.gov.cn/xxgk/gwyzl/index.shtml', '河北', '', False,
            note='仅省委网信办招录栏目当前静态页，包含公务员及所属事业单位公告；不代表河北全省。',
            history_note='河北省委网信办栏目当前页20条，未发现可核验分页；更早历史及其他机关单位不在覆盖范围。'),
    _source('neimenggu_medical_recruitment', '内蒙古医保局 · 招考及录用结果', '内蒙古自治区医疗保障局',
            'https://ylbzj.nmg.gov.cn/zwgk/zfxxgk/fdzdgknr/rsxx/gwyzkjlyjgxx/', '内蒙古', '', False,
            note='仅自治区医保局招考及录用结果两张公开目录表；排除跳转到外部考试网的条目，不代表全区。',
            history_note='内蒙古医保局仅接入当前两张目录表，未核验历史分页；3个外部考试网链接未纳入，其他部门与盟市仍有缺口。'),
]
for _item in EXPANSION_NORTH_SOURCES:
    if _item['id'].startswith('liaoning_sydw_'):
        _item['max_pages'] = 120
    if _item['id'].startswith('liaoning_'):
        _item['provenance'] = 'https://www.fuxin.gov.cn/content/2026/1038905.html'
    if _item['id'].startswith('guangxi_'):
        _item['provenance'] = 'https://jyj.gxzf.gov.cn/xxgk/fdzdgknr/rsxx/1224125_hytbght/t27145844.shtml'

_SOURCES = {s['id']: s for s in EXPANSION_NORTH_SOURCES}
_MIXED = {'jilin_hr_notices', 'heilongjiang_hr_notices', 'hainan_gov_notices'}
_INFER_KIND = _MIXED | {'hebei_cyberspace_recruitment', 'neimenggu_medical_recruitment'}
_RECRUITMENT = re.compile(r'公务员|招考|招录|招聘|遴选|选调|拟.*(?:录用|聘用|聘人员|聘人选)|(?:录用|聘用).*公示')
_LN_PAGES = {'liaoning_gwy_notices': '119', 'liaoning_sydw_notices': '80', 'liaoning_sydw_jobs': '78'}


def _directory_base(source):
    return urljoin(source['url'], './')


def _checked_url(url, source):
    try:
        parsed = urlparse(url)
        if (parsed.scheme != 'https' or parsed.hostname != urlparse(source['url']).hostname
                or parsed.port not in (None, 443) or parsed.username or parsed.password
                or parsed.query or parsed.fragment):
            raise ValueError
        return parsed
    except ValueError:
        raise ValueError('公告目录地址越界或格式无效，需要维护来源') from None


def _static_next(html, source, url):
    sid = source['id']
    path = _checked_url(url, source).path
    base = _directory_base(source)
    requested = re.fullmatch(re.escape(urlparse(base).path) + r'(?:index(?:_([1-9]\d*))?\.html)?', path)
    if not requested:
        raise ValueError('公告目录页码地址无效')
    if sid == 'tianjin_hr_jobs':
        # The official template renders parseInt('6}'); JavaScript uses 6.
        current = re.findall(r"currentPage\s*:\s*parseInt\(['\"](\d+)['\"]\)\s*\+\s*1", html)
        total = re.findall(r"countPage\s*:\s*parseInt\(['\"](\d+)\}?['\"]\)", html)
        if not re.search(r"PAGE_NAME\s*:\s*['\"]index['\"]", html) or not re.search(r"PAGE_EXT\s*:\s*['\"]html['\"]", html):
            raise ValueError('天津目录分页模板已变化')
    elif sid.startswith('guangxi_'):
        matches = re.findall(r"createPageHTML\(\s*(\d+)\s*,\s*(\d+)\s*,\s*['\"]index['\"]\s*,\s*['\"]html['\"]\s*\)", html)
        total, current = ([m[0] for m in matches], [m[1] for m in matches])
    else:
        current = re.findall(r'\bvar\s+currentPage\s*=\s*(\d+)\b', html)
        total = re.findall(r'\bvar\s+countPage\s*=\s*(\d+)\b', html)
    if len(current) != 1 or len(total) != 1:
        raise ValueError('公告目录分页结构已变化')
    page, pages = int(current[0]), int(total[0])
    if not 1 <= pages <= 10000 or not 0 <= page < pages or page != int(requested[1] or 0):
        raise ValueError('官网返回页码与请求不一致，历史目录未查完')
    return urljoin(base, f'index_{page + 1}.html') if page + 1 < pages else None


def _ln_next(soup, source, url):
    path = _checked_url(url, source).path
    base_path = urlparse(source['url']).path
    code = _LN_PAGES[source['id']]
    requested = re.fullmatch(re.escape(base_path) + rf'(?:{code}_([2-9]|[1-9]\d+)\.html)?', path)
    pagers = soup.select('#Pagination')
    if not requested or len(pagers) != 1:
        raise ValueError('辽宁目录分页容器或请求地址已变化')
    pager = pagers[0]
    active = pager.select('#page_center_botton > span.active')
    if len(active) != 1 or not active[0].get_text(strip=True).isdigit():
        raise ValueError('辽宁目录当前页标记缺失')
    page = int(active[0].get_text(strip=True))
    if page != int(requested[1] or 1):
        raise ValueError('辽宁官网返回页码与请求不一致')
    next_links = [a for a in pager.select('a[href]') if a.get_text(strip=True) == '下一页']
    if len(next_links) == 1:
        nxt = urljoin(url, next_links[0]['href'])
        _checked_url(nxt, source)
        if urlparse(nxt).path != base_path + f'{code}_{page + 1}.html':
            raise ValueError('辽宁下一页地址异常')
        return nxt
    if next_links or not any(x.get_text(strip=True) == '下一页' for x in pager.select('span')):
        raise ValueError('辽宁下一页或终点标记缺失')
    return None


def _hainan_next(html, source, url):
    path = _checked_url(url, source).path
    requested = re.fullmatch(r'/hainan/0101/list3_1(?:_([2-9]|[1-9]\d+))?\.shtml', path)
    matches = re.findall(r"createPageHTML\(['\"]page_div['\"]\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*['\"]list3_1['\"]\s*,\s*['\"]shtml['\"]\s*,\s*(\d+)\s*\)", html)
    if not requested or len(matches) != 1:
        raise ValueError('海南目录分页结构已变化')
    pages, page, total = map(int, matches[0])
    if not 1 <= page <= pages <= 10000 or page != int(requested[1] or 1) or not (pages - 1) * 12 < total <= pages * 12:
        raise ValueError('海南目录页码或总数异常')
    return urljoin(url, f'list3_1_{page + 1}.shtml') if page < pages else None


def _date(text):
    stamp = re.fullmatch(r'\s*\[?(20\d{2})[-./年](\d{1,2})[-./月](\d{1,2})日?\]?\s*', text)
    if stamp:
        try:
            return date(*map(int, stamp.groups())).isoformat()
        except ValueError:
            pass
    return None


def parse_expansion_north(html, source, url):
    """Return fixed-source metadata and a verified directory continuation."""
    sid = source['id']
    if sid not in _SOURCES or source['url'] != _SOURCES[sid]['url']:
        raise ValueError('未知的北方/华南目录来源')
    from .notices import exam_year_from_title, stage

    soup = BeautifulSoup(html, 'html.parser')
    base_path = urlparse(_directory_base(source)).path
    if sid in _LN_PAGES:
        next_url = _ln_next(soup, source, url)
        blocks = soup.select('div.kaoshilist')
        selector = '.kaoshilistrighttitle a[href]'
        article_pattern = re.escape(base_path) + r'\d+\.html'
    elif sid in {'hebei_cyberspace_recruitment', 'neimenggu_medical_recruitment'}:
        _checked_url(url, source)
        if url != source['url']:
            raise ValueError('备用招录目录仅接入固定当前页')
        next_url = None
        selector = 'a[href]'
        if sid == 'hebei_cyberspace_recruitment':
            containers = soup.select('div.ct_list > ul')
            if len(containers) != 1:
                raise ValueError('河北网信招录目录容器已变化')
            blocks = containers[0].find_all('li', recursive=False)
            article_pattern = r'/system/20\d{2}/\d{2}/\d{2}/\d+\.shtml'
        else:
            tables = soup.select('table#table1')
            if len(tables) != 2 or {x.get_text(strip=True) for x in soup.select('h3')} != {'招考信息', '录用结果信息'}:
                raise ValueError('内蒙古医保招录目录结构已变化')
            blocks = [row for table in tables for row in table.select('tr') if row.select_one('a[href]')]
            article_pattern = re.escape(base_path) + r'(?:[a-z0-9_]+/)?\d{6}/t\d{8}_\d+\.html'
    elif sid == 'hainan_gov_notices':
        next_url = _hainan_next(html, source, url)
        blocks = soup.select('div.list_div')
        selector = '.list-right_title a[href]'
        article_pattern = r'/hainan/0101/\d{6}/[a-zA-Z0-9]+\.shtml'
    else:
        if sid == 'heilongjiang_hr_notices':
            _checked_url(url, source)
            if url != source['url']:
                raise ValueError('黑龙江仅接入固定静态首页')
            next_url = None
            containers = soup.select('ul.listul')
            article_pattern = r'/hrss/c111741/\d{6}/c00_\d+\.shtml'
        else:
            next_url = _static_next(html, source, url)
            container = ('ul.list' if sid == 'beijing_hr_jobs' else
                         'div.fmultimedia-y > ul' if sid == 'tianjin_hr_jobs' else
                         'div.news_list4 > ul' if sid == 'jilin_hr_jobs' else
                         'div.news_list3 > ul' if sid == 'jilin_hr_notices' else 'ul.articles')
            containers = soup.select(container)
            article_pattern = re.escape(base_path) + (r't\d+\.html' if sid.startswith('guangxi_') else r'\d{6}/t\d{8}_\d+\.html')
        if len(containers) != 1:
            raise ValueError('公告目录容器已变化，需要维护来源')
        blocks = containers[0].find_all('li', recursive=False)
        selector = 'a[href]'
    if not blocks:
        raise ValueError('未识别公告目录条目，不能当作零条公告')
    items, recognized = {}, 0
    for block in blocks:
        a = block.select_one(selector)
        if a is None:
            continue
        target = urljoin(url, a['href'].strip()).split('#')[0]
        try:
            target_path = _checked_url(target, source).path
        except ValueError:
            continue
        if not re.fullmatch(article_pattern, target_path):
            continue
        title = (a.get('title') or '').strip() or a.get_text(' ', strip=True)
        if not title or len(title) > 500:
            raise ValueError('公告标题为空或长度异常，不能当作采集完成')
        recognized += 1
        if sid in _MIXED and not _RECRUITMENT.search(title):
            continue
        if sid in _LN_PAGES:
            year = block.select_one('.kaoshilistleftbottom1')
            md = block.select_one('.kaoshilistlefttop1')
            published = _date(f'{year.get_text(strip=True)}-{md.get_text(strip=True)}') if year and md else None
        elif sid == 'neimenggu_medical_recruitment':
            cells = block.find_all('td', recursive=False)
            published = _date(cells[-1].get_text(' ', strip=True)) if cells else None
        elif sid == 'hainan_gov_notices':
            stamps = [x.get_text(' ', strip=True).removeprefix('发布时间：').strip() for x in block.select('td')
                      if x.get_text(' ', strip=True).startswith('发布时间：')]
            published = _date(stamps[0]) if len(stamps) == 1 else None
        else:
            stamps = {_date(x.get_text(' ', strip=True)) for x in block.select('span,em')}
            stamps.discard(None)
            published = next(iter(stamps)) if len(stamps) == 1 else None
        kind = source['kind']
        if sid in _INFER_KIND:
            kind = '事业单位' if '事业单位' in title else ('省考' if '公务员' in title else '')
        items[target] = dict(id=hashlib.sha256(target.encode()).hexdigest(), source_id=sid,
                             source=source['name'], owner=source['owner'], title=title, url=target,
                             published=published, exam_year=exam_year_from_title(title),
                             kind=kind, region=source['region'], stage=stage(title))
    if not recognized:
        raise ValueError('未识别有效公告链接，不能当作零条公告')
    return list(items.values()), next_url
