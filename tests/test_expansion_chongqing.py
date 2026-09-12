import json
import unittest

from wuzhong.expansion_chongqing import EXPANSION_CHONGQING_SOURCES, parse_expansion_chongqing, chongqing_kind


SOURCE = EXPANSION_CHONGQING_SOURCES[0]


def html(page=1, pages=50, title='2025年度公务员拟录用公示', stamp='2026-09-11', href=None, extra=''):
    href = href or 'https://www.12371.gov.cn/web/article/1234/web/content_1234.html'
    links = ['javascript:void(0)' if n == page else f'https://www.12371.gov.cn/web/column/col5011019{("_"+str(n)) if n>1 else ""}.html' for n in range(1, pages + 1)]
    def page_url(n):
        return 'https://www.12371.gov.cn/web/column/col5011019' + (f'_{n}' if n > 1 else '') + '.html'
    links = ([page_url(page - 1)] if page > 1 else []) + links + ([page_url(page + 1)] if page < pages else [])
    data = json.dumps({'pages': pages, 'current': page, 'href': links})
    return f'''<div class="list-page__main-list"><a href="{href}" title="不得提取这个属性"><div class="content-view"><div class="title">{title}</div><div class="content">不得提取正文 SECRET_BODY</div><div class="date">日期：<span>{stamp}</span></div></div></a>{extra}</div><script>var data={data};</script>'''


def parse(markup, page=1):
    url = SOURCE['url'].replace('.html', f'_{page}.html') if page > 1 else SOURCE['url']
    return parse_expansion_chongqing(markup, SOURCE, url)


class ChongqingTests(unittest.TestCase):
    def test_metadata_only_and_independent_year(self):
        rows, nxt = parse(html())
        self.assertEqual(rows[0]['title'], '2025年度公务员拟录用公示')
        self.assertEqual(rows[0]['exam_year'], 2025)
        self.assertEqual(rows[0]['published'], '2026-09-11')
        self.assertNotIn('SECRET_BODY', json.dumps(rows))
        self.assertNotIn('不得提取这个属性', json.dumps(rows, ensure_ascii=False))
        self.assertTrue(nxt.endswith('col5011019_2.html'))

    def test_short_title_and_empty_title(self):
        self.assertEqual(parse(html(title='提醒'))[0][0]['title'], '提醒')
        with self.assertRaises(ValueError):
            parse(html(title=''))

    def test_end_page_and_wrong_page(self):
        self.assertIsNone(parse(html(page=50), 50)[1])
        with self.assertRaises(ValueError):
            parse(html(page=2))

    def test_external_only_page_is_deliberate_empty(self):
        rows, nxt = parse(html(href='https://district.example.gov.cn/notice.html'))
        self.assertEqual(rows, [])
        self.assertIsNotNone(nxt)

    def test_attachment_excluded_but_unknown_local_path_fails(self):
        self.assertEqual(parse(html(href='https://www.12371.gov.cn/files/list.xlsx'))[0], [])
        with self.assertRaises(ValueError):
            parse(html(href='https://www.12371.gov.cn/web/new-format/1234.html'))
        with self.assertRaises(ValueError):
            parse(html(href='https://www.12371.gov.cn/web/article/1/web/content_2.html'))

    def test_unknown_date_not_guessed(self):
        self.assertIsNone(parse(html(stamp='2026-02-30'))[0][0]['published'])
        self.assertIsNone(parse(html(stamp=''))[0][0]['published'])

    def test_national_reprint_keeps_publishing_region_and_national_kind(self):
        row = parse(html(title='中央机关及其直属机构2026年度考试录用公务员公告'))[0][0]
        self.assertEqual(row['kind'], '国考')
        self.assertEqual(row['region'], '重庆')

    def test_pager_external_redirect_and_container_drift_fail(self):
        with self.assertRaises(ValueError):
            parse(html().replace('https://www.12371.gov.cn/web/column/col5011019_2.html', 'https://evil.example/next'))
        with self.assertRaises(ValueError):
            parse(html().replace('list-page__main-list', 'changed-list'))
        with self.assertRaises(ValueError):
            parse('<html>maintenance</html>')

    def test_known_title_cannot_fall_back_to_body(self):
        with self.assertRaises(ValueError):
            parse(html().replace('class="title"', 'class="unrecognized"'))

    def test_nested_metadata_classes_in_body_cannot_replace_real_metadata(self):
        nested = '<div class="content-view"><div class="title">BODY_ONLY</div></div>'
        fixture = html().replace('<div class="title">', '<div class="changed-title">', 1)
        fixture = fixture.replace('不得提取正文 SECRET_BODY', nested)
        with self.assertRaises(ValueError):
            parse(fixture)

    def test_nested_body_metadata_ignored_when_real_metadata_present(self):
        nested = '<div class="content-view"><div class="title">BODY_ONLY</div><div class="date">日期：2001-01-01</div></div>'
        row = parse(html().replace('不得提取正文 SECRET_BODY', nested))[0][0]
        self.assertEqual(row['title'], '2025年度公务员拟录用公示')
        self.assertEqual(row['published'], '2026-09-11')

    def test_mixed_source_is_not_skipped_and_title_types_are_conservative(self):
        from wuzhong.notices import compatible, relevance
        self.assertEqual(SOURCE['kind'], '')
        filters = dict(area_scope='province', region='重庆', kind='国考',
                       source_id=SOURCE['id'], notice_scope='all', date_from=None,
                       year_from=None, year_to=None)
        self.assertTrue(compatible(SOURCE, filters))
        row = parse(html(title='中央机关及其直属机构2026年度考试录用公务员公告'))[0][0]
        self.assertEqual(relevance(row, filters), 'matched')
        filters['kind'] = '事业单位'
        self.assertTrue(compatible(SOURCE, filters))
        cases = {'事业单位公开招聘公告': '事业单位', '中央机关事业单位公开招聘公告': '事业单位',
                 '参公事业单位考试录用公务员公示': '省考', '编外工作人员招聘公告': '',
                 '非编人员招聘公告': '', '国有企业公开招聘公告': '', '特别提醒': '省考'}
        for title, expected in cases.items():
            self.assertEqual(chongqing_kind(title), expected, title)
        self.assertNotEqual(chongqing_kind('公开招聘工作人员公告'), '事业单位')


if __name__ == '__main__':
    unittest.main()
