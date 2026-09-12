import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from notice_app import create_app
from wuzhong.notices import NoticeStore, validate_filters, next_check


class AlertTests(unittest.TestCase):
    def test_scope_source_and_uncovered_alarm(self):
        with tempfile.TemporaryDirectory() as d:
            app=create_app(d);c=app.test_client();h={'X-Local-Token':c.get('/api/notices/state').json['token']}
            f=dict(month_from='2026-01',month_to='2026-12',source_id='fujian',kind='国考')
            # Fujian has unknown source kind, but incompatible explicit region must reject.
            f['region']='北京'
            self.assertEqual(c.post('/api/notices/saved',headers=h,json=dict(filters=f,enabled=True)).status_code,400)
            for field,value in [('source_id','unknown'),('notice_scope','people')]:
                with self.assertRaises(ValueError):validate_filters(dict(month_from='2026-01',month_to='2026-12',**{field:value}))

    def test_notifications_are_transactional_deduplicated_and_pauseable(self):
        with tempfile.TemporaryDirectory() as d:
            store=NoticeStore(d)
            f=validate_filters(dict(month_from='2026-01',month_to='2026-12',notice_scope='public',year_from=2026,year_to=2026))
            s=dict(id='watch',enabled=True,notify_enabled=True,filters=f)
            store.put('saved',s)
            n=dict(id='one',title='模拟单位2026年拟录用公示',url='https://www.stats.gov.cn/example',source='模拟来源',source_id='stats',published='2026-05-01',exam_year=2026,region='',kind='国考',stage='录聘公示')
            store.record(n);store.record(n)
            self.assertEqual(len(store.all('alerts')),1)
            store.record(dict(n,title='模拟单位2026年拟录用公示（更正）'))
            self.assertEqual(len(store.all('alerts')),2)
            store.record(dict(n,id='exam',title='模拟单位2026年面试公告'))
            store.record(dict(n,id='old',published='2025-05-01'))
            self.assertEqual(len(store.all('alerts')),2)
            store.record(dict(n,id='unknown',exam_year=None))
            self.assertEqual(store.all('alerts')[-1]['match_status'],'review')
            store.put('saved',dict(s,enabled=False));store.record(dict(n,id='paused'))
            self.assertEqual(len(NoticeStore(d).all('alerts')),3)

    def test_alarm_settings_and_read_state(self):
        with tempfile.TemporaryDirectory() as d:
            app=create_app(d);c=app.test_client();h={'X-Local-Token':c.get('/api/notices/state').json['token']}
            f=dict(month_from='2026-01',month_to='2026-12',notice_scope='public')
            data=dict(filters=f,enabled=True,notify_enabled=True,schedule_mode='daily',daily_time='09:17')
            r=c.post('/api/notices/saved',headers=h,json=data)
            self.assertEqual(r.status_code,200);self.assertEqual(r.json['daily_time'],'09:17')
            self.assertEqual(c.post('/api/notices/saved',headers=h,json=dict(data,daily_time='25:00')).status_code,400)
            app.extensions['store'].put('alerts',dict(id='a',created='2026',read=False))
            self.assertEqual(c.get('/api/notices/state').json['unread'],1)
            self.assertEqual(c.post('/api/notices/alerts/read',json={'ids':['a']}).status_code,403)
            c.post('/api/notices/alerts/read',headers=h,json={'ids':['a']})
            self.assertEqual(c.get('/api/notices/state').json['unread'],0)

    def test_daily_time_rolls_to_next_day(self):
        fixed=datetime(2026,9,12,2,0,tzinfo=timezone.utc)
        with patch('wuzhong.notices.datetime') as clock:
            clock.now.return_value=fixed
            due=next_check(dict(schedule_mode='daily',daily_time='09:17'))
        self.assertEqual(due,'2026-09-13T01:17:00+00:00')

if __name__=='__main__':unittest.main()
