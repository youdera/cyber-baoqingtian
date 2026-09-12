import tempfile
import unittest
from unittest.mock import Mock, patch

from notice_app import create_app, main
from wuzhong.notices import validate_filters, relevance, exam_year_from_title


class TimeFilterTests(unittest.TestCase):
    def test_public_launcher_main_is_callable_and_preserves_local_host(self):
        app=Mock()
        with patch('notice_app.create_app',return_value=app),patch('sys.argv',['app.py','--port','8766']):
            main()
        app.run.assert_called_once_with(host='127.0.0.1',port=8766,debug=False,threaded=True,use_reloader=False)

    def test_ambiguous_title_year_does_not_hide_old_cached_notice(self):
        title='模拟单位面向2025年应届毕业生的2026年度拟录用人员公示'
        self.assertIsNone(exam_year_from_title(title))
        self.assertIsNone(exam_year_from_title('模拟单位面向2025年应届毕业生拟录用公示'))
        self.assertIsNone(exam_year_from_title('模拟单位2026年9月拟录用公示'))
        self.assertEqual(exam_year_from_title('模拟单位2026年度拟录用公示'),2026)
        with tempfile.TemporaryDirectory() as d:
            app=create_app(d);c=app.test_client();store=app.extensions['store']
            h={'X-Local-Token':c.get('/api/notices/state').json['token']}
            n=dict(id='old',title=title,url='https://www.stats.gov.cn/example',source='模拟来源',source_id='stats',published='2026-05-01',exam_year=2025,region='',kind='国考')
            store.record(n)
            result=c.post('/api/notices/query',headers=h,json={'year_from':2026}).json
            self.assertEqual(result['records'][0]['match_status'],'review')
            self.assertIsNone(result['records'][0]['exam_year'])
            self.assertEqual(store.all('entries')[0]['exam_year'],2025)

    def test_reverted_metadata_produces_a_new_change_alert(self):
        with tempfile.TemporaryDirectory() as d:
            app=create_app(d);store=app.extensions['store']
            store.put('saved',dict(id='watch',enabled=True,notify_enabled=True,filters=validate_filters({'year_from':2026})))
            item=dict(id='synthetic',title='2026年模拟单位拟录用公示',url='https://www.stats.gov.cn/example',source='模拟来源',source_id='stats',published='2026-05-01',exam_year=2026,region='',kind='国考')
            store.record(item);store.record(dict(item,title=item['title']+'（更正）'));store.record(item);store.record(item)
            self.assertEqual(len(store.all('alerts')),3)
            self.assertEqual(store.all('entries')[0]['revision'],3)

    def test_independent_ranges_and_one_endpoint(self):
        self.assertEqual(validate_filters({'month_from':'2024-02'})['date_to'],'2024-02-29')
        self.assertEqual(validate_filters({'month_to':'2024-02'})['date_from'],'2024-02-01')
        for raw in [{'year_from':2025},{'year_to':'2025'}]:
            f=validate_filters(raw)
            self.assertEqual((f['year_from'],f['year_to']),(2025,2025))
            self.assertIsNone(f['date_from'])
        for raw in [{},{'month_from':'','year_from':''},{'year_from':2026,'year_to':2025},{'year_from':'oops'},{'month_from':'2025-13'}]:
            with self.assertRaises(ValueError):validate_filters(raw)

    def test_cross_year_publication_and_missing_metadata(self):
        n=dict(source_id='stats',published='2026-05-01',exam_year=2025,region='',kind='国考')
        year=validate_filters({'year_from':2025})
        month=validate_filters({'month_from':'2026-05'})
        both=validate_filters({'month_from':'2026-05','year_from':2025})
        for f in [year,month,both]:self.assertEqual(relevance(n,f),'matched')
        self.assertIsNone(relevance(n,validate_filters({'month_from':'2025-05','year_from':2025})))
        self.assertEqual(relevance(dict(n,published=None),year),'matched')
        self.assertEqual(relevance(dict(n,published=None),month),'review')
        self.assertEqual(relevance(dict(n,exam_year=None),year),'review')
        self.assertEqual(relevance(dict(n,exam_year=None),month),'matched')

    def test_year_only_query_saved_watch_and_alert(self):
        with tempfile.TemporaryDirectory() as d:
            app=create_app(d);c=app.test_client();store=app.extensions['store']
            h={'X-Local-Token':c.get('/api/notices/state').json['token']}
            f=dict(year_from=2025,area_scope='national',notice_scope='public')
            saved=c.post('/api/notices/saved',headers=h,json=dict(filters=f,enabled=True,notify_enabled=True))
            self.assertEqual(saved.status_code,200)
            n=dict(id='synthetic',title='2025年度模拟单位拟录用公示',url='https://www.stats.gov.cn/example',source='模拟来源',source_id='stats',published='2026-05-01',exam_year=2025,region='',kind='国考',stage='录聘公示')
            store.record(n)
            r=c.post('/api/notices/query',headers=h,json=f)
            self.assertEqual(r.status_code,200);self.assertEqual(len(r.json['records']),1)
            self.assertIsNone(r.json['filters']['month_from'])
            self.assertEqual(c.get('/api/notices/state').json['unread'],1)
            restored=c.post('/api/notices/saved',headers=h,json=dict(filters=saved.json['filters'],enabled=False))
            self.assertEqual(restored.json['id'],saved.json['id'])

    def test_older_unread_alerts_remain_accessible(self):
        with tempfile.TemporaryDirectory() as d:
            app=create_app(d);c=app.test_client();store=app.extensions['store']
            for i in range(205):store.put('alerts',dict(id=str(i),created=f'2026-{i:04}',read=False))
            first=c.get('/api/notices/state').json
            self.assertEqual(len(first['alerts']),200);self.assertEqual(first['unread'],205)
            c.post('/api/notices/alerts/read',headers={'X-Local-Token':first['token']},json={'ids':[a['id'] for a in first['alerts']]})
            remaining=c.get('/api/notices/state').json
            self.assertEqual(remaining['unread'],5)
            self.assertEqual(sum(not a['read'] for a in remaining['alerts']),5)


if __name__=='__main__':unittest.main()
