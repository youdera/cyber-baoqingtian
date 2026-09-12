"""Cloud monitoring of official announcement metadata only."""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from wuzhong.notices import NoticeStore, NoticeEngine, validate_filters, now
from wuzhong import notices

SCAN_TIMEOUT_SECONDS = 90 * 60
CANCEL_GRACE_SECONDS = 120


def console(message):
    """Keep progress output readable without letting console encoding stop a scan."""
    stream = sys.stdout
    encoding = getattr(stream, 'encoding', None) or 'utf-8'
    text = str(message).encode(encoding, errors='backslashreplace').decode(encoding)
    print(text, file=stream, flush=True)


def markdown(value):
    return str(value).replace('@','＠').replace('<','＜').replace('>','＞').replace('[','［').replace(']','］').replace('\n',' ')


def filter_summary(filters):
    """Describe independent date/year constraints after shared validation."""
    publication = (f"{filters['date_from']} 至 {filters['date_to']}"
                   if filters.get('date_from') else '不限')
    examination = (f"{filters['year_from']} 至 {filters['year_to']}"
                   if filters.get('year_from') else '不限')
    area = {'province': '省内招录', 'national': '全国／中央招录',
            'all': '全部已接入范围'}[filters.get('area_scope', 'all')]
    if filters.get('region'):
        area += f" · {filters['region']}"
    return [f'公告发布时间：{publication}', f'招考年度：{examination}',
            f'招录范围：{markdown(area)}',
            '公告发布时间与招考年度分别筛选；同时设置时需同时符合。']


def initialized_sources(previous):
    """Read acknowledged per-source baselines, including the old health marker."""
    if 'sources' in previous:
        values = previous['sources']
        return {value for value in values if isinstance(value, str) and value} if isinstance(values, list) else set()
    health = previous.get('health')
    if isinstance(health, str):
        try:
            health = json.loads(health)
        except (json.JSONDecodeError, TypeError):
            return set()
    if not isinstance(health, list):
        return set()
    # Old health entries did not save page counts. completed/partial meant at
    # least one parsed page in the old engine; failed/unknown stays uninitialized.
    return {entry['id'] for entry in health
            if isinstance(entry, dict) and isinstance(entry.get('id'), str) and entry['id']
            and entry.get('status') in ('completed', 'partial')
            and ('pages' not in entry or type(entry['pages']) is int and entry['pages'] > 0)}


def rotated_sources(selected, previous, baseline):
    """Resume source order only from an acknowledged report for these filters."""
    cursor = None if baseline else previous.get('next_source')
    position = next((index for index, source in enumerate(selected)
                     if source['id'] == cursor), 0)
    return selected[position:] + selected[:position]


def wait_for_engine(engine):
    """Return after the worker releases its lock; never export while it writes."""
    deadline = time.monotonic() + SCAN_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if engine.lock.acquire(timeout=min(30, max(0, deadline-time.monotonic()))):
            engine.lock.release()
            return False
        console(engine.state.get('message') or '正在等待当前来源完成')
    # Completion can race the deadline, so check once more before cancelling.
    if engine.lock.acquire(blocking=False):
        engine.lock.release()
        return False
    engine.cancel.set()
    console('本轮检查时间预算已用完，正在等待采集线程结束后保存部分结果。')
    deadline = time.monotonic() + CANCEL_GRACE_SECONDS
    while time.monotonic() < deadline:
        if engine.lock.acquire(timeout=min(30, max(0, deadline-time.monotonic()))):
            engine.lock.release()
            return True
        console('正在等待当前请求及存储收尾。')
    raise RuntimeError('取消后采集线程未及时退出；本次不导出待确认报告或更新基线')


