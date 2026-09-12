import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import cloud_watch
from wuzhong.notices import NoticeEngine, NoticeStore, SOURCES, Stopped, relevance


class CloudWatchTests(unittest.TestCase):
    def test_source_rotation_uses_only_matching_acknowledged_checkpoint(self):
        selected = [dict(id=value) for value in ('first', 'middle', 'last')]
        marker = dict(next_source='middle')
        self.assertEqual([source['id'] for source in cloud_watch.rotated_sources(selected, marker, False)],
                         ['middle', 'last', 'first'])
        self.assertEqual(cloud_watch.rotated_sources(selected, marker, True), selected)
        self.assertEqual(cloud_watch.rotated_sources(selected, dict(next_source='removed'), False), selected)
        self.assertEqual(cloud_watch.rotated_sources([], marker, False), [])

    def test_timeout_waits_for_worker_then_reports_partial_and_rotates_after_ack(self):
        started, engines, closed = [], [], []
        slow = {'enabled': True}
        class FakeFetcher:
            def __init__(self, source, cancel):
                self.source, self.cancel = source, cancel
                self.calls = 0
                self.session = Mock()
                self.session.close.side_effect = lambda: closed.append(source['id'])
                started.append(source['id'])
            def get(self, url):
                self.calls += 1
                if self.source['id'] == 'stats' and self.calls > 1 and slow['enabled']:
                    if not self.cancel.wait(3):
                        raise AssertionError('The cloud deadline did not cancel the simulated slow page')
                    raise Stopped()
                count = 11 if self.source['id'] == 'stats' else 1
                current = self.calls - 1
                return f'''<script>m_nRecordCount={count};m_nPageSize=10;m_nCurrPage={current};</script>
                <li><a href="./202609/t20260901_{123+current}.html">2026年模拟单位拟录用公示</a><span>2026-09-01</span></li>'''
        def engine(store, directory):
            instance = NoticeEngine(store, directory, FakeFetcher)
            engines.append(instance)
            return instance
        original_write = Path.write_text
        artifact_writes = []
        def write_after_exit(path, *args, **kwargs):
            if path.parent.name == 'artifacts':
                self.assertFalse(engines[-1].lock.locked())
                self.assertFalse(engines[-1].state['running'])
                self.assertEqual(started, closed)
                artifact_writes.append(path.name)
            return original_write(path, *args, **kwargs)
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as root:
            try:
                os.chdir(root)
                Path('watch.json').write_text(json.dumps(dict(year_from=2026)), encoding='utf-8')
                with patch.object(cloud_watch, 'NoticeEngine', side_effect=engine), \
                     patch.object(cloud_watch, 'SCAN_TIMEOUT_SECONDS', 0.2), \
                     patch.object(cloud_watch, 'CANCEL_GRACE_SECONDS', 1), \
                     patch('wuzhong.notices.SOURCES', SOURCES[:2]), \
                     patch.object(Path, 'write_text', write_after_exit), \
                     patch.dict(os.environ, {'GITHUB_OUTPUT': '', 'GITHUB_STEP_SUMMARY': ''}):
                    cloud_watch.run('state', 'watch.json')
                    self.assertEqual(started, ['stats'])
                    self.assertEqual(set(artifact_writes), {'pending.json', 'report.md', 'alerts.json'})
                    report = NoticeStore('state').all('runs')[0]
                    self.assertEqual(report['status'], 'partial')
                    self.assertTrue(report['budget_exhausted'])
                    self.assertEqual([(source['id'], source['status'], source['pages']) for source in report['sources']],
                                     [('stats', 'partial', 1), ('fujian', 'not_checked', 0)])
                    pending = json.loads(Path('artifacts/pending.json').read_text())
                    self.assertEqual(pending['baseline']['next_source'], 'fujian')
                    self.assertTrue(report['sources'][0]['incomplete_scan'])
                    self.assertEqual(pending['baseline']['sources'], [])
                    self.assertFalse(Path('state/baseline.json').exists())
                    self.assertIn('不是从中断页续采', Path('artifacts/report.md').read_text(encoding='utf-8'))
                    cloud_watch.acknowledge('state')
                    self.assertEqual(json.loads(Path('state/baseline.json').read_text())['next_source'], 'fujian')
                    cloud_watch.run('state', 'watch.json')
                    self.assertEqual(started, ['stats', 'fujian', 'stats'])
                    pending = json.loads(Path('artifacts/pending.json').read_text())
                    self.assertEqual(pending['baseline']['sources'], ['fujian'])
                    self.assertEqual(pending['baseline']['next_source'], 'stats')
                    self.assertEqual(json.loads(Path('state/baseline.json').read_text())['next_source'], 'fujian')
                    cloud_watch.acknowledge('state')
                    self.assertEqual(json.loads(Path('state/baseline.json').read_text())['next_source'], 'stats')
                    slow['enabled'] = False
                    cloud_watch.run('state', 'watch.json')
                    self.assertEqual(started, ['stats', 'fujian', 'stats', 'stats', 'fujian'])
                    self.assertEqual(json.loads(Path('artifacts/pending.json').read_text())['baseline']['sources'], ['fujian', 'stats'])
                    self.assertEqual(NoticeStore('state').all('alerts'), [])
            finally:
                os.chdir(previous)

    def test_cancel_grace_failure_does_not_export_or_advance_old_baseline(self):
        engine = Mock()
        engine.lock.acquire.return_value = False
        engine.cancel = threading.Event()
        engine.state = {'message': '模拟无法结束的请求'}
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as root:
            try:
                os.chdir(root)
                Path('watch.json').write_text(json.dumps(dict(year_from=2026)), encoding='utf-8')
                Path('state').mkdir()
                Path('state/baseline.json').write_text('{"filters":"older","next_source":"stats"}')
                Path('artifacts').mkdir()
                for name in ('pending.json', 'report.md', 'alerts.json'):
                    (Path('artifacts')/name).write_text('stale previous run')
                with patch.object(cloud_watch, 'NoticeEngine', return_value=engine), \
                     patch.object(cloud_watch, 'SCAN_TIMEOUT_SECONDS', 1), \
                     patch.object(cloud_watch, 'CANCEL_GRACE_SECONDS', 1), \
                     patch.object(cloud_watch.time, 'monotonic', side_effect=range(20)), \
                     patch('wuzhong.notices.SOURCES', SOURCES[:1]):
                    with self.assertRaisesRegex(RuntimeError, '采集线程未及时退出'):
                        cloud_watch.run('state', 'watch.json')
                self.assertTrue(engine.cancel.is_set())
                engine.lock.release.assert_not_called()
                self.assertEqual(Path('state/baseline.json').read_text(), '{"filters":"older","next_source":"stats"}')
                self.assertEqual(list(Path('artifacts').iterdir()), [])
            finally:
                os.chdir(previous)

    def test_last_interrupted_source_is_resumed_when_no_sources_are_unvisited(self):
        selected = [dict(id=value, name=value) for value in ('a', 'b')]
        report = dict(status='cancelled', sources=[
            dict(id='a', status='completed', pages=1, warnings=[]),
            dict(id='b', status='cancelled', pages=0, warnings=[])])
        self.assertEqual(cloud_watch.finish_report(report, selected, True), 'b')
        self.assertEqual(report['sources'][1]['status'], 'not_checked')
        self.assertEqual(report['status'], 'partial')

    def test_network_error_after_budget_cancel_keeps_last_partial_source_uninitialized(self):
        selected = [dict(id=value, name=value) for value in ('a', 'b')]
        report = dict(status='cancelled', sources=[
            dict(id='a', status='partial', pages=1, warnings=['模拟请求读取超时'])])
        self.assertEqual(cloud_watch.finish_report(report, selected, True), 'b')
        self.assertTrue(report['sources'][0]['incomplete_scan'])
        self.assertTrue(report['sources'][0]['budget_exhausted'])
        self.assertIn('模拟请求读取超时', report['sources'][0]['warnings'])

    def test_full_scan_rotation_does_not_create_health_change_notification(self):
        started = []
        class FakeFetcher:
            def __init__(self, source, cancel):
                self.session = Mock()
                started.append(source['id'])
            def get(self, url):
                return '''<script>m_nRecordCount=1;m_nPageSize=10;m_nCurrPage=0;</script>
                <li><a href="./202609/t20260901_123.html">2026年模拟单位拟录用公示</a><span>2026-09-01</span></li>'''
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as root:
            try:
                os.chdir(root)
                Path('watch.json').write_text(json.dumps(dict(year_from=2026)), encoding='utf-8')
                def engine(store, directory): return NoticeEngine(store, directory, FakeFetcher)
                with patch.object(cloud_watch, 'NoticeEngine', side_effect=engine), \
                     patch('wuzhong.notices.SOURCES', SOURCES[:2]), \
                     patch.dict(os.environ, {'GITHUB_OUTPUT': str(Path(root)/'output.txt'), 'GITHUB_STEP_SUMMARY': ''}):
                    cloud_watch.run('state', 'watch.json')
                    cloud_watch.acknowledge('state')
                    marker = json.loads(Path('state/baseline.json').read_text())
                    marker['next_source'] = 'fujian'
                    marker['health'] = json.dumps(list(reversed(json.loads(marker['health']))))
                    Path('state/baseline.json').write_text(json.dumps(marker))
                    cloud_watch.run('state', 'watch.json')
                    self.assertEqual(started, ['stats', 'fujian', 'fujian', 'stats'])
                    self.assertTrue(Path('output.txt').read_text().endswith('notify=false\n'))
            finally:
                os.chdir(previous)

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
                    self.assertIn('本轮未读到目录或检查提前中断，尚未建立基线', Path('artifacts/report.md').read_text(encoding='utf-8'))
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
