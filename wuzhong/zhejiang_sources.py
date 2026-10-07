"""Zhejiang's public directory API; no script execution or detail requests."""
import hashlib
import json
import re
from datetime import date
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

from bs4 import BeautifulSoup


COLUMN_URL = 'https://rlsbt.zj.gov.cn/col/col1229743684/index.html'
API_URL = 'https://rlsbt.zj.gov.cn/api-gateway/jpaas-publish-server/front/page/build/unit'
_PARAMS = dict(webId='2758', pageId='1229743684', parseType='bulidstatic',
               pageType='column', tagId='当前栏目列表', tplSetId='kUBgoFENJiaYxr31jYEph')
_ROWS = 10


def directory_url(page=1):
    if type(page) is not int or not 1 <= page <= 10000:
        raise ValueError('浙江目录页码无效')
    params = dict(_PARAMS)
    if page == 1:
        params['editType'] = 'null'
    else:
        params['paramJson'] = json.dumps(dict(pageNo=page, pageSize=_ROWS), separators=(',', ':'))
    return API_URL + '?' + urlencode(params)


ZHEJIANG_SOURCES = [dict(
    id='zhejiang', name='浙江人社厅 · 拟聘公示', owner='浙江省人力资源和社会保障厅',
    url=COLUMN_URL, listing_url=directory_url(), kind='事业单位', region='浙江',
    area_scope='province', max_pages=20, history=False,
    note='浙江人社厅汇集的拟聘公示目录；不代表全省各市县及各单位全部公示。',
    history_note='已接通官方目录分页；每轮最多检查20页更新窗口，未证明全部历史完整；站外引用和名单附件不索引。',
)]


def _checked_url(url):
    parsed = urlparse(url)
    try:
        valid = (parsed.scheme == 'https' and parsed.hostname == 'rlsbt.zj.gov.cn'
                 and parsed.port in (None, 443) and not parsed.username and not parsed.password
                 and not parsed.fragment and not parsed.params)
    except ValueError:
        valid = False
    if not valid:
        raise ValueError('浙江目录请求离开固定官方HTTPS来源')
    return parsed


def _requested_page(url):
    parsed = _checked_url(url)
    if parsed.path != urlparse(API_URL).path:
        raise ValueError('浙江目录API路径已变化')
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    params = dict(pairs)
    if len(params) != len(pairs) or any(params.get(k) != v for k, v in _PARAMS.items()):
        raise ValueError('浙江目录固定参数不一致')
    extras = set(params) - set(_PARAMS)
    if extras == {'editType'} and params['editType'] == 'null':
        return 1
    if extras != {'paramJson'}:
        raise ValueError('浙江目录请求含未知参数')
    try:
        page = json.loads(params['paramJson'])
    except (TypeError, ValueError) as error:
        raise ValueError('浙江目录分页请求格式无效') from error
    if (not isinstance(page, dict) or set(page) != {'pageNo', 'pageSize'}
            or type(page['pageNo']) is not int or not 2 <= page['pageNo'] <= 10000
            or type(page['pageSize']) is not int or page['pageSize'] != _ROWS):
        raise ValueError('浙江目录分页请求参数无效')
    return page['pageNo']


def _pagination(soup, requested):
    tables = soup.select('table.pagination[querydata][uniturl]')
    if len(tables) != 1:
        raise ValueError('浙江目录分页结构已变化')
    table = tables[0]
    try:
        params = json.loads(table['querydata'].replace("'", '"'))
        count = int(table['count'])
        rows = int(table['rows'])
        current = int(table['pageno'])
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError('浙江目录分页元数据无效') from error
    if (params != _PARAMS or table['uniturl'] != urlparse(API_URL).path
            or not 0 <= count <= 100000 or rows != _ROWS):
        raise ValueError('浙江目录栏目或分页配置已变化')
    pages = max(1, (count + rows - 1) // rows)
    if current != requested or not 1 <= current <= pages:
        raise ValueError('浙江官网返回页码与请求不一致，历史目录未查完')
    expected_rows = min(rows, max(0, count - (current - 1) * rows))
    return expected_rows, directory_url(current + 1) if current < pages else None


def _published(block):
    stamps = block.find_all('span', class_='bt_time', recursive=False)
    if len(stamps) != 1:
        return None
    value = stamps[0].get_text(' ', strip=True)
    if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', value):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def parse_zhejiang(raw, source, url):
    """Read only directory titles, independent publication dates and official URLs."""
    if (source.get('id') != 'zhejiang' or source.get('url') != COLUMN_URL
            or source.get('listing_url') != directory_url()):
        raise ValueError('未知的浙江目录来源')
    requested = _requested_page(url)
    try:
        response = json.loads(raw)
    except (ValueError, TypeError) as error:
        raise ValueError('浙江公开目录未返回JSON，不能当作零条公告') from error
    if (not isinstance(response, dict) or str(response.get('code')) != '200'
            or response.get('success') is not True or not isinstance(response.get('data'), dict)
            or not isinstance(response['data'].get('html'), str)):
        raise ValueError('浙江公开目录返回异常，不能当作零条公告')
    soup = BeautifulSoup(response['data']['html'], 'html.parser')
    expected_rows, next_url = _pagination(soup, requested)
    containers = soup.select('div[id="当前栏目列表"] > div.page-content')
    if len(containers) != 1:
        raise ValueError('浙江公告目录容器已变化')
    blocks = containers[0].find_all('li', recursive=False)
    if len(blocks) != expected_rows:
        raise ValueError('浙江目录条目数与分页声明不一致，目录未读完整')
    from .notices import exam_year_from_title, stage
    items = {}
    for block in blocks:
        anchors = block.find_all('a', class_='bt_link', href=True, recursive=False)
        if len(anchors) != 1:
            raise ValueError('浙江目录标题链接结构已变化')
        anchor = anchors[0]
        target = urljoin(COLUMN_URL, anchor['href'].strip())
        parsed = urlparse(target)
        if parsed.scheme not in ('http', 'https'):
            continue
        if parsed.hostname != 'rlsbt.zj.gov.cn':
            continue
        # A known official-host link that changes transport or carries credentials,
        # an unexpected port, fragment or path parameters is a visible failure.
        parsed = _checked_url(target)
        # Explicit external references and attachments are outside this index.
        if re.search(r'\.(?:pdf|docx?|xlsx?|zip|rar)$', parsed.path, re.I):
            continue
        if parsed.query or not re.fullmatch(r'/col/col1229743684/art/20\d{2}/art_[a-f0-9]+\.html', parsed.path):
            raise ValueError('浙江同域公告链接路径已变化，需要维护来源')
        title = (anchor.get('title') or '').strip() or anchor.get_text(' ', strip=True)
        if not title or len(title) > 500:
            raise ValueError('浙江公告标题为空或过长')
        kind = '' if re.search(r'编外|非编|劳务派遣', title) else source['kind']
        items[target] = dict(id=hashlib.sha256(target.encode()).hexdigest(), source_id=source['id'],
                             source=source['name'], owner=source['owner'], title=title, url=target,
                             published=_published(block), exam_year=exam_year_from_title(title),
                             kind=kind, region=source['region'], stage=stage(title))
    return list(items.values()), next_url
