"""Local announcement browser. Legacy personal-search APIs are not mounted."""
import argparse
import hashlib
import json
import os
import re
import secrets
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from wuzhong.notices import NoticeStore, NoticeEngine, SOURCES, REGIONS, compatible, relevance, validate_filters, now, stage, next_check, exam_year_from_title
from wuzhong.source_audit import SourceAuditor
from wuzhong.source_catalog import catalog

ROOT=Path(__file__).resolve().parent


def create_app(data_dir=None, schedule=False):
    app=Flask(__name__,static_folder='web',static_url_path='/assets')
    app.config['MAX_CONTENT_LENGTH']=16_000
    store=NoticeStore(data_dir or os.environ.get('WUZHONG_DATA_DIR',ROOT/'data'))
    engine=NoticeEngine(store,ROOT)
    auditor=SourceAuditor(ROOT,store.path.parent,engine.lock)
    app.extensions.update(store=store,engine=engine,auditor=auditor)
    token=secrets.token_urlsafe(32)

    @app.before_request
    def boundary():
        if request.host.split(':')[0] not in ('127.0.0.1','localhost'):
            return jsonify(error='仅允许本机访问'),403
        if request.method != 'GET' and request.headers.get('X-Local-Token') != token:
            return jsonify(error='请刷新页面后重试'),403

    @app.after_request
    def headers(response):
        response.headers['Cache-Control']='no-store'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https://ddragon.leagueoflegends.com; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.get('/')
    def index():return send_from_directory(ROOT/'web','notices.html')

    @app.get('/api/notices/state')
    def state():
        alerts=sorted(store.all('alerts'),key=lambda a:(not a['read'],a['created']),reverse=True)
        return jsonify(token=token,sources=SOURCES,catalog=catalog(),source_audit=dict(auditor.state,report=auditor.latest()),regions=REGIONS,engine=engine.state,runs=sorted(store.all('runs'),key=lambda r:r['started'],reverse=True)[:30],saved=store.all('saved'),alerts=alerts[:200],alert_total=len(alerts),unread=sum(not a['read'] for a in alerts),count=len(store.all('entries')),version='0.2.0')

    @app.post('/api/notices/source-audit')
    def source_audit():
        if not auditor.start(): return jsonify(error='已有采集或巡检在运行'),409
        return jsonify(ok=True)

    @app.post('/api/notices/source-audit/stop')
    def stop_source_audit():
        auditor.cancel.set()
        return jsonify(ok=True)

    @app.post('/api/notices/alerts/read')
    def read_alerts():
        d=request.get_json(silent=True)
        if not isinstance(d,dict) or not isinstance(d.get('ids'),list) or len(d['ids'])>200 or any(not isinstance(x,str) for x in d['ids']):
            return jsonify(error='提醒编号格式错误'),400
        with store.db() as db:
            for id in d['ids']:
                row=db.execute('SELECT data FROM alerts WHERE id=?',(id,)).fetchone()
                if row:
                    a=json.loads(row[0]);a['read']=True
                    db.execute('UPDATE alerts SET data=? WHERE id=?',(json.dumps(a,ensure_ascii=False),id))
        return jsonify(ok=True)

    @app.post('/api/notices/query')
    def query():
        try:f=validate_filters(request.get_json(silent=True))
        except (ValueError,TypeError) as e:return jsonify(error=str(e)),400
        records=[]
        for n in store.all('entries'):
            n=dict(n,exam_year=exam_year_from_title(n['title']))
            status=relevance(n,f)
            if status:records.append(dict(n,stage=stage(n['title']),match_status=status))
        records.sort(key=lambda n:(n['published'] or '',n['title']),reverse=True)
        return jsonify(filters=f,records=records,sources=[s for s in SOURCES if compatible(s,f)])

    @app.post('/api/notices/scan')
    def scan():
        try:f=validate_filters(request.get_json(silent=True))
        except (ValueError,TypeError) as e:return jsonify(error=str(e)),400
        if not any(compatible(s,f) for s in SOURCES):return jsonify(error='所选范围尚无已接入栏目'),400
        if not engine.start(f):return jsonify(error='已有检查在运行'),409
        return jsonify(ok=True,run_id=engine.state['run_id'])

    @app.post('/api/notices/stop')
    def stop():engine.cancel.set();return jsonify(ok=True)

    @app.post('/api/notices/saved')
    def save():
        with engine.settings_lock:
            return save_locked()

    def save_locked():
        if engine.state['running']:return jsonify(error='请等待当前检查结束后保存条件'),409
        try:
            d=request.get_json(silent=True)
            if not isinstance(d,dict):raise ValueError('条件格式错误')
            f=validate_filters(d.get('filters'))
            interval=d.get('interval_hours',24)
            if interval not in (6,12,24):raise ValueError('请选择6、12或24小时')
            enabled=d.get('enabled',False)
            if not isinstance(enabled,bool):raise ValueError('定时设置格式错误')
            notify=d.get('notify_enabled',False)
            mode=d.get('schedule_mode','interval');daily=d.get('daily_time','09:00')
            if not isinstance(notify,bool) or mode not in ('daily','interval') or not isinstance(daily,str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',daily):raise ValueError('提醒时间格式错误')
            if enabled and not any(compatible(s,f) for s in SOURCES):raise ValueError('所选范围尚无已接入栏目，不能开启定时')
            id=hashlib.sha256(json.dumps(f,sort_keys=True).encode()).hexdigest()[:24]
            # Preserve legacy query identity after adding optional scope fields.
            prior=next((s for s in store.all('saved') if validate_filters(s['filters'])==f),None)
            if prior:id=prior['id']
            item=dict(id=id,filters=f,interval_hours=interval,enabled=enabled,notify_enabled=notify,schedule_mode=mode,daily_time=daily,saved_at=now())
            item['next_run']=next_check(item)
            store.put('saved',item)
            return jsonify(item)
        except (ValueError,TypeError) as e:return jsonify(error=str(e)),400

    @app.delete('/api/notices/saved/<id>')
    def remove(id):
        with engine.settings_lock:
            if engine.state['running']:return jsonify(error='请等待当前检查结束后删除条件'),409
            store.delete(id);return jsonify(ok=True)

    if schedule:threading.Thread(target=engine.scheduler,daemon=True).start()
    return app


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765);parser.add_argument('--open',action='store_true')
    args=parser.parse_args()
    app=create_app(schedule=True)
    if args.open:threading.Timer(1.5,lambda:webbrowser.open(f'http://127.0.0.1:{args.port}')).start()
    app.run(host='127.0.0.1',port=args.port,debug=False,threaded=True,use_reloader=False)


if __name__=='__main__':
    main()
