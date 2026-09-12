import unittest
from urllib.parse import urljoin

from wuzhong.expansion_north import EXPANSION_NORTH_SOURCES, parse_expansion_north


SOURCES = {s['id']: s for s in EXPANSION_NORTH_SOURCES}
TITLE = '2025年度模拟单位公开招聘拟聘用公示'


def listing(sid, page=0, pages=3, stamp='2026-09-01', title=TITLE, href=None):
    source = SOURCES[sid]
    if sid == 'neimenggu_medical_recruitment':
        href = href or './zkxx_9374/202601/t20260101_12345.html'
        return f'''<h3>招考信息</h3><table id="table1"><tr><td>1</td><td><a href="{href}">{title}</a></td>
          <td class="mobile"><a href="{href}">{title}</a><span>发布日期：{stamp}</span></td><td>{stamp}</td></tr></table>
          <h3>录用结果信息</h3><table id="table1"><tr><th>标题</th></tr></table>'''
    if sid == 'hebei_cyberspace_recruitment':
        href = href or '//www.caheb.gov.cn/system/2026/01/01/12345.shtml'
        return f'<div class="ct_list"><ul><li><a href="{href}">{title}</a><span>{stamp}</span></li></ul></div>'
    if sid.startswith('liaoning_'):
        page = page or 1
        code = {'liaoning_gwy_notices': '119', 'liaoning_sydw_notices': '80', 'liaoning_sydw_jobs': '78'}[sid]
        href = href or './12345.html'
        nxt = f'<a href="{code}_{page+1}.html">下一页</a>' if page < pages else '<span>下一页</span>'
        return f'''<div class="kaoshilist"><div class="kaoshilistlefttop1">{stamp[5:]}</div>
          <div class="kaoshilistleftbottom1">{stamp[:4]}</div>
          <div class="kaoshilistrighttitle"><a href="{href}">{title}</a></div></div>
          <div id="Pagination"><div id="page_center_botton"><span class="active">{page}</span></div>{nxt}</div>'''
    if sid == 'hainan_gov_notices':
        page = page or 1
        href = href or '/hainan/0101/202601/abcd1234.shtml'
        return f'''<div class="list_div"><div class="list-right_title"><a href="{href}">{title}</a></div>
          <table><tr><td>发布时间： {stamp}</td></tr></table></div>
          <script>createPageHTML('page_div',{pages},{page},'list3_1','shtml',{pages * 12});</script>'''
    if sid.startswith('guangxi_'):
        href = href or './t12345.html'
        pager = f'<script>createPageHTML({pages},{page}, "index","html");</script>'
        opening, closing = '<ul class="articles">', '</ul>'
    elif sid == 'heilongjiang_hr_notices':
        href = href or '/hrss/c111741/202601/c00_12345.shtml'
        pager, opening, closing = '', '<ul class="listul">', '</ul>'
    else:
        href = href or './202601/t20260101_12345.html'
        pager = f'<script>var currentPage={page}; var countPage={pages};</script>'
        if sid == 'beijing_hr_jobs':
            opening, closing = '<ul class="list">', '</ul>'
        elif sid == 'tianjin_hr_jobs':
            pager = f'''<script>var pager_options={{ currentPage:parseInt('{page}')+1,
            countPage:parseInt('{pages}}}'), PAGE_NAME:'index', PAGE_EXT:'html' }};</script>'''
            opening, closing = '<div class="fmultimedia-y"><ul>', '</ul></div>'
        else:
            css = 'news_list4' if sid == 'jilin_hr_jobs' else 'news_list3'
            opening, closing = f'<div class="{css}"><ul>', '</ul></div>'
    return pager + opening + f'<li><a href="{href}" title="{title}">短标题</a><span>[{stamp}]</span></li>' + closing


