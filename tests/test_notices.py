import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from notice_app import create_app
from wuzhong.notices import SOURCES, Fetcher, NoticeStore, NoticeEngine, Stopped, listing, validate_filters, relevance, stage


def fixture(page=0):
    return f'''<html><script>var m_nRecordCount="2";var m_nPageSize=1;var m_nCurrPage={page};</script>
    <ul><li><span>2024-02-{28+page}</span><a href="./202402/t202402{28+page}_123{page}.html" title="2023年度模拟招录公告{page}">公告</a></li></ul>
    <table><tr><td>虚构人员私密字段不得持久化</td></tr></table><a href="名单.xlsx">附件</a></html>'''


class NoticeTests(unittest.TestCase):
    def test_short_publication_title_forms_are_included_in_public_filter(self):
        filters=validate_filters(dict(year_from=2026,notice_scope='public'))
        item=listing(fixture(),SOURCES[0],SOURCES[0]['url'])[0][0]
        for title in ['2026年模拟单位拟聘公示','2026年模拟单位拟录人员公示',
                      '2026年模拟单位拟聘名单公示','2026年模拟单位拟录名单公示']:
            with self.subTest(title=title):
                self.assertEqual(stage(title),'录聘公示')
                self.assertEqual(relevance(dict(item,title=title,exam_year=2026),filters),'matched')
        self.assertNotEqual(stage('2026年模拟单位招聘报名公告'),'录聘公示')

    def test_area_scope_filters_sources_and_legacy_entries(self):
        from wuzhong.notices import compatible
        base=dict(month_from='2024-02',month_to='2024-02')
        provincial=validate_filters(dict(base,area_scope='province',region='广东'))
        national=validate_filters(dict(base,area_scope='national'))
        self.assertEqual([s['id'] for s in SOURCES if compatible(s,provincial)],['guangdong','zhaoqing_recruitment','zhaoqing_civil','yangjiang_civil'])
        self.assertEqual([s['id'] for s in SOURCES if compatible(s,national)],['stats'])
        item=listing(fixture(),SOURCES[0],SOURCES[0]['url'])[0][0]
        self.assertIsNone(relevance(item,provincial))
        self.assertEqual(relevance(item,national),'matched')
        self.assertEqual(relevance(item,validate_filters(base)),'matched')
        self.assertIsNone(relevance(dict(item,source_id='unregistered'),national))
        for extra in [dict(area_scope='province'),dict(area_scope='national',region='广东'),dict(area_scope='invalid')]:
            with self.assertRaises(ValueError):validate_filters(dict(base,**extra))

    def test_query_reclassifies_stale_stage_without_changing_stored_notice(self):
        with tempfile.TemporaryDirectory() as d:
            app=create_app(d);client=app.test_client()
            item=listing(fixture(),SOURCES[0],SOURCES[0]['url'])[0][0]
            item.update(title='2024年模拟单位拟聘人员的公示',stage='招录信息')
            app.extensions['store'].record(item)
            token=client.get('/api/notices/state').get_json()['token']
            response=client.post('/api/notices/query',json=dict(month_from='2024-02',month_to='2024-02'),headers={'X-Local-Token':token})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.get_json()['records'][0]['stage'],'录聘公示')
            self.assertEqual(app.extensions['store'].all('entries')[0]['stage'],'招录信息')

    def test_cancellation_releases_run_lock(self):
        ready=threading.Event()
        class WaitingFetcher:
            def __init__(self,s,c):self.cancel=c;self.session=Mock()
            def get(self,url):
                ready.set();self.cancel.wait(3);raise Stopped()
        with tempfile.TemporaryDirectory() as d:
            engine=NoticeEngine(NoticeStore(d),d,WaitingFetcher)
            engine.start(validate_filters(dict(month_from='2024-02',month_to='2024-02')))
            self.assertTrue(ready.wait(2));engine.cancel.set()
            self.assertTrue(engine.lock.acquire(timeout=3));engine.lock.release()
            self.assertFalse(engine.state['running'])
            self.assertEqual(engine.store.all('runs')[0]['status'],'cancelled')

    def test_start_storage_error_releases_run_lock(self):
        with tempfile.TemporaryDirectory() as d:
            store=NoticeStore(d);engine=NoticeEngine(store,d)
            with patch.object(store,'put',side_effect=OSError('模拟磁盘失败')):
                with self.assertRaises(OSError):engine.start({})
            self.assertFalse(engine.state['running'])
            self.assertTrue(engine.lock.acquire(blocking=False));engine.lock.release()

    def test_source_restriction_and_private_dns(self):
        f=Fetcher(SOURCES[0],threading.Event())
        try:
            with self.assertRaises(ValueError):f.raw('https://127.0.0.1/secret')
            with patch('wuzhong.notices.socket.getaddrinfo',return_value=[(0,0,0,'',('10.0.0.1',443))]):
                with self.assertRaises(ValueError):f.raw(SOURCES[0]['url'])
        finally:f.session.close()

    def test_schedule_coalesces_missed_runs(self):
        with tempfile.TemporaryDirectory() as d:
            store=NoticeStore(d);engine=NoticeEngine(store,d)
            store.put('saved',dict(id='a',enabled=True,next_run='2000-01-01T00:00:00+00:00',interval_hours=24,filters={}))
            engine.start=Mock(return_value=True)
            engine.tick();engine.tick()
            self.assertEqual(engine.start.call_count,1)
            self.assertEqual(stage('2026年度模拟单位拟聘人员公示'),'录聘公示')

    def test_month_end_leap_cross_year_and_order(self):
        f=validate_filters(dict(month_from='2024-02',month_to='2024-02'))
        self.assertEqual(f['date_to'],'2024-02-29')
        self.assertEqual(validate_filters(dict(month_from='2023-12',month_to='2024-03'))['date_to'],'2024-03-31')
        for d in [dict(month_from='2024-03',month_to='2024-02'),dict(month_from='2024-02',month_to='2024-13'),dict(month_from='2024-02',month_to='2024-02',year_from=2026,year_to=2015)]:
            with self.assertRaises(ValueError):validate_filters(d)

    def test_optional_year_and_unknown_date(self):
        f=validate_filters(dict(month_from='2024-02',month_to='2024-02',year_from=2023,year_to=2024))
        n=dict(published='2024-02-29',exam_year=2023,region='',kind='国考')
        self.assertEqual(relevance(n,f),'matched')
        self.assertIsNone(relevance(dict(n,published='2024-03-01'),f))
        self.assertIsNone(relevance(dict(n,exam_year=2022),f))
        self.assertEqual(relevance(dict(n,published=None),f),'review')
        self.assertEqual(relevance(dict(n,exam_year=None),f),'review')

    def test_metadata_only_and_pagination(self):
        items,nxt=listing(fixture(),SOURCES[0],SOURCES[0]['url'])
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['published'],'2024-02-28')
        self.assertTrue(nxt.endswith('index_1.html'))
        self.assertNotIn('私密',str(items));self.assertNotIn('xlsx',str(items))
        with self.assertRaises(ValueError):listing('<html>登录验证码</html>',SOURCES[0],SOURCES[0]['url'])

    def test_unknown_date_not_taken_from_url(self):
        items,_=listing(fixture().replace('<span>2024-02-28</span>',''),SOURCES[0],SOURCES[0]['url'])
        self.assertIsNone(items[0]['published'])

    def test_index_dedup_updates_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            store=NoticeStore(d);item=listing(fixture(),SOURCES[0],SOURCES[0]['url'])[0][0]
            self.assertEqual(store.record(item),(1,0));self.assertEqual(store.record(item),(0,0))
            self.assertEqual(store.record(dict(item,title='2023年度模拟更正公告')),(0,1))
            self.assertEqual(len(store.all('entries')),1)
            store.put('runs',dict(id='r',status='running'))
            restarted=NoticeStore(d)
            self.assertEqual(restarted.all('runs')[0]['status'],'interrupted')
            self.assertNotIn('私密',str(restarted.all('entries')))

    def test_engine_reads_directory_only_and_preserves_success(self):
        requests=[]
        class FakeFetcher:
            def __init__(self,s,c):self.source=s;self.session=Mock()
            def get(self,url):
                requests.append(url)
                if self.source['id']=='fujian':raise ValueError('模拟网络失败')
                return fixture(1 if 'index_1' in url else 0)
        with tempfile.TemporaryDirectory() as d:
            engine=NoticeEngine(NoticeStore(d),Path(d),FakeFetcher)
            f=validate_filters(dict(month_from='2024-02',month_to='2024-02'))
            with patch('wuzhong.notices.SOURCES', SOURCES[:2]):
                self.assertTrue(engine.start(f))
                self.assertTrue(engine.lock.acquire(timeout=5));engine.lock.release()
            self.assertEqual(len(engine.store.all('entries')),2)
            self.assertEqual(engine.store.all('runs')[0]['status'],'partial')
            self.assertEqual(len(requests),3)
            self.assertFalse(any('t2024' in u or '.xlsx' in u for u in requests))

    def test_api_boundary_query_and_saved(self):
        with tempfile.TemporaryDirectory() as d:
            app=create_app(d);c=app.test_client();token=c.get('/api/notices/state').json['token'];h={'X-Local-Token':token}
            with c.get('/') as response:self.assertEqual(response.status_code,200)
            self.assertEqual(c.get('/api/state').status_code,404)
            self.assertEqual(c.get('/api/notices/state',headers={'Host':'attacker.example'}).status_code,403)
            f=dict(month_from='2024-01',month_to='2024-02')
            self.assertEqual(c.post('/api/notices/query',json=f).status_code,403)
            self.assertEqual(c.post('/api/notices/query',headers=h,json=f).json['filters']['date_to'],'2024-02-29')
            for _ in range(2):self.assertEqual(c.post('/api/notices/saved',headers=h,json={'filters':f,'enabled':False}).status_code,200)
            self.assertEqual(len(c.get('/api/notices/state').json['saved']),1)
            self.assertEqual(c.post('/api/notices/saved',headers=h,json={'filters':f,'enabled':'false'}).status_code,400)


if __name__=='__main__':unittest.main()
