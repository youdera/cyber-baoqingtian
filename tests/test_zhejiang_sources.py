import copy
import html
import json
import unittest
from urllib.parse import parse_qsl, urlencode, urlparse

from wuzhong.zhejiang_sources import ZHEJIANG_SOURCES, directory_url, parse_zhejiang


SOURCE = ZHEJIANG_SOURCES[0]
PARAMS = dict(webId='2758', pageId='1229743684', parseType='bulidstatic', pageType='column',
              tagId='当前栏目列表', tplSetId='kUBgoFENJiaYxr31jYEph')


def row(index, title='2025年模拟事业单位拟聘公示', stamp='2026-01-02', href=None):
    href = href or f'/col/col1229743684/art/2026/art_{index:032x}.html'
    return (f'<li><span></span><a class="bt_link" href="{html.escape(href)}" '
            f'title="{html.escape(title)}">{html.escape(title)}</a>'
            f'<span class="bt_time">{html.escape(stamp)}</span><br></li>')


def response(page=1, count=21, rows=None, params=None):
    actual = max(0, min(10, count - (page - 1) * 10))
    rows = rows if rows is not None else ''.join(row((page - 1) * 10 + n + 1) for n in range(actual))
    attrs = html.escape(json.dumps(params or PARAMS, ensure_ascii=False), quote=True)
    fragment = (f'<div id="当前栏目列表"><div class="page-content">{rows}</div></div>'
                f'<table class="pagination" querydata="{attrs}" uniturl="{urlparse(directory_url()).path}" '
                f'count="{count}" rows="10" pageno="{page}"></table>')
    return json.dumps(dict(code='200', success=True, data=dict(html=fragment)), ensure_ascii=False)


def parse(raw, page=1, source=SOURCE):
    return parse_zhejiang(raw, source, directory_url(page))


