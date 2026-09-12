"""Bounded directory health probes; no detail pages, attachments or identity data."""
import hashlib
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .notices import Fetcher, Stopped, listing, now
from .source_catalog import catalog
from .http_transport import failure_reason


def probe(source, cancel, fetcher=Fetcher):
    result = dict(id=source['id'], name=source['name'], url=source['url'], enabled=source['enabled'],
                  checked_at=now(), status='failed', recognized=0, reason='')
    reader = fetcher(source, cancel)
    try:
        listing_url = source.get('listing_url') or source['url']
        html = reader.get(listing_url)
        if source.get('portal'):
            soup = BeautifulSoup(html, 'html.parser')
            found = {}
            labels = re.compile(r'招考|招录|招聘|拟聘|人事考试|人事信息|公示公告|事业单位')
            for anchor in soup.select('a[href]'):
                title = (anchor.get('title') or anchor.get_text(' ', strip=True)).strip()
                target = urljoin(source['url'], anchor['href']).split('#')[0]
                parsed = urlparse(target)
                # Discover navigation only, not announcements or attachments.
                if not 2 <= len(title) <= 24 or not labels.search(title) or re.search(r'20\d{2}|公示名单', title): continue
                if parsed.scheme not in ('http','https') or parsed.hostname != urlparse(source['url']).hostname or parsed.port not in (None,443) or parsed.username or parsed.password: continue
                # Official HTTPS portals sometimes retain HTTP navigation hrefs.
                # Probe only the same-host HTTPS equivalent, still as a candidate.
                target = parsed._replace(scheme='https').geturl()
                if re.search(r'\.(pdf|docx?|xlsx?|zip|rar)(?:$|\?)', target, re.I): continue
                if re.search(r'/content/|post_\d|/t\d{8}_|/art_\d|/article(?:_|/)|/c/\d{4}-\d{2}-\d{2}/', parsed.path, re.I): continue
                found[target] = dict(title=title, url=target)
            result.update(status='portal_checked' if soup.title else 'needs_adapter', discovered=list(found.values()),
                          reason=f'门户首页发现{len(found)}个候选栏目链接；尚未接入公告索引，也未跟进读取这些链接。')
            return result
        try:
            parse_source = dict(source, url=urljoin(source['url'], '.')) if not source['enabled'] and source['url'].endswith('/index.html') else source
            items, next_url = listing(html, parse_source, listing_url)
            result.update(status='sample_ok' if source['enabled'] else 'candidate_sample', recognized=len(items),
                          reason='首页目录可解析；本次未核验后续分页和历史完整性。' if source['enabled'] else '当前页可识别样本，仍需分页适配和测试后才能加入正式索引。')
        except ValueError as error:
            soup = BeautifulSoup(html, 'html.parser')
            dynamic = bool(soup.select('script[querydata],script[url]'))
            result.update(status='needs_adapter', reason='发现动态目录加载标记，需要适配公开目录接口。' if dynamic else str(error))
    except Stopped:
        result.update(status='cancelled', reason='巡检已停止。')
    except Exception as error:
        result['reason'] = failure_reason(error, getattr(reader,'phase','directory'))
    finally:
        result['transport'] = getattr(reader,'transport_mode','default')
        reader.session.close()
    return result


def audit(root, folder, cancel=None, progress=None, fetcher=Fetcher):
    root, folder = Path(root), Path(folder)
    # Read the current handoff before any network probes.
    handoff = (root/'HANDOFF.md').read_bytes()
    report = dict(started=now(), ended=None, status='running', handoff_digest=hashlib.sha256(handoff).hexdigest(), results=[])
    cancel = cancel or threading.Event()
    entries = catalog()
    # Fixed catalog currently has distinct hosts; a future duplicate host stays sequential.
    groups = {}
    for source in entries:
        groups.setdefault(urlparse(source['url']).hostname, []).append(source)
    def group_probe(group):
        results = []
        for index, source in enumerate(group):
            if cancel.is_set() or (index and cancel.wait(2)): break
            results.append(probe(source, cancel, fetcher))
        return results
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(group_probe, group) for group in groups.values()]
        for future in as_completed(futures):
            report['results'].extend(future.result())
            if progress: progress(len(report['results']), len(entries))
    order = {s['id']: index for index, s in enumerate(entries)}
    report['results'].sort(key=lambda r: order[r['id']])
    report.update(ended=now(), status='cancelled' if cancel.is_set() else 'completed')
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder/'source-audit.tmp'
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(folder/'source-audit.json')
    with (folder/'source-audit-history.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(report, ensure_ascii=False)+'\n')
    return report


class SourceAuditor:
    def __init__(self, root, folder, collection_lock):
        self.root, self.folder, self.lock = root, Path(folder), collection_lock
        self.cancel = threading.Event()
        self.state = dict(running=False, message='')

    def latest(self):
        try: return json.loads((self.folder/'source-audit.json').read_text(encoding='utf-8'))
        except FileNotFoundError: return None
        except (OSError, ValueError): return dict(status='failed', results=[], reason='巡检报告读取失败。')

    def start(self):
        if not self.lock.acquire(blocking=False): return False
        self.cancel.clear()
        self.state = dict(running=True, message='准备巡检固定官方来源目录')
        try: threading.Thread(target=self._run, daemon=True).start()
        except Exception:
            self.state = dict(running=False, message='无法启动巡检')
            self.lock.release()
            raise
        return True

    def _run(self):
        try:
            audit(self.root, self.folder, self.cancel,
                  lambda done, total: self.state.update(message=f'已巡检 {done}/{total} 个登记入口'))
            self.state['message'] = '巡检结束；可访问不代表覆盖完整。'
        except Exception:
            self.state['message'] = '巡检失败，请检查本机存储和交接文件。'
        finally:
            self.state['running'] = False
            self.lock.release()
