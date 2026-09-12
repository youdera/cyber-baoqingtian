import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import cloud_watch
from wuzhong.notices import NoticeEngine, NoticeStore, SOURCES


class CloudWatchTests(unittest.TestCase):
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
