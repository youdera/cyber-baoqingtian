"""Directory API routing, pagination failures and coverage reporting."""
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from wuzhong.notices import SOURCES, NoticeEngine, NoticeStore, validate_filters
from wuzhong.source_audit import probe


BASE = next(s for s in SOURCES if s['id'] == 'guangdong')


def entry(number):
    return dict(id=str(number), source_id=BASE['id'], source=BASE['name'], owner=BASE['owner'],
                title=f'2026年模拟单位招聘公示第{number}期',
                url=f"{BASE['url']}rygs/content/post_{number}.html", published='2026-09-01',
                exam_year=2026, kind='事业单位', region='广东', stage='录聘公示')


class ListingApiTests(unittest.TestCase):
    def run_engine(self, source, responses):
        requested = []
        class Reader:
            def __init__(self, source, cancel): self.session = Mock()
            def get(self, url): requested.append(url); return 'synthetic directory'
        with tempfile.TemporaryDirectory() as folder:
            engine = NoticeEngine(NoticeStore(folder), folder, Reader)
            with patch('wuzhong.notices.SOURCES', [source]), patch('wuzhong.notices.listing', side_effect=responses):
                engine.start(validate_filters({'year_from': 2026}))
                self.assertTrue(engine.lock.acquire(timeout=10)); engine.lock.release()
            return engine.store.all('runs')[0], requested

    def test_api_start_preserves_public_directory_and_specific_history_reason(self):
        api = 'https://hrss.gd.gov.cn/directory-api?page=1'
        second = 'https://hrss.gd.gov.cn/directory-api?page=2'
        source = dict(BASE, listing_url=api, history=False, history_note='目录接口总数少于栏目声明数，历史范围不完整')
        run, requested = self.run_engine(source, [([entry(1)], second), ([entry(2)], None)])
        self.assertEqual(requested, [api, second])
        self.assertEqual(run['sources'][0]['pages'], 2)
        self.assertEqual(run['status'], 'partial')
        self.assertEqual(run['sources'][0]['warnings'], [source['history_note']])
        with patch('wuzhong.source_audit.listing', return_value=([entry(1)], second)) as parser:
            class Reader:
                def __init__(self, source, cancel): self.session = Mock()
                def get(self, url): self_url.append(url); return 'synthetic directory'
            self_url = []
            result = probe(dict(source, enabled=True), threading.Event(), Reader)
            self.assertEqual(self_url, [api])
            self.assertEqual(result['url'], BASE['url'])
            self.assertEqual(result['status'], 'sample_ok')
            self.assertEqual(parser.call_args.args[2], api)

    def test_different_urls_returning_same_page_remain_partial(self):
        run, _ = self.run_engine(BASE, [([entry(1)], BASE['url']+'index_2.html'), ([entry(1)], None)])
        self.assertEqual(run['status'], 'partial')
        self.assertIn('重复目录页', run['sources'][0]['warnings'][0])
        self.assertEqual(run['sources'][0]['found'], 1)

    def test_overlapping_pinned_items_count_once_without_stopping(self):
        run, _ = self.run_engine(BASE, [([entry(1), entry(2)], BASE['url']+'index_2.html'), ([entry(1), entry(3)], None)])
        self.assertEqual(run['status'], 'completed')
        self.assertEqual(run['sources'][0]['found'], 3)
        self.assertEqual(run['sources'][0]['pages'], 2)


if __name__ == '__main__': unittest.main()
