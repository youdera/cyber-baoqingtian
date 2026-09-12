import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import cloud_watch
from wuzhong.notices import NoticeEngine, NoticeStore, SOURCES, relevance


class CloudWatchTests(unittest.TestCase):
    def test_independent_time_filters_and_report(self):
        """A 2025 exam announced in 2026 must work with either time dimension."""
        class FakeFetcher:
            def __init__(self, source, cancel): self.session = Mock()
            def get(self, url):
                return '''<script>m_nRecordCount=1;m_nPageSize=10;m_nCurrPage=0;</script>
                <li><a href="./202609/t20260901_123.html">2025年模拟单位拟录用公示</a><span>2026-09-01</span></li>'''

        cases = [
            ({'month_from': '2026-09'}, '2026-09-01 至 2026-09-30', '不限', True),
            ({'month_to': '2026-09'}, '2026-09-01 至 2026-09-30', '不限', True),
            ({'year_from': 2025}, '不限', '2025 至 2025', True),
            ({'year_to': 2025}, '不限', '2025 至 2025', True),
            ({'month_from': '2026-09', 'year_from': 2025},
             '2026-09-01 至 2026-09-30', '2025 至 2025', True),
            ({'month_from': '2026-09', 'year_from': 2024},
             '2026-09-01 至 2026-09-30', '2024 至 2024', False),
        ]
        previous = Path.cwd()
        for config, publication, examination, matches in cases:
            with self.subTest(config=config), tempfile.TemporaryDirectory() as root:
                try:
                    os.chdir(root)
                    config = dict(config, notice_scope='public', area_scope='national')
                    Path('watch.json').write_text(json.dumps(config), encoding='utf-8')
                    def engine(store, directory): return NoticeEngine(store, directory, FakeFetcher)
                    with patch.object(cloud_watch, 'NoticeEngine', side_effect=engine), patch('wuzhong.notices.SOURCES', SOURCES[:1]), patch.dict(os.environ, {'GITHUB_OUTPUT': '', 'GITHUB_STEP_SUMMARY': ''}):
                        cloud_watch.run('state', 'watch.json')
                    report = Path('artifacts/report.md').read_text(encoding='utf-8')
                    self.assertIn(f'公告发布时间：{publication}', report)
                    self.assertIn(f'招考年度：{examination}', report)
                    self.assertIn('招录范围：全国／中央招录', report)
                    self.assertNotIn('None', report)
                    store = NoticeStore('state')
                    self.assertEqual(len(store.all('alerts')), 0)
                    self.assertEqual(sum(relevance(item, store.all('saved')[0]['filters']) is not None
                                         for item in store.all('entries')), int(matches))
                    self.assertEqual(json.loads(Path('artifacts/alerts.json').read_text()), [])
                    saved = store.all('saved')[0]['filters']
                    if 'month_from' not in config and 'month_to' not in config:
                        self.assertIsNone(saved['date_from'])
                        self.assertIsNone(saved['date_to'])
                finally:
                    os.chdir(previous)

    def test_equivalent_single_year_config_preserves_baseline(self):
        class FakeFetcher:
            def __init__(self, source, cancel): self.session = Mock()
            def get(self, url):
                return '''<script>m_nRecordCount=1;m_nPageSize=10;m_nCurrPage=0;</script>
                <li><a href="./202609/t20260901_123.html">2025年模拟单位拟录用公示</a><span>2026-09-01</span></li>'''
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as root:
            try:
                os.chdir(root)
                config = dict(year_from=2025, notice_scope='public')
                def engine(store, directory): return NoticeEngine(store, directory, FakeFetcher)
                with patch.object(cloud_watch, 'NoticeEngine', side_effect=engine), patch('wuzhong.notices.SOURCES', SOURCES[:1]), patch.dict(os.environ, {'GITHUB_OUTPUT': str(Path(root)/'output.txt'), 'GITHUB_STEP_SUMMARY': ''}):
                    Path('watch.json').write_text(json.dumps(config), encoding='utf-8')
                    cloud_watch.run('state', 'watch.json')
                    cloud_watch.acknowledge('state')
                    config['year_to'] = 2025
                    Path('watch.json').write_text(json.dumps(config), encoding='utf-8')
                    cloud_watch.run('state', 'watch.json')
                    self.assertTrue(Path('output.txt').read_text().endswith('notify=false\n'))
                    self.assertIn('未读公告提醒：0条', Path('artifacts/report.md').read_text(encoding='utf-8'))
            finally:
                os.chdir(previous)

    def test_initialized_sources_migrates_only_known_successful_legacy_entries(self):
        legacy = dict(health=json.dumps([
            dict(id='stats', status='completed'), dict(id='fujian', status='partial'),
            dict(id='failed', status='failed'), dict(id='unknown', status='running'),
            dict(id='zero', status='partial', pages=0), dict(id=None, status='completed'),
        ]))
        self.assertEqual(cloud_watch.initialized_sources(legacy), {'stats', 'fujian'})
        self.assertEqual(cloud_watch.initialized_sources(dict(legacy, sources=['explicit'])), {'explicit'})
        for previous in ({}, {'health': 'not-json'}, {'health': 'null'}, {'health': {}},
                         dict(legacy, sources=None)):
            with self.subTest(previous=previous):
                self.assertEqual(cloud_watch.initialized_sources(previous), set())

    def test_new_source_baseline_does_not_suppress_existing_source_changes(self):
        titles = {'stats': '2026年模拟甲单位拟录用公示', 'fujian': '2026年模拟乙单位拟录用公示'}
        class FakeFetcher:
            def __init__(self, source, cancel): self.session, self.source = Mock(), source
            def get(self, url):
                return f'''<script>m_nRecordCount=1;m_nPageSize=10;m_nCurrPage=0;</script>
                <li><a href="./202609/t20260901_123.html">{titles[self.source['id']]}</a><span>2026-09-01</span></li>'''
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as root:
            try:
                os.chdir(root)
                Path('watch.json').write_text(json.dumps(dict(year_from=2026, notice_scope='public')), encoding='utf-8')
                def engine(store, directory): return NoticeEngine(store, directory, FakeFetcher)
                with patch.object(cloud_watch, 'NoticeEngine', side_effect=engine), patch.dict(os.environ, {'GITHUB_OUTPUT': '', 'GITHUB_STEP_SUMMARY': ''}):
                    with patch('wuzhong.notices.SOURCES', SOURCES[:1]):
                        cloud_watch.run('state', 'watch.json')
                        cloud_watch.acknowledge('state')
                    marker_path = Path('state/baseline.json')
                    marker = json.loads(marker_path.read_text())
                    self.assertEqual(marker['sources'], ['stats'])
                    # Reproduce deployment from the old marker format.
                    marker.pop('sources')
                    marker_path.write_text(json.dumps(marker), encoding='utf-8')
                    titles['stats'] += '（更正）'
                    with patch('wuzhong.notices.SOURCES', SOURCES[:2]):
                        cloud_watch.run('state', 'watch.json')
                        alerts = json.loads(Path('artifacts/alerts.json').read_text(encoding='utf-8'))
                        self.assertEqual([a['source_id'] for a in alerts], ['stats'])
                        self.assertEqual(NoticeStore('state').all('saved')[0]['initializing_sources'], ['fujian'])
                        pending = json.loads(Path('artifacts/pending.json').read_text())
                        self.assertEqual(pending['baseline']['sources'], ['fujian', 'stats'])
                        self.assertNotIn('sources', json.loads(marker_path.read_text()))
                        self.assertIn('已有来源的正常更新提醒不受影响', Path('artifacts/report.md').read_text(encoding='utf-8'))
                        cloud_watch.acknowledge('state')
                        self.assertEqual(json.loads(marker_path.read_text())['sources'], ['fujian', 'stats'])
                        titles['fujian'] += '（更正）'
                        cloud_watch.run('state', 'watch.json')
                        alerts = json.loads(Path('artifacts/alerts.json').read_text(encoding='utf-8'))
                        self.assertEqual([a['source_id'] for a in alerts], ['fujian'])
                        self.assertEqual(NoticeStore('state').all('saved')[0]['initializing_sources'], [])
            finally:
                os.chdir(previous)

    def test_first_source_failure_stays_uninitialized_until_a_page_is_read_and_acknowledged(self):
        failed = {'fujian'}
        class FakeFetcher:
            def __init__(self, source, cancel): self.session, self.source = Mock(), source
            def get(self, url):
                if self.source['id'] in failed:
                    raise OSError('模拟来源不可读取')
                return '''<script>m_nRecordCount=1;m_nPageSize=10;m_nCurrPage=0;</script>
                <li><a href="./202609/t20260901_123.html">2026年模拟单位拟录用公示</a><span>2026-09-01</span></li>'''
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as root:
            try:
                os.chdir(root)
                Path('watch.json').write_text(json.dumps(dict(year_from=2026, notice_scope='public')), encoding='utf-8')
                def engine(store, directory): return NoticeEngine(store, directory, FakeFetcher)
                with patch.object(cloud_watch, 'NoticeEngine', side_effect=engine), patch('wuzhong.notices.SOURCES', SOURCES[:2]), patch.dict(os.environ, {'GITHUB_OUTPUT': '', 'GITHUB_STEP_SUMMARY': ''}):
                    cloud_watch.run('state', 'watch.json')
                    self.assertEqual(json.loads(Path('artifacts/pending.json').read_text())['baseline']['sources'], ['stats'])
                    self.assertIn('本轮未读到目录，尚未建立基线', Path('artifacts/report.md').read_text(encoding='utf-8'))
                    cloud_watch.acknowledge('state')
                    failed.clear()
                    cloud_watch.run('state', 'watch.json')
                    self.assertEqual(NoticeStore('state').all('saved')[0]['initializing_sources'], ['fujian'])
                    self.assertEqual(NoticeStore('state').all('alerts'), [])
                    self.assertEqual(json.loads(Path('state/baseline.json').read_text())['sources'], ['stats'])
                    cloud_watch.acknowledge('state')
                    self.assertEqual(json.loads(Path('state/baseline.json').read_text())['sources'], ['fujian', 'stats'])
            finally:
                os.chdir(previous)

    def test_filter_change_reinitializes_previously_known_sources(self):
        title = ['2026年模拟单位拟录用公示']
        class FakeFetcher:
            def __init__(self, source, cancel): self.session = Mock()
            def get(self, url):
                return f'''<script>m_nRecordCount=1;m_nPageSize=10;m_nCurrPage=0;</script>
                <li><a href="./202609/t20260901_123.html">{title[0]}</a><span>2026-09-01</span></li>'''
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as root:
            try:
                os.chdir(root)
                config_path = Path('watch.json')
                config_path.write_text(json.dumps(dict(month_from='2026-09', notice_scope='public')), encoding='utf-8')
                def engine(store, directory): return NoticeEngine(store, directory, FakeFetcher)
                with patch.object(cloud_watch, 'NoticeEngine', side_effect=engine), patch('wuzhong.notices.SOURCES', SOURCES[:1]), patch.dict(os.environ, {'GITHUB_OUTPUT': '', 'GITHUB_STEP_SUMMARY': ''}):
                    cloud_watch.run('state', 'watch.json')
                    cloud_watch.acknowledge('state')
                    title[0] += '（更正）'
                    config_path.write_text(json.dumps(dict(year_from=2026, notice_scope='public')), encoding='utf-8')
                    cloud_watch.run('state', 'watch.json')
                    self.assertEqual(NoticeStore('state').all('saved')[0]['initializing_sources'], ['stats'])
                    self.assertEqual(NoticeStore('state').all('alerts'), [])
                    self.assertIn('首次运行、缓存丢失或条件改变', Path('artifacts/report.md').read_text(encoding='utf-8'))
            finally:
                os.chdir(previous)

    def test_baseline_quiet_repeat_change_and_acknowledgement(self):
        title = ['2026年模拟单位拟录用公示']
        class FakeFetcher:
            def __init__(self, source, cancel): self.session = Mock()
            def get(self, url):
                return f'''<script>m_nRecordCount=1;m_nPageSize=10;m_nCurrPage=0;</script>
                <li><a href="./202609/t20260901_123.html">{title[0]}</a><span>2026-09-01</span></li>'''
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as root:
            try:
                os.chdir(root)
                Path('watch.json').write_text(json.dumps(dict(month_from='2026-01',month_to='2026-12',notice_scope='public')),encoding='utf-8')
                def engine(store, directory): return NoticeEngine(store, directory, FakeFetcher)
                with patch.object(cloud_watch,'NoticeEngine',side_effect=engine), patch('wuzhong.notices.SOURCES', SOURCES[:1]), patch.dict(os.environ,{'GITHUB_OUTPUT':str(Path(root)/'output.txt'),'GITHUB_STEP_SUMMARY':str(Path(root)/'summary.md')}):
                    cloud_watch.run('state','watch.json')
                    self.assertTrue(Path('output.txt').read_text().endswith('notify=true\n'))
                    self.assertEqual(json.loads(Path('artifacts/alerts.json').read_text()),[])
                    self.assertFalse(Path('state/baseline.json').exists())
                    cloud_watch.acknowledge('state')
                    cloud_watch.run('state','watch.json')
                    self.assertTrue(Path('output.txt').read_text().endswith('notify=false\n'))
                    title[0] += '（更正）'
                    cloud_watch.run('state','watch.json')
                    self.assertTrue(Path('output.txt').read_text().endswith('notify=true\n'))
                    self.assertEqual(len(json.loads(Path('artifacts/alerts.json').read_text(encoding='utf-8'))),1)
                    cloud_watch.acknowledge('state')
                    self.assertTrue(all(a['read'] for a in NoticeStore('state').all('alerts')))
            finally:
                os.chdir(previous)


if __name__ == '__main__': unittest.main()
