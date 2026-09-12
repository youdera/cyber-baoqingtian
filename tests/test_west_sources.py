import unittest
from urllib.parse import parse_qs, quote, urlparse

from wuzhong.west_sources import SOURCE_AREAS, WEST_SOURCES, parse_west


SC = WEST_SOURCES[0]


def directory(source=SC, current=1, count=3, size=1, title='2025年度模拟单位公务员拟录用公示',
              published='2026-09-01', href=None):
    path = urlparse(source['url']).path
    category = path.rsplit('/', 1)[1]
    topic = parse_qs(urlparse(source['url']).query)['t'][0]
    prefix = source['url'].split('www.scpta.com.cn', 1)[1] + '&i='
    target = href or f'/front/News/info/{current:032x}?t={category}'
    return f'''<script>var listCount = '{count}'; var pageIndex = '{current}';
    var pageSize = '{size}'; var pageUrl = '{quote(prefix, safe="")}'; var selId = parseInt('{topic}');</script>
    <div class="item active" id="left_item_{topic}"></div>
    <div class="wrap-content"><li><a href="{target}" title="{title}">模拟公告</a>
    <span>{published}</span></li></div><div id="pagination"></div>
    <a href="/名单.xlsx">人员名单附件</a><table><tr><td>名单正文不应被索引</td></tr></table>'''


class WestSourceTests(unittest.TestCase):
    def test_six_fixed_topics_and_honest_history(self):
        self.assertEqual(len(WEST_SOURCES), 6)
        self.assertEqual(len(SOURCE_AREAS), 6)
        self.assertEqual({parse_qs(urlparse(s['url']).query)['t'][0] for s in WEST_SOURCES},
                         {'117', '88', '98', '68', '69', '70'})
        for source in WEST_SOURCES:
            self.assertEqual(source['area_scope'], 'province')
            self.assertEqual(source['region'], '四川')
            self.assertEqual(source['max_pages'], 100)
            self.assertEqual(source['history'], source['id'] != 'scpta_selected')
        self.assertIn('记录总数不一致', WEST_SOURCES[1]['history_note'])

    def test_first_second_last_page_and_independent_dates(self):
        rows, next_url = parse_west(directory(), SC, SC['url'])
        self.assertEqual(next_url, SC['url'] + '&i=2')
        self.assertEqual(rows[0]['published'], '2026-09-01')
        self.assertEqual(rows[0]['exam_year'], 2025)
        self.assertEqual(rows[0]['source_id'], SC['id'])
        self.assertNotIn('名单正文', str(rows))
        self.assertNotIn('xlsx', str(rows))
        _, next_url = parse_west(directory(current=2), SC, next_url)
        self.assertEqual(next_url, SC['url'] + '&i=3')
        self.assertIsNone(parse_west(directory(current=3), SC, next_url)[1])

    def test_application_cap_preserves_next_url(self):
        _, next_url = parse_west(directory(current=100, count=101), SC, SC['url'] + '&i=100')
        self.assertEqual(next_url, SC['url'] + '&i=101')

    def test_every_topic_parses_own_canonical_links(self):
        for source in WEST_SOURCES:
            with self.subTest(source=source['id']):
                rows, _ = parse_west(directory(source), source, source['url'])
                self.assertEqual(rows[0]['kind'], source['kind'])
                self.assertEqual(rows[0]['source_id'], source['id'])
                self.assertEqual(rows[0]['url'].split('?')[1],
                                 't=' + urlparse(source['url']).path.rsplit('/', 1)[1])

    def test_missing_or_invalid_publication_date_remains_unknown(self):
        for published in ['', '2026-02-30', '时间未知']:
            rows, _ = parse_west(directory(published=published), SC, SC['url'])
            self.assertIsNone(rows[0]['published'])
            self.assertEqual(rows[0]['exam_year'], 2025)
        rows, _ = parse_west(directory(title='模拟单位公务员拟录用公示'), SC, SC['url'])
        self.assertIsNone(rows[0]['exam_year'])
        rows, _ = parse_west(directory(title='特别提醒'), SC, SC['url'])
        self.assertEqual(rows[0]['title'], '特别提醒')

    def test_repeated_homepage_or_changed_template_fails(self):
        bad_cases = [
            (directory(), SC['url'] + '&i=2'),
            (directory().replace('pageIndex', 'differentIndex'), SC['url']),
            (directory().replace('wrap-content', 'different-content'), SC['url']),
            (directory().replace('pagination', 'different-pagination'), SC['url']),
            (directory().replace("parseInt('117')", "parseInt('88')"), SC['url']),
            (directory().replace('item active', 'item'), SC['url']),
            (directory(count=0), SC['url']),
            (directory(size=2), SC['url']),
            (directory(count=1, current=2), SC['url'] + '&i=2'),
            (directory().replace("var pageSize = '1';", "var pageSize = '1'; var pageSize = '1';"), SC['url']),
        ]
        for html, url in bad_cases:
            with self.subTest(url=url, html=html[:80]), self.assertRaises(ValueError):
                parse_west(html, SC, url)

    def test_wrong_source_request_or_pagination_target_fails(self):
        for url in [SC['url'].replace('https:', 'http:'), SC['url'] + '&extra=1',
                    SC['url'] + '&i=2&i=3', SC['url'] + '&i=0',
                    SC['url'].replace('t=117', 't=88'), SC['url'] + '#fragment',
                    SC['url'].replace('www.scpta.com.cn', 'www.scpta.com.cn.evil.test')]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                parse_west(directory(), SC, url)
        good_prefix = quote('/front/News/List/56?t=117&a=0&i=', safe='')
        for prefix in ['https://example.test/front/News/List/56?t=117&a=0&i=',
                       '/front/News/List/67?t=117&a=0&i=',
                       '/front/News/List/56?t=117&a=2&i=',
                       '/front/News/List/56?t=117&a=0&i=2']:
            html = directory().replace(good_prefix, quote(prefix, safe=''))
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                parse_west(html, SC, SC['url'])

    def test_unverified_article_urls_never_silently_complete(self):
        path = '/front/News/info/' + 'a' * 32 + '?t=56'
        for href in ['https://example.test' + path, 'http://www.scpta.com.cn' + path,
                     path + '&download=1', path.replace('?t=56', '.pdf'),
                     path.replace('?t=56', '?t=67'), path + '#body',
                     '/front/News/info/not-an-id?t=56']:
            with self.subTest(href=href), self.assertRaises(ValueError):
                parse_west(directory(href=href), SC, SC['url'])

    def test_duplicate_same_page_or_missing_title_fails(self):
        html = directory(size=2).replace('</li>', '</li>' + directory().split('<div class="wrap-content">')[1].split('</div>')[0], 1)
        with self.assertRaises(ValueError):
            parse_west(html, SC, SC['url'])
        with self.assertRaises(ValueError):
            parse_west(directory(title='超' * 501), SC, SC['url'])

    def test_unknown_adapter_is_not_enabled(self):
        with self.assertRaises(ValueError):
            parse_west(directory(), dict(SC, id='chongqing'), SC['url'])


if __name__ == '__main__':
    unittest.main()
