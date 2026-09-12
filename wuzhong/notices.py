"""Announcement metadata only. No legacy matcher or attachment parser imports."""
import calendar
import hashlib
import ipaddress
import json
import re
import socket
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from .extra_sources import EXTRA_SOURCES, parse_extra

REGIONS = '北京 天津 河北 山西 内蒙古 辽宁 吉林 黑龙江 上海 江苏 浙江 安徽 福建 江西 山东 河南 湖北 湖南 广东 广西 海南 重庆 四川 贵州 云南 西藏 陕西 甘肃 青海 宁夏 新疆 兵团'.split()
SOURCES = [
    dict(id='stats', name='国家统计局 · 公务员招录', owner='国家统计局', url='https://www.stats.gov.cn/xxgk/rsxx/gwyzl2020/', kind='国考', region='', max_pages=12, history=True, note='仅统计局机关及调查队系统；岗位地区需看原文。'),
    dict(id='fujian', name='福建省科技厅 · 招考招录', owner='福建省科技厅', url='https://kjt.fujian.gov.cn/xxgk/rsxx/zkzl/', kind='', region='福建', max_pages=1, history=False, note='仅当前栏目首页；历史分页尚未接入，不代表福建全省。'),
    dict(id='guangdong', name='广东省人社厅 · 事业单位公开招聘', owner='广东省人力资源和社会保障厅', url='https://hrss.gd.gov.cn/zwgk/sydwzp/', kind='事业单位', region='广东', max_pages=200, history=True, note='仅本厅汇集的事业单位招聘栏目，不代表广东所有单位；官网分页最多200页，更早历史可能不可达。'),
]
UA = 'WuzhongNoticeReader/0.2 (local announcement metadata browser)'


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def next_check(saved):
    current = datetime.now(timezone.utc)
    if saved.get('schedule_mode') == 'daily':
        hour, minute = map(int, saved['daily_time'].split(':'))
        local = current.astimezone(timezone(timedelta(hours=8)))
        target = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= local: target += timedelta(days=1)
        return target.astimezone(timezone.utc).isoformat(timespec='seconds')
    return (current + timedelta(hours=saved['interval_hours'])).isoformat(timespec='seconds')


def validate_filters(data):
    if not isinstance(data, dict):
        raise ValueError('查询条件格式错误')
    def month(value):
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}', value):
            raise ValueError('请选择开始和结束年月')
        return date.fromisoformat(value+'-01')
    month_from, month_to = data.get('month_from'), data.get('month_to')
    # One supplied endpoint means a single month/year, never an open-ended crawl.
    has_month = month_from not in ('', None) or month_to not in ('', None)
    start = month(month_from if month_from not in ('', None) else month_to) if has_month else None
    end = month(month_to if month_to not in ('', None) else month_from) if has_month else None
    if has_month and start > end:
        raise ValueError('公示开始月份不能晚于结束月份')
    year_from, year_to = data.get('year_from'), data.get('year_to')
    if year_from in ('', None): year_from = year_to
    if year_to in ('', None): year_to = year_from
    if year_from not in ('', None):
        if not re.fullmatch(r'\d{4}', str(year_from)) or not re.fullmatch(r'\d{4}', str(year_to)):
            raise ValueError('招考年度需为四位年份')
        year_from, year_to = int(year_from), int(year_to)
        if not 1000 <= year_from <= year_to <= 9999:
            raise ValueError('招考开始年份不能晚于结束年份')
    else:
        year_from = year_to = None
    if not has_month and not year_from:
        raise ValueError('请至少设置公示发布时间或招考年度；填一个月份或年份也可以查询')
    region, kind = data.get('region', ''), data.get('kind', '')
    if region not in ['', *REGIONS] or kind not in ('', '国考', '省考', '事业单位'):
        raise ValueError('地区或招录类型无效')
    area_scope = data.get('area_scope', 'all')
    if area_scope not in ('all', 'province', 'national'):
        raise ValueError('招录范围无效')
    if area_scope == 'province' and not region:
        raise ValueError('请选择省份')
    if area_scope == 'national' and region:
        raise ValueError('全国／中央招录不按省份筛选；岗位所在地请查看原文')
    source_id, scope = data.get('source_id', ''), data.get('notice_scope', 'all')
    if source_id not in ['', *[s['id'] for s in SOURCES]] or scope not in ('all', 'public'):
        raise ValueError('公告来源或范围无效')
    return dict(month_from=start.strftime('%Y-%m') if start else None, month_to=end.strftime('%Y-%m') if end else None, date_from=start.isoformat() if start else None, date_to=end.replace(day=calendar.monthrange(end.year, end.month)[1]).isoformat() if end else None, year_from=year_from, year_to=year_to, region=region, kind=kind, source_id=source_id, notice_scope=scope, area_scope=area_scope)


