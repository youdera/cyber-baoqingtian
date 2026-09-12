"""Synthetic metadata fixtures only; no real applicants or network access."""
import json
import unittest

from wuzhong.expansion_east import EXPANSION_EAST_SOURCES, parse_expansion_east


SOURCES = {s['id']: s for s in EXPANSION_EAST_SOURCES}


def parse(sid, html, url=None):
    s = SOURCES[sid]
    return parse_expansion_east(html, s, url or s['url'])


def shanghai(page=1, total=322, title='特别提醒', date='2026-09-11', extra=''):
    return f'''<ul class="uli14 list-date"><li><a href="/tnprygs_17409/20260910/t0035_1.html">{title}</a><span class="time">{date}</span></li>{extra}</ul>
    <script>totalPage: {total}; $(".pagination").pagination("setPage",{page},{total});</script>'''


def anhui(page=1, total=3, title='2025年度公开招聘公告', stamp='2026-01-08', extra=''):
    return f'''<ul class="doc_list list-6791573"><li class="odd"><a href="https://hrss.ah.gov.cn/zxzx/ztzl/ahssydwgkzp/1234.html" title="{title}">{title}</a><span class="date">{stamp}</span></li><li class="lm_line"></li>{extra}</ul>
    <script>Ls.pagination("#page_6791573", function(pageIndex){{ location.href='https://hrss.ah.gov.cn/content/column/6791573?pageIndex=' + pageIndex;}},{{currPage: ({page-1}+1),pageCount:{total}}});</script>'''


def hubei(page=0, total=17, attachment=False, title='2026年度拟录用人员公示', date='2026/09/11'):
    href = './202609/P020260911000000.xlsx' if attachment else './202609/t20260910_1.shtml'
    return f'''<ul class="list-t"><li><a href="{href}" title="{title}">{title}<span class="date">{date}</span></a></li></ul>
    <script>createPageHTML({total}, {page},"index", "shtml", "black2", 250);</script>'''


def shandong(total=1, title='2025年度招聘公告', date='2026-09-11'):
    return f'''<li class="pagedContent"><a href="/articles/ch00232/202609/aaaa-bbbb.shtml" title="{title}"><span class="news_box01_title">{title}</span><span>{date}</span></a></li>
    <script>var totalCount={total};var perSize=20;var startPage=1;var endPage=1;var logicTotalPage=1;</script>'''


def huzhou(title='2025年度公务员录用公示', daytime='2026-01-08', groups=None):
    if groups is None:
        groups = [{'infolist': [{'channelid': 68873, 'title': title, 'daytime': daytime,
                                'url': 'http://zzb.huzhou.gov.cn/gbgz/gwykl/lygs/20260108/i1234.html',
                                'userid': 'should-not-be-stored', 'summary': 'should-not-be-stored'}]}]
    return '<script>var dataList=' + json.dumps(groups, ensure_ascii=False) + ';var pagesData={"curPageNo":1,"pageTotal":1};</script>'


