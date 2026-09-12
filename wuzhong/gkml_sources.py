"""Fixed Guangdong recruitment directories, parsed from public gkmlpt JSON.

Only the directory metadata is retained. This module never performs requests or
follows an article/attachment link. The common Fetcher remains the only reader.
"""
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit


_BJT = timezone(timedelta(hours=8))
_PAGE_SIZE = 100  # Public list service groups five displayed 20-row pages.
_WINDOW_NOTE = ('已读取官网当前公开目录分页；接口可列出总数少于栏目计数，'
                '未列出的历史或其他条目无法由当前目录核实。'
                '目录中的外部跳转型条目不纳入，仅保存本栏目同域普通公告，不代表本地区招录公示完整。')


def _source(id, name, owner, base, sid, column, column_name, kind, counts):
    return dict(
        id=id, name=name, owner=owner,
        url=f'{base}/gkmlpt/index#{column}',
        listing_url=f'{base}/gkmlpt/api/all/{column}?page=1&sid={sid}',
        kind=kind, region='广东', area_scope='province', max_pages=100,
        history=False, history_note=_WINDOW_NOTE,
        note=f'仅{owner}的{column_name}栏目；{counts}。'+_WINDOW_NOTE,
        gkml_sid=str(sid), gkml_column=column, gkml_column_name=column_name,
        gkml_document_prefix=urlsplit(base).path + '/gkmlpt/content/',
    )


GKML_SOURCES = [
    _source('zhaoqing_recruitment', '肇庆人社局 · 事业单位招聘', '肇庆市人力资源和社会保障局',
            'https://www.zhaoqing.gov.cn/zqrsj', 758017, 21206, '事业单位招聘', '事业单位',
            '2026-09-12核验当前目录221条、栏目计数726条'),
    _source('zhaoqing_civil', '肇庆人社局 · 公务员招考', '肇庆市人力资源和社会保障局',
            'https://www.zhaoqing.gov.cn/zqrsj', 758017, 22168, '公务员招考', '省考',
            '2026-09-12核验当前目录6条、栏目计数20条'),
    _source('yangjiang_civil', '阳江人社局 · 公务员招考', '阳江市人力资源和社会保障局',
            'https://www.yangjiang.gov.cn/yjrsj', 662018, 318, '公务员招考', '省考',
            '2026-09-12核验当前目录14条、栏目计数43条'),
    _source('shantou_recruitment', '汕头人社局 · 招考录用', '汕头市人力资源和社会保障局',
            'https://www.shantou.gov.cn/stsrlsbj', 754019, 3283, '招考录用', '',
            '2026-09-12核验当前目录2252条、栏目计数3205条'),
    _source('huizhou_recruitment', '惠州人社局 · 事业单位招考信息', '惠州市人力资源和社会保障局',
            'https://rsj.huizhou.gov.cn', 752020, 588, '事业单位招考信息', '事业单位',
            '2026-09-12核验当前目录205条、栏目计数419条'),
    _source('zhongshan_recruitment', '中山人社局 · 人员招聘', '中山市人力资源和社会保障局',
            'https://hrss.zs.gov.cn', 760005, 3265, '人员招聘', '',
            '2026-09-12核验当前目录21条、栏目计数2679条'),
    _source('shenzhen_recruitment', '深圳人社局 · 人员招录', '深圳市人力资源和社会保障局',
            'https://hrss.sz.gov.cn', 755011, 24007, '人员招录', '',
            '2026-09-13经TLS曲线兼容重试核验当前目录135条、栏目计数217条'),
]

_SOURCE_IDS = {s['id'] for s in GKML_SOURCES}


def _integer(value, name, minimum=0, maximum=10_000_000):
    # Booleans, strings and fractional values signal a changed JSON contract.
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'公开目录{name}无效，需要维护来源')
    return value


def _page(source, url):
    expected, requested = urlsplit(source['listing_url']), urlsplit(url)
    try:
        params = parse_qs(requested.query, strict_parsing=True)
        valid = (requested.scheme == 'https' and requested.netloc == expected.netloc
                 and requested.path == expected.path and not requested.fragment
                 and set(params) == {'page', 'sid'}
                 and params['sid'] == [source['gkml_sid']]
                 and len(params['page']) == 1
                 and re.fullmatch(r'[1-9]\d{0,5}', params['page'][0]))
    except ValueError:
        valid = False
    if not valid:
        raise ValueError('公开目录请求不属于已核验栏目或页码无效')
    return int(params['page'][0])