SOURCES.extend(EXTRA_SOURCES)
SOURCE_AREAS = {'stats': 'national', 'fujian': 'province', 'guangdong': 'province', **{s['id']:s['area_scope'] for s in EXTRA_SOURCES}}
for _source in SOURCES:
    _source['area_scope'] = SOURCE_AREAS[_source['id']]


def area_matches(source_id, f):
    return f.get('area_scope', 'all') == 'all' or SOURCE_AREAS.get(source_id) == f['area_scope']


def compatible(source, f):
    if not area_matches(source['id'], f): return False
    if f.get('source_id') and source['id'] != f['source_id']: return False
    return (not f['kind'] or not source['kind'] or f['kind'] == source['kind']) and (not f['region'] or not source['region'] or f['region'] == source['region'])


def relevance(n, f):
    if not area_matches(n.get('source_id'), f): return None
    if f.get('source_id') and n['source_id'] != f['source_id']: return None
    if f.get('notice_scope') == 'public' and stage(n['title']) not in ('录聘公示', '更正／补充', '撤销通知'): return None
    if f.get('date_from') and n['published'] and not f['date_from'] <= n['published'] <= f['date_to']:
        return None
    if f['year_from'] and n['exam_year'] and not f['year_from'] <= n['exam_year'] <= f['year_to']:
        return None
    if f['kind'] and n['kind'] and n['kind'] != f['kind']:
        return None
    if f['region'] and n['region'] and n['region'] != f['region']:
        return None
    return 'review' if (f.get('date_from') and not n['published']) or (f['year_from'] and not n['exam_year']) or (f['region'] and not n['region']) or (f['kind'] and not n['kind']) else 'matched'


def stage(title):
    if re.search('撤销|撤回|取消招聘', title): return '撤销通知'
    if re.search('更正|调整|补充公告', title): return '更正／补充'
    if re.search('拟.*(?:录用|聘用|聘人员|聘人选)|(?:录用|聘用).*公示', title): return '录聘公示'
    if '面试' in title: return '面试通知'
    if re.search('体检|考察', title): return '体检／考察'
    if re.search('笔试|成绩', title): return '考试通知'
    return '招录信息'


def exam_year_from_title(title):
    """Conservative title evidence; publication dates never imply an exam year."""
    matches = list(re.finditer(r'(20\d{2})\s*年(?:度)?', title))
    years = {int(m[1]) for m in matches}
    if len(years) != 1:
        return None
    for m in matches:
        tail = title[m.end():]
        if re.match(r'\s*(?:\d{1,2}月|应届|毕业|入学|出生|参加工作)', tail):
            return None
    return years.pop()


