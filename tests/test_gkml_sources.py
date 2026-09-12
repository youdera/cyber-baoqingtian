import copy
import json
import unittest
from datetime import datetime, timezone

from wuzhong.gkml_sources import GKML_SOURCES, parse_gkml


SOURCE = GKML_SOURCES[0]


def entry(number=1):
    return dict(id=number, title='2025年模拟事业单位招聘拟聘用公示',
                type='normal', classify_main=SOURCE['gkml_column'],
                url=f'https://www.zhaoqing.gov.cn/zqrsj/gkmlpt/content/0/0/post_{number}.html',
                create_time=int(datetime(2026, 1, 31, 16, 0, tzinfo=timezone.utc).timestamp()),
                date=1, created_at='2030-09-10 12:34:00',
                attachment=[dict(url='https://example.com/private-list.xlsx')],
                abstract='虚构人员信息，禁止落库', description='虚构正文，禁止落库')


def response(page=1, total=201, overrides=None):
    offset = (page - 1) * 100
    result = dict(classify=dict(id=SOURCE['gkml_column'], name=SOURCE['gkml_column_name'],
                                post_count=726, jump_url=''), offset=offset, total=total,
                  articles=[entry(i+1) for i in range(offset, min(offset+100, total))])
    result.update(overrides or {})
    return result


def parse(payload, page=1, source=SOURCE):
    return parse_gkml(json.dumps(payload), source,
                      source['listing_url'].replace('page=1&', f'page={page}&'))


class GkmlSourceTests(unittest.TestCase):
    def test_metadata_only_and_independent_publication_exam_year(self):
        rows, nxt = parse(response())
        self.assertEqual(len(rows), 100)
        self.assertEqual(rows[0]['published'], '2026-02-01')
        self.assertEqual(rows[0]['exam_year'], 2025)
        self.assertEqual(rows[0]['stage'], '录聘公示')
        self.assertEqual(set(rows[0]), {'id','source_id','source','owner','title','url',
                                        'published','exam_year','kind','region','stage'})
        self.assertNotIn('虚构人员', json.dumps(rows, ensure_ascii=False))
        self.assertNotIn('attachment', str(rows))
        self.assertEqual(nxt, SOURCE['listing_url'].replace('page=1&', 'page=2&'))
        self.assertEqual(parse(response(page=2), page=2)[1],
                         SOURCE['listing_url'].replace('page=1&', 'page=3&'))
        self.assertIsNone(parse(response(page=3), page=3)[1])

    def test_publication_date_does_not_fall_back_to_document_or_ingestion_date(self):
        for value in (None, '', '1770000000', 0, True, -10, 10**100):
            with self.subTest(value=value):
                data = response(total=1)
                data['articles'][0]['create_time'] = value
                self.assertIsNone(parse(data)[0][0]['published'])

    def test_empty_directory_requires_explicit_consistent_zero(self):
        self.assertEqual(parse(response(total=0)), ([], None))
        for changes in ({'articles': []}, {'offset': 100}, {'total': '100'},
                        {'total': True}, {'total': -1}, {'articles': {}}, {'classify': {}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                parse(response(overrides=changes))
        for bad in ('<html>captcha</html>', 'null', '[]', '{}'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_gkml(bad, SOURCE, SOURCE['listing_url'])

    def test_repeated_page_wrong_column_and_short_page_fail(self):
        with self.assertRaisesRegex(ValueError, '页码'):
            parse(response(), page=2)
        for mutation in ('id', 'name', 'jump_url'):
            data = response(total=1)
            data['classify'][mutation] = 'changed'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): parse(data)
        data = response(); data['articles'].pop()
        with self.assertRaisesRegex(ValueError, '条目数'): parse(data)
        data = response(total=2); data['articles'][1] = copy.deepcopy(data['articles'][0])
        with self.assertRaisesRegex(ValueError, '重复'): parse(data)

    def test_fixed_listing_request_cannot_switch_site_column_or_add_query(self):
        for bad in (SOURCE['listing_url'].replace('https:', 'http:'),
                    SOURCE['listing_url'].replace('page=1', 'page=0'),
                    SOURCE['listing_url'].replace('sid=758017', 'sid=2'),
                    SOURCE['listing_url'].replace('/21206?', '/1?'),
                    SOURCE['listing_url'] + '&page=2', SOURCE['listing_url'] + '&target=x',
                    SOURCE['listing_url'] + '#fragment'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_gkml(json.dumps(response()), SOURCE, bad)

    def test_article_links_cannot_be_attachments_or_external_pages(self):
        data = response(total=1)
        data['articles'][0]['url'] = data['articles'][0]['url'].replace('https:', 'http:')
        self.assertTrue(parse(data)[0][0]['url'].startswith('https:'))
        for raw in ('https://example.com/post_1.html', 'javascript:alert(1)',
                    'https://user:pass@www.zhaoqing.gov.cn/zqrsj/gkmlpt/content/0/0/post_1.html',
                    'https://www.zhaoqing.gov.cn:8443/zqrsj/gkmlpt/content/0/0/post_1.html',
                    'https://www.zhaoqing.gov.cn/zqrsj/gkmlpt/content/0/0/list.xlsx',
                    'https://www.zhaoqing.gov.cn/zqrsj/gkmlpt/content/0/0/post_2.html',
                    'https://www.zhaoqing.gov.cn/other/gkmlpt/content/0/0/post_1.html',
                    'https://www.zhaoqing.gov.cn/zqrsj/gkmlpt/content/0/0/post_1.html?jump=true'):
            data['articles'][0]['url'] = raw
            with self.subTest(raw=raw), self.assertRaises(ValueError): parse(data)

    def test_malformed_or_relocated_articles_are_not_silently_dropped(self):
        for key, value in (('id', True), ('title', ''), ('classify_main', 1), ('type', 'attachment'),
                           ('url', None), ('title', 123)):
            data = response(total=1); data['articles'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): parse(data)
        data = response(total=1); data['articles'][0] = None
        with self.assertRaises(ValueError): parse(data)

    def test_external_references_are_excluded_without_changing_pagination(self):
        data = response(total=101)
        for item in data['articles']:
            item.update(type='url', url='https://other.example/notice.html')
        rows, nxt = parse(data)
        self.assertEqual(rows, [])
        self.assertEqual(nxt, SOURCE['listing_url'].replace('page=1&', 'page=2&'))
        last = response(page=2, total=101)
        last['articles'][0].update(type='url', url='https://other.example/notice.html')
        self.assertEqual(parse(last, page=2), ([], None))

    def test_fixed_sources_keep_current_window_explicit(self):
        for source in GKML_SOURCES:
            self.assertFalse(source['history'])
            self.assertIn('接口可列出总数少于栏目计数', source['history_note'])
            self.assertEqual(source['region'], '广东')
            self.assertEqual(source['area_scope'], 'province')
            self.assertTrue(source['listing_url'].startswith('https:'))
            self.assertIn('#', source['url'])


if __name__ == '__main__': unittest.main()