class ExpansionEastTests(unittest.TestCase):
    def test_sources_are_fixed_and_partial_scopes_explicit(self):
        self.assertEqual(len(SOURCES), len(EXPANSION_EAST_SOURCES))
        for s in SOURCES.values():
            self.assertTrue(s['url'].startswith('https://'))
            self.assertTrue(s['note'])
            if not s['history']:
                self.assertTrue(s['history_note'])
        self.assertFalse(SOURCES['shanghai_hires']['history'])
        self.assertEqual(SOURCES['zhejiang_huzhou_hires']['region'], '浙江')

    def test_shanghai_one_based_and_short_title(self):
        rows, nxt = parse('shanghai_hires', shanghai())
        self.assertEqual(rows[0]['title'], '特别提醒')
        self.assertTrue(nxt.endswith('index_2.html'))
        self.assertEqual(rows[0]['published'], '2026-09-11')
        self.assertIsNone(rows[0]['exam_year'])

    def test_shanghai_cap_preserves_next_page(self):
        _, nxt = parse('shanghai_hires', shanghai(120), SOURCES['shanghai_hires']['url'].replace('index.html', 'index_120.html'))
        self.assertTrue(nxt.endswith('index_121.html'))

    def test_shanghai_terminal_and_wrong_page(self):
        _, nxt = parse('shanghai_hires', shanghai(2, 2), SOURCES['shanghai_hires']['url'].replace('index.html', 'index_2.html'))
        self.assertIsNone(nxt)
        with self.assertRaises(ValueError):
            parse('shanghai_hires', shanghai(2))

    def test_empty_title_after_good_row_is_error(self):
        extra = '<li><a href="/tnprygs_17409/20260910/t0035_2.html"></a></li>'
        with self.assertRaises(ValueError):
            parse('shanghai_hires', shanghai(extra=extra))

    def test_unknown_date_stays_unknown(self):
        for stamp in ('', '2026-02-30', '本日'):
            rows, _ = parse('shanghai_hires', shanghai(date=stamp))
            self.assertIsNone(rows[0]['published'])

    def test_anhui_next_page_and_independent_year(self):
        rows, nxt = parse('anhui_jobs', anhui())
        self.assertEqual(rows[0]['exam_year'], 2025)
        self.assertEqual(rows[0]['published'], '2026-01-08')
        self.assertEqual(nxt, 'https://hrss.ah.gov.cn/content/column/6791573?pageIndex=2')

    def test_anhui_last_page_and_mismatch(self):
        _, nxt = parse('anhui_jobs', anhui(3), 'https://hrss.ah.gov.cn/content/column/6791573?pageIndex=3')
        self.assertIsNone(nxt)
        with self.assertRaises(ValueError):
            parse('anhui_jobs', anhui(1), 'https://hrss.ah.gov.cn/content/column/6791573?pageIndex=2')
        with self.assertRaises(ValueError):
            parse('anhui_jobs', anhui(), 'https://hrss.ah.gov.cn/content/column/6791574?pageIndex=1')

    def test_anhui_separator_is_allowed_but_missing_link_is_not(self):
        self.assertEqual(len(parse('anhui_jobs', anhui())[0]), 1)
        with self.assertRaises(ValueError):
            parse('anhui_jobs', anhui(extra='<li>公告标题</li>'))

    def test_hubei_zero_based_pagination(self):
        rows, nxt = parse('hubei_gwy_notice', hubei())
        self.assertEqual(rows[0]['stage'], '录聘公示')
        self.assertEqual(rows[0]['published'], '2026-09-11')
        self.assertTrue(nxt.endswith('index_1.shtml'))
        with self.assertRaises(ValueError):
            parse('hubei_gwy_notice', hubei(1))

    def test_attachment_only_terminal_is_intentional(self):
        rows, nxt = parse('hubei_gwy_notice', hubei(16, attachment=True), SOURCES['hubei_gwy_notice']['url'] + 'index_16.shtml')
        self.assertEqual(rows, [])
        self.assertIsNone(nxt)

    def test_date_inside_anchor_cannot_become_the_title(self):
        html = hubei(title='').replace('title=""', '')
        with self.assertRaises(ValueError):
            parse('hubei_gwy_notice', html)

    def test_jiangsu_cdata_and_truncated_title_preserved(self):
        html = '''<script type="text/xml"><datastore><record><![CDATA[<li><a href="/art/2026/9/10/art_78506_1.html"><span class="list_title">招聘公示...</span><i>2026-09-10</i></a></li>]]></record></datastore></script><script>columnid:78506;unitid:'325517';</script>'''
        rows, nxt = parse('jiangsu_jobs', html)
        self.assertEqual(rows[0]['title'], '招聘公示...')
        self.assertIsNone(rows[0]['exam_year'])
        self.assertEqual(rows[0]['published'], '2026-09-10')
        self.assertIsNone(nxt)
        with self.assertRaises(ValueError):
            parse('jiangsu_jobs', html.replace('招聘公示...', ''))

    def test_huzhou_only_metadata_whitelist(self):
        rows, _ = parse('zhejiang_huzhou_hires', huzhou())
        self.assertEqual(rows[0]['exam_year'], 2025)
        self.assertEqual(rows[0]['published'], '2026-01-08')
        self.assertTrue(rows[0]['url'].startswith('https://'))
        self.assertNotIn('userid', rows[0])
        self.assertNotIn('summary', rows[0])
        for invalid in ('', None, 'x' * 501):
            with self.assertRaises(ValueError):
                parse('zhejiang_huzhou_hires', huzhou(title=invalid))

    def test_huzhou_missing_or_invalid_group_fails(self):
        for groups in ([], [{'infolist': []}], [{'infolist': ['bad']}], {'infolist': []}):
            with self.assertRaises(ValueError):
                parse('zhejiang_huzhou_hires', huzhou(groups=groups))

    def test_shandong_reads_embedded_records_and_validates_count(self):
        rows, nxt = parse('shandong_jobs', shandong())
        self.assertEqual(rows[0]['published'], '2026-09-11')
        self.assertEqual(rows[0]['exam_year'], 2025)
        self.assertIsNone(nxt)
        with self.assertRaises(ValueError):
            parse('shandong_jobs', shandong(total=2))

    def test_shandong_missing_date_does_not_use_url_date(self):
        rows, _ = parse('shandong_jobs', shandong(date=''))
        self.assertIsNone(rows[0]['published'])

    def test_henan_legacy_link_date_and_unknown_kind(self):
        html = '''<div id="pageDec" pagesize="24" pagecount="51"></div><table><tr><td class="xin2zuo"><table><tr><td><a href="http://hrss.henan.gov.cn/2026/09-11/1234.html">特别提醒</a></td><td>[2026-09-12]</td></tr></table></td></tr></table>'''
        rows, _ = parse('henan_hr_recruit', html)
        self.assertEqual(rows[0]['published'], '2026-09-12')
        self.assertEqual(rows[0]['kind'], '')
        self.assertTrue(rows[0]['url'].startswith('https://'))

    def test_fujian_template_and_non_recruitment_filter(self):
        html = '''<script>list2.trsapi;recordCount:'2';</script><ul class="gl-ul"><li><a href="../../gsgg/202609/t20260911_1.htm" title="2026年事业单位招聘公告"><div class="li-btn">2026-09-11</div></a></li><li><a href="../../gsgg/202609/t20260911_2.htm" title="关于调整内设机构的通知"></a></li><li ms-repeat="list"><a ms-attr-href="el.url"></a></li></ul>'''
        rows, _ = parse('fujian_forest_recruit', html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['kind'], '事业单位')
        self.assertEqual(rows[0]['published'], '2026-09-11')

    def test_external_and_attachment_links_are_excluded(self):
        extra = '<li><a href="https://outside.example/notice.html">外站公示</a></li><li><a href="/tnprygs_17409/20260910/list.pdf">附件名单</a></li>'
        self.assertEqual(len(parse('shanghai_hires', shanghai(extra=extra))[0]), 1)

    def test_changed_same_host_path_and_request_origin_fail(self):
        with self.assertRaises(ValueError):
            parse('shanghai_hires', shanghai().replace('t0035_1.html', 'new-format.html'))
        for url in ('http://rsj.sh.gov.cn/tnprygs_17409/index.html', 'https://rsj.sh.gov.cn.evil.example/tnprygs_17409/index.html', 'https://user@rsj.sh.gov.cn/tnprygs_17409/index.html'):
            with self.assertRaises(ValueError):
                parse('shanghai_hires', shanghai(), url)

    def test_hunan_one_based_and_terminal_pages(self):
        def html(page):
            return f'''<div class="xxgkzd-box"><div class="box"><ul><li><a href="/rst/xxgk/zpzl/sydwzp/202609/t20260911_1.html">2026年事业单位拟聘人员公示</a><span>2026-09-11</span></li></ul></div></div><script>createPageHTML('paging',25,{page},'index','html',500);</script>'''
        rows, nxt = parse('hunan_jobs', html(1))
        self.assertEqual(rows[0]['stage'], '录聘公示')
        self.assertTrue(nxt.endswith('index_2.html'))
        rows, nxt = parse('hunan_jobs', html(25), SOURCES['hunan_jobs']['url'] + 'index_25.html')
        self.assertIsNone(nxt)
        with self.assertRaises(ValueError):
            parse('hunan_jobs', html(2))

    def test_jingdezhen_local_scope_and_explicit_date(self):
        html = '''<ul class="info-list"><li><a href="./t1234.shtml" title="2025年公务员录用公示">2025年公务员录用公示</a><span name="PushDate">2026-01-08</span></li></ul><script>createPageHTML(7,0,"index","shtml","black2",136);</script>'''
        rows, nxt = parse('jiangxi_jingdezhen_recruit', html)
        self.assertEqual(rows[0]['region'], '江西')
        self.assertEqual(rows[0]['kind'], '省考')
        self.assertEqual(rows[0]['published'], '2026-01-08')
        self.assertEqual(rows[0]['exam_year'], 2025)
        self.assertTrue(nxt.endswith('index_1.shtml'))
        with self.assertRaises(ValueError):
            parse('jiangxi_jingdezhen_recruit', html.replace('136);', '136);createPageHTML(7,0,"index","shtml","black2",136);'))

    def test_drift_never_successful_empty(self):
        for sid in SOURCES:
            with self.assertRaises(ValueError, msg=sid):
                parse(sid, '<html><body>临时维护</body></html>')

    def test_excluded_external_or_attachment_rows_keep_history_partial(self):
        for sid in ['anhui_city','hubei_gwy_notice','jiangxi_jingdezhen_recruit']:
            self.assertFalse(SOURCES[sid]['history'])
            self.assertTrue(SOURCES[sid]['history_note'])


if __name__ == '__main__':
    unittest.main()