def listing(html, source, url):
    if source['id'] in {s['id'] for s in EXTRA_SOURCES}:
        return parse_extra(html, source, url)
    soup = BeautifulSoup(html, 'html.parser')
    base = urlparse(source['url'])
    items = {}
    for a in soup.select('a[href]'):
        target = urljoin(url, a['href']).split('#')[0]
        p = urlparse(target)
        if p.scheme != 'https' or p.hostname != base.hostname or p.port not in (None,443) or p.username or p.password or not p.path.startswith(base.path):
            continue
        # Each fixed adapter recognizes announcement links, never attachment files.
        pattern = r'/(?:zpgg|rygs|zcfg)/content/post_\d+\.html$' if source['id'] == 'guangdong' else r'/\d{6}/t\d{8}_\d+\.(?:s?html?)$'
        if not re.search(pattern, p.path):
            continue
        title = (a.get('title') or a.get_text(' ', strip=True)).strip()
        if not 6 <= len(title) <= 500:
            continue
        parent = a.find_parent('li') or a.parent
        dates = re.findall(r'(?<!\d)(20\d{2})[-年./](\d{1,2})[-月./](\d{1,2})(?:日)?', parent.get_text(' ', strip=True))
        published = None
        if dates:
            try: published = date(*map(int, dates[-1])).isoformat()
            except ValueError: pass
        # URL dates are not substituted for missing publication metadata.
        kind = '事业单位' if '事业单位' in title else source['kind']
        if not kind and '公务员' in title: kind = '省考'
        items[target] = dict(id=hashlib.sha256(target.encode()).hexdigest(), source_id=source['id'], source=source['name'], owner=source['owner'], title=title, url=target, published=published, exam_year=exam_year_from_title(title), kind=kind, region=source['region'], stage=stage(title))
    next_url = None
    if source['id'] == 'stats':
        count = re.search(r'm_nRecordCount\s*=\s*["\']?(\d+)', html)
        size = re.search(r'm_nPageSize\s*=\s*["\']?(\d+)', html)
        current = re.search(r'm_nCurrPage\s*=\s*["\']?(\d+)', html)
        if not all((count, size, current)) or int(size[1]) < 1:
            raise ValueError('目录分页结构已变化，需要维护来源')
        if (int(current[1])+1)*int(size[1]) < int(count[1]):
            next_url = urljoin(source['url'], f'index_{int(current[1])+1}.html')
    elif source['id'] == 'guangdong':
        count = re.search(r"var\s+numbers\s*=\s*['\"](\d+)['\"]", html)
        size = re.search(r'var\s+page_t1\s*=\s*Math\.ceil\(\s*numbers\s*/\s*(\d+)\s*\)', html)
        limit = re.search(r"var\s+page_t2\s*=\s*['\"](\d+)['\"]", html)
        if not all((count, size, limit)) or int(size[1]) < 1 or int(limit[1]) != source['max_pages']:
            raise ValueError('广东目录分页结构或官网页数上限已变化，需要维护来源')
        current = re.search(r'/index_(\d+)\.html$', urlparse(url).path)
        page = int(current[1]) if current else 1
        if page * int(size[1]) < int(count[1]):
            # Leave next_url set at the cap so the engine reports partial, not complete.
            next_url = urljoin(source['url'], f'index_{page+1}.html')
    if not items:
        raise ValueError('未识别到有效公告目录，不能当作零条公告')
    return list(items.values()), next_url


class Stopped(Exception): pass