class ExpansionNorthTests(unittest.TestCase):
    def parse(self, sid, **kwargs):
        source = SOURCES[sid]
        return parse_expansion_north(listing(sid, **kwargs), source, source['url'])

    def test_all_fixed_directories_return_only_metadata(self):
        fields = {'id', 'source_id', 'source', 'owner', 'title', 'url', 'published', 'exam_year', 'kind', 'region', 'stage'}
        for sid, source in SOURCES.items():
            with self.subTest(sid=sid):
                rows, _ = self.parse(sid)
                self.assertEqual(len(rows), 1)
                row = rows[0]
                self.assertEqual(set(row), fields)
                self.assertEqual(row['published'], '2026-09-01')
                self.assertEqual(row['exam_year'], 2025)
                self.assertEqual(row['stage'], '录聘公示')
                self.assertEqual(row['title'], TITLE)
                self.assertEqual(row['region'], source['region'])

    def test_zero_based_static_pages_and_safety_cap_keep_continuation(self):
        for sid in ['beijing_hr_jobs', 'tianjin_hr_jobs', 'jilin_hr_jobs', 'guangxi_sydw_jobs']:
            source = SOURCES[sid]
            with self.subTest(sid=sid):
                for page in [1, 2, 119]:
                    pages = 121 if page == 119 else 3
                    url = urljoin(source['url'], f'index_{page}.html')
                    _, nxt = parse_expansion_north(listing(sid, page=page, pages=pages), source, url)
                    self.assertEqual(nxt, urljoin(url, f'index_{page+1}.html') if page+1 < pages else None)

    def test_liaoning_follows_only_official_next_and_disabled_terminal(self):
        sid = 'liaoning_sydw_notices'
        source = SOURCES[sid]
        for page in [2, 3]:
            _, nxt = parse_expansion_north(listing(sid, page=page), source, source['url'] + f'80_{page}.html')
            self.assertEqual(nxt, source['url'] + '80_3.html' if page == 2 else None)
        self.assertFalse(source['history'])
        self.assertGreater(source['max_pages'], 1)
        bad = listing(sid).replace('80_2.html', '80_30.html')
        with self.assertRaisesRegex(ValueError, '下一页地址异常'):
            parse_expansion_north(bad, source, source['url'])

    def test_hainan_one_based_page_addresses_and_totals(self):
        sid = 'hainan_gov_notices'
        source = SOURCES[sid]
        _, nxt = self.parse(sid)
        self.assertEqual(nxt, urljoin(source['url'], 'list3_1_2.shtml'))
        _, nxt = parse_expansion_north(listing(sid, page=3), source, urljoin(source['url'], 'list3_1_3.shtml'))
        self.assertIsNone(nxt)
        with self.assertRaisesRegex(ValueError, '总数异常'):
            parse_expansion_north(listing(sid).replace("'shtml',36", "'shtml',100"), source, source['url'])

    def test_unrelated_mixed_directory_can_be_empty_without_implying_failure(self):
        for sid in ['jilin_hr_notices', 'heilongjiang_hr_notices', 'hainan_gov_notices']:
            with self.subTest(sid=sid):
                rows, _ = self.parse(sid, title='模拟职业技能补贴发放公告')
                self.assertEqual(rows, [])
                row = self.parse(sid, title='2026年模拟单位招聘公告')[0][0]
                self.assertEqual(row['kind'], '')
                row = self.parse(sid, title='2026年模拟公务员招录公示')[0][0]
                self.assertEqual(row['kind'], '省考')

    def test_no_publication_date_inferred_from_url_or_title(self):
        for stamp in ['', '2026-02-30', '2026-09-01 2026-09-02']:
            with self.subTest(stamp=stamp):
                rows, _ = self.parse('beijing_hr_jobs', stamp=stamp,
                                     title='模拟招聘公告（2026年9月1日）')
                self.assertIsNone(rows[0]['published'])
                self.assertIsNone(rows[0]['exam_year'])
        html = listing('beijing_hr_jobs').replace('</li>', '<span>2026-09-02</span></li>')
        self.assertIsNone(parse_expansion_north(html, SOURCES['beijing_hr_jobs'], SOURCES['beijing_hr_jobs']['url'])[0][0]['published'])

    def test_missing_split_liaoning_date_is_unknown(self):
        source = SOURCES['liaoning_gwy_notices']
        html = listing(source['id']).replace('kaoshilistleftbottom1', 'removed')
        rows, _ = parse_expansion_north(html, source, source['url'])
        self.assertIsNone(rows[0]['published'])

    def test_attachments_external_and_nonstandard_urls_are_excluded(self):
        source = SOURCES['guangxi_sydw_jobs']
        html = listing(source['id'])
        bad = ['https://example.com/t222.html', source['url'] + 't222.html?download=1',
               source['url'].replace('https:', 'http:') + 't222.html', './人员.xlsx',
               source['url'].replace('www.gxpta.com.cn', 'user@www.gxpta.com.cn') + 't222.html',
               source['url'].replace('www.gxpta.com.cn', 'www.gxpta.com.cn:444') + 't222.html']
        extras = ''.join(f'<li><a href="{url}" title="模拟招聘公告">模拟招聘公告</a></li>' for url in bad)
        html = html.replace('</ul>', extras + '</ul>') + '<p>虚构正文不得索引</p>'
        rows, _ = parse_expansion_north(html, source, source['url'])
        self.assertEqual(len(rows), 1)
        self.assertNotIn('虚构正文', str(rows))

    def test_duplicate_links_deduplicated(self):
        source = SOURCES['beijing_hr_jobs']
        html = listing(source['id'])
        row = html[html.index('<li>'):html.index('</li>') + 5]
        rows, _ = parse_expansion_north(html.replace('</ul>', row + '</ul>'), source, source['url'])
        self.assertEqual(len(rows), 1)

    def test_short_titles_preserved_and_missing_title_fails(self):
        self.assertEqual(self.parse('guangxi_sydw_jobs', title='更正')[0][0]['title'], '更正')
        source = SOURCES['guangxi_sydw_jobs']
        html = listing(source['id'], title='').replace('短标题', '')
        with self.assertRaisesRegex(ValueError, '标题为空'):
            parse_expansion_north(html, source, source['url'])

    def test_layout_and_page_drift_fail_explicitly(self):
        sid = 'beijing_hr_jobs'
        source = SOURCES[sid]
        for html in [listing(sid, page=1), listing(sid, pages=0), listing(sid).replace('countPage', 'renamed'),
                     listing(sid).replace('class="list"', 'class="renamed"'),
                     listing(sid).replace('./202601/t20260101_12345.html', './file.pdf')]:
            with self.subTest(html=html[:100]), self.assertRaises(ValueError):
                parse_expansion_north(html, source, source['url'])
        for url in [source['url'] + 'index_0.html', source['url'] + '?page=2',
                    source['url'].replace('https:', 'http:'), source['url'] + '202601/t20260101_12345.html']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                parse_expansion_north(listing(sid), source, url)

    def test_fixed_sources_and_static_only_policy(self):
        sid = 'heilongjiang_hr_notices'
        source = SOURCES[sid]
        self.assertFalse(source['history'])
        self.assertEqual(source['max_pages'], 1)
        with self.assertRaises(ValueError):
            parse_expansion_north(listing(sid), source, source['url'] + '?page=2')
        with self.assertRaises(ValueError):
            parse_expansion_north(listing(sid), dict(source, id='unregistered'), source['url'])
        with self.assertRaises(ValueError):
            parse_expansion_north(listing(sid), dict(source, url='https://example.com/'), 'https://example.com/')

    def test_local_fallback_columns_keep_scope_and_unknown_type(self):
        for sid in ['hebei_cyberspace_recruitment', 'neimenggu_medical_recruitment']:
            source = SOURCES[sid]
            with self.subTest(sid=sid):
                self.assertFalse(source['history'])
                self.assertEqual(source['max_pages'], 1)
                rows, nxt = self.parse(sid, title='更正')
                self.assertEqual(rows[0]['kind'], '')
                self.assertIsNone(nxt)
                with self.assertRaises(ValueError):
                    parse_expansion_north(listing(sid), source, urljoin(source['url'], 'index_1.html'))

    def test_medical_two_tables_deduplicate_mobile_links_and_reject_drift(self):
        sid = 'neimenggu_medical_recruitment'
        source = SOURCES[sid]
        rows, _ = self.parse(sid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['published'], '2026-09-01')
        for html in [listing(sid).replace('录用结果信息', '未知栏目'),
                     listing(sid).replace('id="table1"', 'id="changed"'),
                     listing(sid, href='http://www.impta.com.cn/sydw/123.asp')]:
            with self.subTest(html=html[:70]), self.assertRaises(ValueError):
                parse_expansion_north(html, source, source['url'])


if __name__ == '__main__':
    unittest.main()
