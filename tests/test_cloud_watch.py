import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import cloud_watch
from wuzhong.notices import NoticeEngine, NoticeStore, SOURCES


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
                    self.assertEqual(len(store.all('alerts')), int(matches))
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
