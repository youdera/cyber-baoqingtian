import unittest

from wuzhong.east_sources import EAST_SOURCES, parse_east


GWY, SYDW, JOBS = EAST_SOURCES


def directory(page=0, pages=3, stamp='2026.09.01', title='2025年度模拟单位拟录用公示', href=None):
    href = href or './2025gwy/202609/t20260901_12345.shtml'
    return f'''<script>var currentPage = {page}; var countPage = {pages};</script>
    <ul class="second_right_ul"><li><a href="{href}" title="{title}">缩略标题</a>
    <span class="pull-right">{stamp}</span></li></ul>'''


class EastSourceTests(unittest.TestCase):
    def test_metadata_preserves_separate_exam_and_publication_years(self):
        rows, nxt = parse_east(directory(), GWY, GWY['url'])
        self.assertEqual(rows[0]['title'], '2025年度模拟单位拟录用公示')
        self.assertEqual(rows[0]['published'], '2026-09-01')
        self.assertEqual(rows[0]['exam_year'], 2025)
        self.assertEqual(rows[0]['stage'], '录聘公示')
        self.assertEqual(nxt, GWY['url'] + 'index_1.shtml')
        self.assertEqual(rows[0]['kind'], '省考')
        self.assertEqual(rows[0]['region'], '山西')

    def test_zero_based_second_last_and_cap_pages(self):
        self.assertEqual(parse_east(directory(1), GWY, GWY['url'] + 'index_1.shtml')[1],
                         GWY['url'] + 'index_2.shtml')
        self.assertIsNone(parse_east(directory(2), GWY, GWY['url'] + 'index_2.shtml')[1])
        self.assertIsNotNone(parse_east(directory(119, 121), GWY,
                                       GWY['url'] + 'index_119.shtml')[1])

    def test_missing_invalid_and_title_only_dates_stay_unknown(self):
        for stamp in ['', '2026.02.30', '2026.09.01 2026.09.02']:
            with self.subTest(stamp=stamp):
                rows, _ = parse_east(directory(stamp=stamp,
                    title='模拟招录公告（2026年9月1日）'), GWY, GWY['url'])
                self.assertIsNone(rows[0]['published'])
                self.assertIsNone(rows[0]['exam_year'])

    def test_republished_official_article_outside_column_is_included(self):
        href = 'https://rst.shanxi.gov.cn/ztzl/zpxx/szsydwzpgg/202601/t20260129_12345.shtml'
        rows, _ = parse_east(directory(href=href), SYDW, SYDW['url'])
        self.assertEqual(rows[0]['url'], href)
        self.assertEqual(rows[0]['kind'], '事业单位')

    def test_provincial_recruitment_column_without_title_attribute(self):
        html = directory(href='./202607/t20260707_12345.shtml',
                         title='2026年模拟事业单位公开招聘公告')
        html = html.replace(' title="2026年模拟事业单位公开招聘公告"', '')
        html = html.replace('缩略标题', '2026年模拟事业单位公开招聘公告')
        rows, nxt = parse_east(html, JOBS, JOBS['url'])
        self.assertEqual(rows[0]['title'], '2026年模拟事业单位公开招聘公告')
        self.assertEqual(rows[0]['url'], JOBS['url'] + '202607/t20260707_12345.shtml')
        self.assertEqual(nxt, JOBS['url'] + 'index_1.shtml')

    def test_attachments_external_links_forms_and_page_body_are_excluded(self):
        html = directory()
        unrelated = '''<li><a href="https://example.com/rsks/gwyks/202609/t20260901_777.shtml">外部公告不可收录</a></li>
        <li><a href="https://rst.shanxi.gov.cn:444/rsks/gwyks/202609/t20260901_778.shtml">异常端口链接</a></li>
        <li><a href="https://user@rst.shanxi.gov.cn/rsks/gwyks/202609/t20260901_779.shtml">凭据链接</a></li>
        <li><a href="./202609/t20260901_999.shtml?download=1">下载入口不可收录</a></li>
        <li><a href="./202609/名单.xlsx">名单文件不可收录</a></li>'''
        html = html.replace('</ul>', unrelated + '</ul>')
        html += '<div>虚构人员记录不得索引</div><form><input name="person" value="虚构记录"></form>'
        rows, _ = parse_east(html, GWY, GWY['url'])
        self.assertEqual(len(rows), 1)
        self.assertNotIn('虚构', str(rows))

    def test_same_url_is_deduplicated_and_full_title_used(self):
        html = directory()
        row = html[html.index('<li>'):html.index('</li>') + 5]
        rows, _ = parse_east(html.replace('</ul>', row + '</ul>'), GWY, GWY['url'])
        self.assertEqual(len(rows), 1)
        self.assertNotEqual(rows[0]['title'], '缩略标题')

    def test_short_official_titles_are_not_silently_dropped(self):
        for title in ['通知', '特别提醒', '更正']:
            with self.subTest(title=title):
                rows, _ = parse_east(directory(title=title), GWY, GWY['url'])
                self.assertEqual(rows[0]['title'], title)
        html = directory(title='   ').replace('缩略标题', '特别提醒')
        self.assertEqual(parse_east(html, GWY, GWY['url'])[0][0]['title'], '特别提醒')

    def test_malformed_title_in_otherwise_valid_page_fails(self):
        for title in ['', '   ', '公' * 501]:
            with self.subTest(title=title[:10]):
                invalid = directory(title=title, href='./202609/t20260901_98765.shtml')
                invalid = invalid.replace('缩略标题', ' ')
                row = invalid[invalid.index('<li>'):invalid.index('</li>') + 5]
                mixed_page = directory().replace('</ul>', row + '</ul>')
                with self.assertRaisesRegex(ValueError, '公告标题为空或长度异常'):
                    parse_east(mixed_page, GWY, GWY['url'])

    def test_page_drift_and_unknown_sources_fail_explicitly(self):
        cases = [directory().replace('countPage', 'renamed'), directory(pages=0),
                 directory(page=1), directory().replace('second_right_ul', 'renamed'),
                 directory().replace('.shtml', '.pdf'), directory() + '<script>var currentPage=0;</script>']
        for html in cases:
            with self.subTest(html=html[:90]), self.assertRaises(ValueError):
                parse_east(html, GWY, GWY['url'])
        for url in [GWY['url'] + 'index_0.shtml', GWY['url'] + '?page=2',
                    GWY['url'].replace('https:', 'http:')]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                parse_east(directory(), GWY, url)
        with self.assertRaises(ValueError):
            parse_east(directory(), dict(GWY, id='unknown'), GWY['url'])


if __name__ == '__main__':
    unittest.main()
