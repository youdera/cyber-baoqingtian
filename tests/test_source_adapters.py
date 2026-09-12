import tempfile
import unittest
from unittest.mock import Mock, patch

from wuzhong.notices import SOURCES, NoticeEngine, NoticeStore, listing, validate_filters


GD = next(s for s in SOURCES if s['id'] == 'guangdong')


def directory(count=2008):
    return f'''<script>var numbers='{count}';var page_t1 = Math.ceil(numbers / 9 );var page_t2 = "200";</script>
    <ul><li><a title="2026年模拟单位拟聘用公示" href="{GD['url']}rygs/content/post_123.html">公告</a><span>2026-09-01</span></li></ul>
    <a href="{GD['url']}rygs/content/名单.xlsx">名单附件</a>
    <a href="https://example.com/rygs/content/post_123.html">外部链接不得采集</a>
    <table><tr><td>虚构个人记录不得索引</td></tr></table>'''


class SourceAdapterTests(unittest.TestCase):
    def test_guangdong_metadata_and_one_based_pagination(self):
        entries, nxt = listing(directory(), GD, GD['url'])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['published'], '2026-09-01')
        self.assertEqual(entries[0]['kind'], '事业单位')
        self.assertEqual(nxt, GD['url'] + 'index_2.html')
        self.assertEqual(listing(directory(), GD, nxt)[1], GD['url'] + 'index_3.html')
        self.assertIsNone(listing(directory(18), GD, nxt)[1])
        self.assertNotIn('个人记录', str(entries))

    def test_structure_drift_fails_instead_of_claiming_empty(self):
        for html in [directory().replace('page_t2', 'renamed'), directory().replace('post_123.html', 'file.xlsx')]:
            with self.assertRaises(ValueError): listing(html, GD, GD['url'])

    def test_official_archive_cap_reports_partial(self):
        requested = []
        class FakeFetcher:
            def __init__(self, source, cancel): self.session = Mock()
            def get(self, url):
                requested.append(url)
                return directory().replace('post_123.html', f'post_{1000+len(requested)}.html')
        with tempfile.TemporaryDirectory() as root:
            engine = NoticeEngine(NoticeStore(root), root, FakeFetcher)
            with patch('wuzhong.notices.SOURCES', [GD]):
                engine.start(validate_filters(dict(month_from='2026-01', month_to='2026-12')))
                self.assertTrue(engine.lock.acquire(timeout=20)); engine.lock.release()
            run = engine.store.all('runs')[0]
            self.assertEqual(run['status'], 'partial')
            self.assertEqual(run['sources'][0]['pages'], 200)
            self.assertIn('达到分页上限', run['sources'][0]['warnings'][0])
            self.assertEqual(requested[-1], GD['url'] + 'index_200.html')
            self.assertFalse(any('content/' in url for url in requested))


if __name__ == '__main__': unittest.main()