class Fetcher:
    def __init__(self, source, cancel):
        self.source, self.cancel = source, cancel
        self.host = urlparse(source['url']).hostname
        self.session = requests.Session()
        self.session.headers['User-Agent'] = UA
        self.robot = None
        self.delay, self.last = 2.0, 0.0

    def check(self):
        if self.cancel.is_set(): raise Stopped()

    def raw(self, url):
        for hop in range(4):
            self.check()
            p = urlparse(url)
            if p.scheme != 'https' or p.hostname != self.host or p.port not in (None,443) or p.username or p.password:
                raise ValueError('重定向离开已核验官方来源')
            addresses = socket.getaddrinfo(self.host, 443, type=socket.SOCK_STREAM)
            # This local machine uses a VPN's fake-IP DNS (198.18.0.0/15).
            # Only hardcoded official HTTPS hosts can reach this path; TLS hostname
            # verification remains enabled. Ordinary private/loopback IPs are refused.
            def permitted(address):
                ip=ipaddress.ip_address(address)
                return ip.is_global or ip in ipaddress.ip_network('198.18.0.0/15')
            if not addresses or any(not permitted(a[4][0]) for a in addresses):
                raise ValueError('来源解析到非公网地址，已停止读取')
            remaining = self.delay - (time.monotonic()-self.last)
            if remaining > 0 and self.cancel.wait(remaining): raise Stopped()
            self.last = time.monotonic()
            for attempt in range(2):
                try:
                    r = self.session.get(url, timeout=(6,12), stream=True, allow_redirects=False)
                    break
                except (requests.Timeout, requests.ConnectionError):
                    if attempt: raise
                    if self.cancel.wait(2): raise Stopped()
            with r:
                if r.is_redirect:
                    url = urljoin(url, r.headers.get('Location',''))
                    continue
                if r.status_code == 429:
                    raise ValueError('站点限流，本轮暂停；请按站点要求稍后重试')
                if r.status_code == 404: return '',404
                r.raise_for_status()
                content, size = [], 0
                start = time.monotonic()
                for block in r.iter_content(16384):
                    self.check()
                    size += len(block)
                    if size > 3_000_000 or time.monotonic()-start > 30:
                        raise ValueError('页面超过读取限制，本轮未完成')
                    content.append(block)
                raw = b''.join(content)
                enc = re.search(br'charset\s*=\s*["\']?([\w-]+)', raw[:5000], re.I)
                try: text = raw.decode(enc[1].decode('ascii') if enc else 'utf-8')
                except (UnicodeError, LookupError): text = raw.decode('gb18030','replace')
                return text, r.status_code
        raise ValueError('重定向次数超过限制')

    def get(self, url):
        if self.robot is None:
            text, code = self.raw(f'https://{self.host}/robots.txt')
            if code != 404 and '<html' in text.lower():
                raise ValueError('robots返回网页而非规则，需人工核验访问要求')
            self.robot = RobotFileParser()
            self.robot.parse([] if code == 404 else text.splitlines())
            self.delay = max(2, self.robot.crawl_delay(UA) or self.robot.crawl_delay('*') or 2)
        if not self.robot.can_fetch(UA,url): raise ValueError('站点规则不允许读取该栏目')
        text, code = self.raw(url)
        if code == 404: raise ValueError('栏目目前返回404，需复核入口')
        return text