def finish_report(report, selected, timed_out):
    """Expose unvisited sources and choose a fair source-level checkpoint."""
    visited = {source['id'] for source in report['sources']}
    interrupted = [source['id'] for source in report['sources']
                   if source['status'] in ('cancelled', 'running')]
    # A request already in flight may raise a network error after cancellation
    # instead of Stopped. Do not initialize that final partial source either.
    if timed_out and report['sources'] and report['sources'][-1]['status'] == 'partial':
        interrupted.append(report['sources'][-1]['id'])
    missing = [source for source in selected if source['id'] not in visited]
    for source in report['sources']:
        if source['id'] in interrupted:
            source['status'] = 'partial' if source['pages'] else 'not_checked'
            source['incomplete_scan'] = True
            source['budget_exhausted'] = timed_out
            source['warnings'].append('本轮时间预算用完，当前栏目未查完' if timed_out
                                      else '检查中断，当前栏目未查完')
    for source in missing:
        report['sources'].append(dict(id=source['id'], name=source['name'],
            status='not_checked', pages=0, found=0, earliest=None, latest=None,
            transport='not_started', incomplete_scan=True, budget_exhausted=timed_out, warnings=[
                '本轮时间预算用完，尚未开始检查此来源' if timed_out
                else '检查提前结束，尚未开始检查此来源']))
    if timed_out or missing or interrupted:
        report['status'] = 'partial'
    report['budget_exhausted'] = timed_out
    # An exceptionally slow source must not prevent later sources being visited.
    # No page checkpoint is claimed: each source still starts at its first page.
    if missing:
        return missing[0]['id']
    if interrupted:
        return interrupted[0]
    return selected[0]['id'] if selected else None


def health_signature(health):
    """Ignore scan order when comparing current and legacy health markers."""
    if isinstance(health, str):
        try:
            health = json.loads(health)
        except (json.JSONDecodeError, TypeError):
            return None
    if not isinstance(health, list) or any(not isinstance(item, dict) for item in health):
        return None
    return json.dumps(sorted(health, key=lambda item: str(item.get('id', ''))),
                      sort_keys=True, ensure_ascii=False)


