import unittest

from wuzhong.extra_sources import EXTRA_SOURCES, SOURCE_AREAS, parse_extra


BJ, JXJ, FJ_HR = EXTRA_SOURCES


def directory(source=BJ, total=7, current=0, published='2026-09-01', title='2025年度模拟公务员拟录用公示'):
    return f'''<script>Pager({{size:{total}, current:{current}, prefix:'index',suffix:'html'}});</script>
    <ul><li><a title="{title}" href="{source['url']}202609/t20260901_123.html">公告</a><span>{published}</span></li></ul>
    <a href="{source['url']}名单.xlsx">名单附件</a><table><tr><td>名单正文不得索引</td></tr></table>'''


class ExtraSourceTests(unittest.TestCase):
    def test_fixed_provincial_sources(self):
        self.assertEqual(SOURCE_AREAS, {'beijing': 'province', 'beijing_jxj': 'province', 'fujian_hr': 'province'})
        self.assertTrue(all(s['history'] and s['max_pages'] == 60 for s in [BJ, JXJ]))
        self.assertFalse(FJ_HR['history'])

    def test_zero_based_pager_and_independent_dates(self):
        rows, nxt = parse_extra(directory(), BJ, BJ['url'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['published'], '2026-09-01')
        self.assertEqual(rows[0]['exam_year'], 2025)
        self.assertEqual(nxt, BJ['url'] + 'index_1.html')
        self.assertEqual(parse_extra(directory(current=1), BJ, nxt)[1], BJ['url'] + 'index_2.html')
        self.assertIsNone(parse_extra(directory(current=6), BJ, BJ['url'] + 'index_6.html')[1])
        self.assertNotIn('名单正文', str(rows))

    def test_repeated_homepage_or_changed_pagination_is_not_complete(self):
        for html, url in [(directory(), BJ['url'] + 'index_1.html'),
                          (directory().replace('Pager', 'Other'), BJ['url']),
                          (directory().replace("suffix:'html'", "suffix:'shtml'"), BJ['url']),
                          (directory(total=0), BJ['url'])]:
            with self.assertRaises(ValueError):
                parse_extra(html, BJ, url)

    def test_allowlist_excludes_files_offsite_and_wrong_directory(self):
        html = directory()
        for bad in ['https://example.com/202609/t20260901_234.html',
                    'https://www.beijing.gov.cn/other/202609/t20260901_234.html',
                    'http://www.beijing.gov.cn/gongkai/rsxx/gwyzk/202609/t20260901_234.html',
                    BJ['url'] + '202609/t20260901_234.pdf',
                    BJ['url'] + '202609/t20260901_234.html?download=1']:
            html += f'<li><a href="{bad}">2026年度模拟招考公告不得纳入</a><span>2026-09-01</span></li>'
        self.assertEqual(len(parse_extra(html, BJ, BJ['url'])[0]), 1)
        with self.assertRaises(ValueError):
            parse_extra(directory().replace('t20260901_123.html', 't20260901_123.pdf'), BJ, BJ['url'])

    def test_missing_metadata_is_unknown_not_url_date(self):
        rows, _ = parse_extra(directory(published='', title='模拟单位公务员拟录用公示'), BJ, BJ['url'])
        self.assertIsNone(rows[0]['published'])
        self.assertIsNone(rows[0]['exam_year'])

    def test_mixed_personnel_directory_excludes_unrelated_titles(self):
        html = directory(JXJ, title='模拟机构干部任免通知')
        rows, nxt = parse_extra(html, JXJ, JXJ['url'])
        self.assertEqual(rows, [])
        self.assertIsNotNone(nxt)
        rows, _ = parse_extra(directory(JXJ, title='2026年所属事业单位招聘工作人员公告'), JXJ, JXJ['url'])
        self.assertEqual(rows[0]['kind'], '事业单位')

    def test_fujian_static_block_keeps_history_partial(self):
        html = directory(FJ_HR).replace('t20260901_123.html', 't20260901_123.htm')
        html += "<script>require(['list2.trsapi']);listModel({maxStaticIndex:7,pagebar:{prepage:10,recordCount:'213'}})</script>"
        rows, nxt = parse_extra(html, FJ_HR, FJ_HR['url'])
        self.assertEqual(len(rows), 1)
        self.assertIsNone(nxt)
        self.assertFalse(FJ_HR['history'])
        self.assertEqual(FJ_HR['max_pages'], 1)
        with self.assertRaises(ValueError):
            parse_extra(html.replace('recordCount', 'changedCount'), FJ_HR, FJ_HR['url'])


if __name__ == '__main__':
    unittest.main()