class NoticeStore:
    def __init__(self, folder):
        folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
        self.path = folder/'announcements.sqlite3'
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS entries (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS saved (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS alerts (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
        for run in self.all('runs'):
            if run['status'] == 'running':
                run.update(status='interrupted', ended=now());self.put('runs',run)

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=15)
        try:
            with db: yield db
        finally: db.close()

    def all(self, table):
        assert table in ('entries','runs','saved','alerts')
        with self.db() as db: return [json.loads(row[0]) for row in db.execute(f'SELECT data FROM {table}')]

    def put(self, table, item):
        assert table in ('entries','runs','saved','alerts')
        with self.db() as db: db.execute(f'INSERT OR REPLACE INTO {table} VALUES (?,?)',(item['id'],json.dumps(item,ensure_ascii=False)))

    def delete(self, id):
        with self.db() as db: db.execute('DELETE FROM saved WHERE id=?',(id,))

    def record(self, item):
        with self.db() as db:
            row = db.execute('SELECT data FROM entries WHERE id=?',(item['id'],)).fetchone()
            prior=json.loads(row[0]) if row else None
            changed=bool(prior and any(item[k] != prior.get(k) for k in item if k not in ('revision','first_seen','checked_at','changed_at')))
            item=dict(item,first_seen=prior['first_seen'] if prior else now(),checked_at=now(),changed_at=now() if changed else prior.get('changed_at') if prior else None)
            item['revision']=(prior.get('revision',1)+int(changed)) if prior else 1
            db.execute('INSERT OR REPLACE INTO entries VALUES (?,?)',(item['id'],json.dumps(item,ensure_ascii=False)))
            if not prior or changed:
                for row in db.execute('SELECT data FROM saved').fetchall():
                    saved = json.loads(row[0])
                    if not saved.get('enabled') or not saved.get('notify_enabled'): continue
                    match = relevance(item, saved['filters'])
                    if not match: continue
                    # revision distinguishes A -> B -> A from a repeated unchanged fetch.
                    fingerprint = {k:v for k,v in item.items() if k not in ('first_seen','checked_at','changed_at')}
                    alert_id = hashlib.sha256((saved['id'] + json.dumps(fingerprint,sort_keys=True)).encode()).hexdigest()
                    alert = dict(id=alert_id,saved_id=saved['id'],created=now(),read=False,title=item['title'],url=item['url'],source=item['source'],published=item['published'],match_status=match,event='updated' if prior else 'new')
                    db.execute('INSERT OR IGNORE INTO alerts VALUES (?,?)',(alert_id,json.dumps(alert,ensure_ascii=False)))
        return (0 if prior else 1), int(changed)


class NoticeEngine:
    def __init__(self, store, root, fetcher=Fetcher):
        self.store,self.root,self.fetcher=store,root,fetcher
        self.cancel=threading.Event();self.lock=threading.Lock()
        self.settings_lock=threading.RLock()
        self.state=dict(running=False,message='',run_id=None)

    def start(self, filters):
        if not self.lock.acquire(blocking=False): return False
        self.cancel.clear()
        run=dict(id=uuid.uuid4().hex,started=now(),ended=None,status='running',filters=filters,sources=[],new=0,updated=0)
        self.state=dict(running=True,message='准备检查官方栏目',run_id=run['id'])
        try:
            self.store.put('runs',run)
            threading.Thread(target=self._run,args=(run,),daemon=True).start()
        except Exception:
            self.state=dict(running=False,message='无法启动检查，请检查本机存储',run_id=None)
            self.lock.release()
            raise
        return True

    def _run(self, run):
        try:
            handoff=Path(self.root)/'HANDOFF.md'
            run['handoff_digest']=hashlib.sha256(handoff.read_bytes()).hexdigest() if handoff.exists() else None
            selected=[s for s in SOURCES if compatible(s,run['filters'])]
            for source in selected:
                if self.cancel.is_set(): raise Stopped()
                report=dict(id=source['id'],name=source['name'],status='running',pages=0,found=0,dates=[],warnings=[])
                run['sources'].append(report)
                f=self.fetcher(source,self.cancel)
                url=source['url'];seen=set()
                try:
                    while url and report['pages'] < source['max_pages']:
                        if url in seen: raise ValueError('分页出现循环，本轮未查完')
                        seen.add(url)
                        self.state['message']=f"正在检查{source['name']} · 第{report['pages']+1}页"
                        items,url=listing(f.get(url),source,url)
                        report['pages']+=1
                        for item in items:
                            n,u=self.store.record(item);run['new']+=n;run['updated']+=u
                            report['found']+=1
                            if item['published']:report['dates'].append(item['published'])
                        self.store.put('runs',run)
                    if url:report['warnings'].append('达到分页上限，历史目录未查完')
                    if not source['history']:report['warnings'].append('仅读取当前栏目首页，历史分页未接入')
                    report['status']='partial' if report['warnings'] else 'completed'
                except Stopped:
                    report['status']='cancelled';raise
                except Exception as e:
                    report['status']='partial' if report['pages'] else 'failed'
                    report['warnings'].append(str(e) if isinstance(e,ValueError) else '网络请求失败，请稍后重试或打开官方栏目检查')
                finally:
                    f.session.close()
                    dates=report.pop('dates',[])
                    report['earliest']=min(dates) if dates else None
                    report['latest']=max(dates) if dates else None
                    self.store.put('runs',run)
            statuses=[r['status'] for r in run['sources']]
            run['status']='not_covered' if not statuses else 'completed' if all(s=='completed' for s in statuses) else 'failed' if all(s=='failed' for s in statuses) else 'partial'
        except Stopped:run['status']='cancelled'
        except Exception:run['status']='failed'
        finally:
            run['ended']=now()
            try:self.store.put('runs',run)
            finally:
                self.state=dict(running=False,message='',run_id=run['id']);self.lock.release()

    def scheduler(self):
        while True:
            try: self.tick()
            except Exception: self.state['message']='定时检查暂时失败，将自动重试；请检查本机存储'
            time.sleep(5)

    def tick(self):
        with self.settings_lock:
            self._tick_locked()

    def _tick_locked(self):
        for saved in self.store.all('saved'):
            if saved.get('enabled') and saved['next_run'] <= now():
                if self.start(saved['filters']):
                    saved['next_run']=next_check(saved)
                    # Do not resurrect a query deleted while a fast scan completed.
                    with self.store.db() as db:
                        db.execute('UPDATE saved SET data=? WHERE id=?',(json.dumps(saved,ensure_ascii=False),saved['id']))
                break