def run(folder, config):
    # These are per-run outputs, not collection history. A failed run must not
    # leave an older pending acknowledgement or report looking like this run's.
    for name in ('pending.json', 'report.md', 'alerts.json'):
        (Path('artifacts') / name).unlink(missing_ok=True)
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    store=NoticeStore(folder)
    filters=validate_filters(json.loads(Path(config).read_text(encoding='utf-8')))
    digest=hashlib.sha256(json.dumps(filters,sort_keys=True).encode()).hexdigest()
    marker=folder/'baseline.json'
    previous=json.loads(marker.read_text()) if marker.exists() else {}
    baseline=previous.get('filters')!=digest
    known_sources=set() if baseline else initialized_sources(previous)
    selected=[source for source in notices.SOURCES if notices.compatible(source,filters)]
    selected=rotated_sources(selected, previous, baseline)
    initializing_sources={source['id'] for source in selected} - known_sources
    # This store is dedicated to a single cloud watch, never the local user's database.
    store.put('saved',dict(id='cloud',enabled=True,notify_enabled=True,filters=filters,
                          initializing_sources=sorted(initializing_sources)))
    engine=NoticeEngine(store,ROOT)
    engine.source_order=[source['id'] for source in selected]
    if not engine.start(filters):
        raise RuntimeError('无法启动本轮检查')
    timed_out=wait_for_engine(engine)
    report=next(r for r in store.all('runs') if r['id']==engine.state['run_id'])
    next_source=finish_report(report, selected, timed_out)
    store.put('runs', report)
    alerts=[a for a in store.all('alerts') if not a['read']]
    health=[dict(id=s['id'],status=s['status'],warnings=s['warnings']) for s in report['sources']]
    health_key=health_signature(health)
    changed_health=health_key!=health_signature(previous.get('health'))
    read_sources={source['id'] for source in report['sources']
                  if source['pages'] > 0 and not source.get('incomplete_scan')}
    acknowledged_sources=known_sources | read_sources
    lines=['# 官方公示检查报告', '', f'检查时间（UTC）：{now()}',
           f"本轮状态：{report['status']}",
           *filter_summary(filters), '',
           '仅覆盖已接入栏目；不读取名单附件、不查询个人。', '']
    for s in report['sources']:
        lines.append(f"- {markdown(s['name'])}：{s['status']}，{s['pages']}页、{s['found']}条目录记录。{markdown('；'.join(s['warnings']))}")
    if not health:lines.append('- 所选范围没有已接入来源。')
    if timed_out:
        lines.extend(['', f'本轮达到 {SCAN_TIMEOUT_SECONDS // 60} 分钟检查预算；已等待采集线程结束，以上保留已读取、未完成及尚未检查的来源。'])
    if timed_out or any(source['status'] == 'not_checked' for source in report['sources']):
        next_name=next((source['name'] for source in selected if source['id'] == next_source), '')
        if next_name:
            lines.append('报告确认后，下次从“'+markdown(next_name)+'”开始轮转检查。轮转按来源进行，每个栏目仍从首页开始，不是从中断页续采。')
    lines.extend(['', '首次运行、缓存丢失或条件改变：建立基线，不逐条推送历史公告。' if baseline else f'未读公告提醒：{len(alerts)}条。'])
    if initializing_sources:
        ready=initializing_sources & read_sources
        pending=initializing_sources - read_sources
        lines.append('新增或尚未初始化的来源首次建立独立基线，不逐条推送历史公告；已有来源的正常更新提醒不受影响。')
        if ready:
            lines.append('本轮已读取并完成当前配置的检查窗口、待报告确认后记为已初始化：'+
                         '、'.join(markdown(source['name']) for source in selected if source['id'] in ready)+'。')
        if pending:
            lines.append('本轮未读到目录或检查提前中断，尚未建立基线，下次继续首次检查：'+
                         '、'.join(markdown(source['name']) for source in selected if source['id'] in pending)+'。')
    if not baseline:
        for a in alerts[:100]:
            label='信息待核对' if a['match_status']=='review' else '符合条件'
            lines.append(f"- [{markdown(a['title'])}]({a['url']}) · {a['event']} · {label}")
        if len(alerts)>100:lines.append(f'- 还有{len(alerts)-100}条，详见本次运行的报告附件。')
    text='\n'.join(lines)+'\n'
    Path('artifacts').mkdir(exist_ok=True)
    Path('artifacts/report.md').write_text(text,encoding='utf-8')
    Path('artifacts/alerts.json').write_text(json.dumps([] if baseline else alerts,ensure_ascii=False,indent=2),encoding='utf-8')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:f.write(text)
    should_notify=bool((alerts and not baseline) or changed_health or baseline)
    Path('artifacts/pending.json').write_text(json.dumps(dict(ids=[a['id'] for a in alerts],baseline=dict(filters=digest,health=health_key,sources=sorted(acknowledged_sources),next_source=next_source))),encoding='utf-8')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write(f'notify={str(should_notify).lower()}\n')
    console(f"status={report['status']}; alerts={len(alerts)}; baseline={baseline}")


def acknowledge(folder):
    store=NoticeStore(folder)
    pending=json.loads(Path('artifacts/pending.json').read_text())
    with store.db() as db:
        for id in pending['ids']:
            row=db.execute('SELECT data FROM alerts WHERE id=?',(id,)).fetchone()
            if row:
                alert=json.loads(row[0]);alert['read']=True
                db.execute('UPDATE alerts SET data=? WHERE id=?',(json.dumps(alert,ensure_ascii=False),id))
    (Path(folder)/'baseline.json').write_text(json.dumps(pending['baseline']),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',default='data/cloud')
    parser.add_argument('--config',default='cloud-watch.json')
    parser.add_argument('--ack',action='store_true')
    args=parser.parse_args()
    if args.ack:acknowledge(args.data_dir)
    else:run(args.data_dir,args.config)