class ZhejiangSourcesTests(unittest.TestCase):
    def test_current_next_last_pages_and_independent_years(self):
        entries, nxt = parse(response())
        self.assertEqual(len(entries), 10)
        self.assertEqual(nxt, directory_url(2))
        self.assertEqual(entries[0]['published'], '2026-01-02')
        self.assertEqual(entries[0]['exam_year'], 2025)
        self.assertEqual(parse(response(2), 2)[1], directory_url(3))
        last, nxt = parse(response(3), 3)
        self.assertEqual(len(last), 1)
        self.assertIsNone(nxt)

    def test_unknown_date_never_comes_from_title_or_url(self):
        for stamp in ('', '2026-02-30', '2026-1-2', '2026-01-02 2026-01-03'):
            with self.subTest(stamp=stamp):
                items, _ = parse(response(count=1, rows=row(1, '2025年模拟事业单位2026-01-01拟聘公示', stamp)))
                self.assertIsNone(items[0]['published'])

    def test_title_fallback_short_title_and_unknown_exam_year(self):
        raw = response(count=1, rows=row(1, '公示')).replace('title=\\"公示\\"', 'title=\\" \\"')
        items, _ = parse(raw)
        self.assertEqual(items[0]['title'], '公示')
        self.assertIsNone(items[0]['exam_year'])

    def test_non_establishment_is_not_confirmed_by_directory(self):
        items, _ = parse(response(count=1, rows=row(1, '2026年事业单位编外招聘公示')))
        self.assertEqual(items[0]['kind'], '')

    def test_only_directory_metadata_is_returned(self):
        data = json.loads(response(count=1))
        data['data']['content'] = '虚构正文不得保存'
        data['data']['html'] += '<div class="article-body">虚构名单内容不得保存</div>'
        entries, _ = parse(json.dumps(data))
        self.assertNotIn('虚构', json.dumps(entries, ensure_ascii=False))
        self.assertEqual(set(entries[0]), {'id', 'source_id', 'source', 'owner', 'title', 'url',
                                         'published', 'exam_year', 'kind', 'region', 'stage'})

    def test_external_links_actions_and_attachments_excluded(self):
        for target in ('https://example.com/notice.html', 'javascript:alert(1)',
                       '/col/col1229743684/list.xlsx'):
            with self.subTest(target=target):
                self.assertEqual(parse(response(count=1, rows=row(1, href=target))), ([], None))

    def test_unexpected_same_site_path_does_not_silently_disappear(self):
        for target in ('/other/notice.html', '/col/col1229743684/art/2026/art_1.html?redirect=x',
                       'https://user:pass@rlsbt.zj.gov.cn/col/col1229743684/art/2026/art_1.html',
                       'https://rlsbt.zj.gov.cn:8443/col/col1229743684/art/2026/art_1.html',
                       'http://rlsbt.zj.gov.cn/col/col1229743684/art/2026/art_1.html',
                       '/col/col1229743684/art/2026/art_1.html#fragment',
                       '/col/col1229743684/art/2026/art_1.html;params'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                parse(response(count=1, rows=row(1, href=target)))

    def test_api_cannot_switch_host_path_parameters_or_duplicate_parameters(self):
        base = directory_url()
        for url in (base.replace('https:', 'http:'), base.replace('rlsbt.zj.gov.cn', 'example.com'),
                    base.replace('rlsbt.zj.gov.cn', 'user:pass@rlsbt.zj.gov.cn'),
                    base.replace('rlsbt.zj.gov.cn', 'rlsbt.zj.gov.cn:8443'),
                    base.replace('/build/unit?', '/build/other?'), base.replace('webId=2758', 'webId=1'),
                    base + '&target=x', base + '&webId=2758', base + '#fragment',
                    base.replace('/build/unit?', '/build/unit;params?')):
            with self.subTest(url=url), self.assertRaises(ValueError):
                parse_zhejiang(response(), SOURCE, url)

    def test_page_params_are_bounded_and_have_fixed_size(self):
        for value in (dict(pageNo=True, pageSize=10), dict(pageNo=2, pageSize=100),
                      dict(pageNo=0, pageSize=10), dict(pageNo=2, pageSize=10, target='x'), None):
            params = dict(parse_qsl(urlparse(directory_url(2)).query))
            params['paramJson'] = json.dumps(value)
            url = directory_url(2).split('?')[0] + '?' + urlencode(params)
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_zhejiang(response(2), SOURCE, url)

    def test_source_configuration_is_fixed(self):
        for key in ('id', 'url', 'listing_url'):
            source = copy.deepcopy(SOURCE)
            source[key] = 'unreviewed'
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse(response(), source=source)

    def test_response_page_mismatch_count_drift_and_structure_fail(self):
        for raw in (response(2), response(count=11, rows=row(1)),
                    response(params={**PARAMS, 'pageId': '123'}),
                    response().replace('page-content', 'moved-content'),
                    response().replace('bt_link', 'moved-link'),
                    response().replace('pageno=\\"1\\"', 'pageno=\\"0\\"')):
            with self.subTest(raw=raw[:60]), self.assertRaises(ValueError):
                parse(raw)

    def test_error_response_is_not_empty_success(self):
        for raw in ('<html>challenge</html>', '{}', '[]',
                    json.dumps(dict(code='200', success=False, data=dict(html=''))),
                    json.dumps(dict(code='500', success=True, data=dict(html='')))):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse(raw)

    def test_zero_directory_requires_consistent_count_and_container(self):
        self.assertEqual(parse(response(count=0)), ([], None))
        with self.assertRaises(ValueError):
            parse(response(count=1, rows=''))

    def test_duplicate_link_is_deduplicated(self):
        items, _ = parse(response(count=2, rows=row(1) + row(1)))
        self.assertEqual(len(items), 1)

    def test_partial_history_and_scope_remain_explicit(self):
        self.assertFalse(SOURCE['history'])
        self.assertIn('未证明全部历史完整', SOURCE['history_note'])
        self.assertIn('不代表全省', SOURCE['note'])

    def test_update_window_keeps_next_page_for_engine_partial_status(self):
        entries, nxt = parse(response(page=20, count=2637), page=20)
        self.assertEqual(len(entries), 10)
        self.assertEqual(SOURCE['max_pages'], 20)
        self.assertEqual(nxt, directory_url(21))


if __name__ == '__main__':
    unittest.main()
