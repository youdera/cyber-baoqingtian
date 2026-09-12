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


def markdown(value):
    return str(value).replace('@','＠').replace('<','＜').replace('>','＞').replace('[','［').replace(']','］').replace('\n',' ')


def run(folder, config):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    store=NoticeStore(folder)
    filters=validate_filters(json.loads(Path(config).read_text(encoding='utf-8')))
    digest=hashlib.sha256(json.dumps(filters,sort_keys=True).encode()).hexdigest()
    marker=folder/'baseline.json'
    previous=json.loads(marker.read_text()) if marker.exists() else {}
    baseline=previous.get('filters')!=digest
    # This store is dedicated to a single cloud watch, never the local user's database.
    store.put('saved',dict(id='cloud',enabled=True,notify_enabled=True,filters=filters))
    engine=NoticeEngine(store,ROOT)
    engine.start(filters)
    deadline = time.monotonic() + 1500
    while not engine.lock.acquire(timeout=min(30, max(0, deadline-time.monotonic()))):
        print(engine.state.get('message') or '正在等待当前来源完成', flush=True)
        if time.monotonic() >= deadline:
            engine.cancel.set()
            raise RuntimeError('检查超时；本次不更新缓存基线')
    engine.lock.release()
    report=next(r for r in store.all('runs') if r['id']==engine.state['run_id'])
    alerts=[a for a in store.all('alerts') if not a['read']]
    health=[dict(id=s['id'],status=s['status'],warnings=s['warnings']) for s in report['sources']]
    health_key=json.dumps(health,sort_keys=True,ensure_ascii=False)
    changed_health=health_key!=previous.get('health')
    lines=['# 官方公示检查报告', '', f'检查时间（UTC）：{now()}',
           f"公告日期：{filters['date_from']} 至 {filters['date_to']}；招考年度：{filters['year_from'] or '不限'} 至 {filters['year_to'] or '不限'}",'',
           '仅覆盖已接入栏目；不读取名单附件、不查询个人。', '']
    for s in report['sources']:
        lines.append(f"- {markdown(s['name'])}：{s['status']}，{s['pages']}页、{s['found']}条目录记录。{markdown('；'.join(s['warnings']))}")
    if not health:lines.append('- 所选范围没有已接入来源。')
    lines.extend(['', '首次运行、缓存丢失或条件改变：建立基线，不逐条推送历史公告。' if baseline else f'未读公告提醒：{len(alerts)}条。'])
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
    Path('artifacts/pending.json').write_text(json.dumps(dict(ids=[a['id'] for a in alerts],baseline=dict(filters=digest,health=health_key))),encoding='utf-8')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write(f'notify={str(should_notify).lower()}\n')
    print(f"status={report['status']}; alerts={len(alerts)}; baseline={baseline}")


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