def _published(value):
    # The site's public table labels create_time as 发布日期 and date as 成文日期.
    # Missing/invalid publication metadata must not be replaced with either the
    # document date, ingestion time (created_at), URL date or examination year.
    if type(value) is not int or value <= 0:
        return None
    try:
        result = datetime.fromtimestamp(value, _BJT)
        return result.date().isoformat() if 1900 <= result.year <= 9999 else None
    except (OverflowError, OSError, ValueError):
        return None


def _article_url(article, source):
    raw = article.get('url')
    if not isinstance(raw, str):
        raise ValueError('公开目录条目缺少官方原文链接，不能忽略后报告完成')
    try:
        parsed = urlsplit(raw.strip())
        official = urlsplit(source['url'])
        # The verified site's renderer uses protocol-relative links for ordinary
        # documents. On its HTTPS listing, same-host HTTP metadata therefore
        # becomes HTTPS as well. Never upgrade/follow an external redirect.
        valid = (parsed.scheme in ('https', 'http') and parsed.hostname == official.hostname
                 and parsed.port in (None, 443) and not parsed.username and not parsed.password
                 and not parsed.query and article.get('type') == 'normal'
                 and re.fullmatch(re.escape(source['gkml_document_prefix'])
                                  + r'\d+/\d+/post_' + str(article['id']) + r'\.html', parsed.path))
    except (KeyError, ValueError):
        valid = False
    if not valid:
        raise ValueError('公开目录含未核验原文链接或非普通公告，需复核；未读取详情或附件')
    return urlunsplit(('https', official.netloc, parsed.path, '', ''))


def parse_gkml(html, source, url):
    """Return exact metadata fields and a next directory URL, never an article URL."""
    if source.get('id') not in _SOURCE_IDS:
        raise ValueError('未知的公开目录来源')
    page = _page(source, url)
    try:
        payload = json.loads(html)
    except (json.JSONDecodeError, TypeError):
        raise ValueError('官网未返回有效公开目录JSON，不能当作零条公告') from None
    if not isinstance(payload, dict) or not isinstance(payload.get('classify'), dict):
        raise ValueError('公开目录分类结构已变化，需要维护来源')
    classification = payload['classify']
    if (classification.get('id') != source['gkml_column']
            or classification.get('name') != source['gkml_column_name']
            or classification.get('jump_url')):
        raise ValueError('官网返回栏目与已核验招录栏目不一致')
    _integer(classification.get('post_count'), '栏目计数')
    total = _integer(payload.get('total'), '总数')
    offset = _integer(payload.get('offset'), '偏移量')
    articles = payload.get('articles')
    if not isinstance(articles, list):
        raise ValueError('公开目录条目结构已变化，需要维护来源')
    if offset != (page - 1) * _PAGE_SIZE or offset > total:
        raise ValueError('官网返回页码与请求不一致，历史目录未查完')
    if len(articles) != min(_PAGE_SIZE, total - offset):
        raise ValueError('公开目录条目数与分页总数不符，不能当作已查完')

    from .notices import exam_year_from_title, stage
    rows, seen = [], set()
    for article in articles:
        if not isinstance(article, dict):
            raise ValueError('公开目录含无效条目，需要维护来源')
        _integer(article.get('id'), '公告编号', 1, 2**53-1)
        if article.get('classify_main') != source['gkml_column']:
            raise ValueError('公开目录条目不属于已核验招录栏目')
        title = article.get('title')
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 500:
            raise ValueError('公开目录公告标题缺失或异常，需要维护来源')
        title = title.strip()
        # External references have not been verified as fixed official sources.
        # Keep that exclusion explicit and use the original row count for paging.
        if article.get('type') == 'url':
            continue
        target = _article_url(article, source)
        if target in seen:
            raise ValueError('公开目录页内出现重复公告，不能当作已查完')
        seen.add(target)
        kind = source['kind'] or ('省考' if '公务员' in title else '事业单位' if '事业单位' in title else '')
        if re.search('编外|非编', title): kind = ''
        rows.append(dict(
            id=hashlib.sha256(target.encode()).hexdigest(), source_id=source['id'],
            source=source['name'], owner=source['owner'], title=title, url=target,
            published=_published(article.get('create_time')),
            exam_year=exam_year_from_title(title),
            kind=kind,
            region=source['region'], stage=stage(title),
        ))

    next_url = None
    if offset + len(articles) < total:
        base = urlsplit(source['listing_url'])
        next_url = urlunsplit((base.scheme, base.netloc, base.path,
                              urlencode({'page': page + 1, 'sid': source['gkml_sid']}), ''))
    return rows, next_url
