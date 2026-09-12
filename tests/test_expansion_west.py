import unittest
from urllib.parse import urljoin

from wuzhong.expansion_west import EXPANSION_WEST_SOURCES, parse_expansion_west


SOURCES = {s['id']: s for s in EXPANSION_WEST_SOURCES}


def directory(id_='gz_hr_recruit', *, current=None, total=3,
              title='2025年度模拟单位公开招聘拟聘用公示', published='2026-09-02', href=None):
    source = SOURCES[id_]
    one_based = id_ in {'yn_hr_recruit', 'qh_hr_recruit', 'gs_exam_recruit',
                        'xj_hr_civil', 'xj_hr_recruit', 'bt_exam_civil', 'bt_exam_recruit'}
    current = int(one_based) if current is None else current
    href = href or urljoin(source['url'], f'202609/t20260902_{current+100}.html')
    row = f'<a href="{href}" title="{title}">缩略标题</a><span>{published}</span>'
    pager = f'<script>createPageHTML({total},{current},"index","html");</script>'
    wrappers = {
        'gz_hr_recruit': ('<div class="right-list-box"><ul><li>', '</li></ul></div>'),
        'yn_gov_civil': ('<ul class="wjer_list"><li>', '</li></ul>'),
        'nx_exam_civil': ('<div class="content"><p class="title-li">', '</p></div>'),
        'nx_exam_recruit': ('<div class="content"><p class="title-li">', '</p></div>'),
    }
    if id_ in wrappers:
        before, after = wrappers[id_]
    elif id_ == 'xz_hr_notices':
        before, after = '<div class="gl-list"><div class="gl-list-item">', '</div></div>'
        row = f'<a class="nm" href="{href}">{title}</a><div class="date">{published}</div>'
    elif id_ == 'sn_hr_notices':
        before, after = '<ul class="list"><li class="list-item">', '</li></ul>'
        row = f'<a href="{href}"><div class="text">{title}</div><div class="time">{published}</div></a>'
        pager = pager.replace('createPageHTML', 'createPage')
    elif id_ == 'yn_hr_recruit':
        href = '/NewsView.aspx?NewsID=123&ClassID=602'
        before, after = '<div class="listBox"><ul class="ul13"><li>', '</li></ul></div>'
        row = f'<a href="{href}" title="{title}">缩略标题</a><span>{published}</span>'
        pager = f'<div id="Body_AspNetPager1">第{current}页 共 {total} 页 <a href="/NewsLsit.aspx?ClassID=602&page={current+1}">下一页</a></div>'
    elif id_ == 'qh_hr_recruit':
        href = '/ztzl/kldt/query/12345.html'
        before, after = '<ul class="list"><li>', '</li></ul>'
        row = f'<a href="{href}">{title}</a><span>{published}</span>'
        pager = f'<div><span class="current">{current}</span><a href="/ztzl/kldt/list/{total}.html">尾页</a></div>'
    elif id_ == 'gs_exam_recruit':
        href = '/ncms/article_' + 'a' * 32 + '.shtml'
        before, after = '<ul class="ap"><li>', '</li></ul>'
        row = f'<a href="{href}" title="{title}"><span class="you">[{published}]</span></a>'
        pager = f'''<script>var dataTotal = parseInt("{total*15}");var pagenum = parseInt("{current}");
        var target="wzlb.shtml?mkbh=gwysydwks&begin=";</script>'''
    elif id_.startswith('xj_'):
        href = '/xjrst/c112746/202609/' + 'a'*32 + '.shtml'
        if id_ == 'xj_hr_civil':
            before, after = '<div class="gknr_list"><dl><dd>', '</dd></dl></div>'
            row = f'<a href="{href}" title="{title}">缩略标题</a><span>{published}</span>'
            prefix = 'zfxxgk_gknrz'
        else:
            before, after = '<ul class="com-pic-news-list"><li>', '</li></ul>'
            row = f'<a class="cpn-title" href="{href}" title="{title}">缩略标题</a><span class="cpn-date">{published}</span><span class="cpn-des">正文摘要不应保存</span>'
            prefix = 'list'
        pager = f'<script>createPageHTML("page_div",{total},{current},"{prefix}","shtml",{total*6});</script>'
    elif id_.startswith('bt_'):
        href = '/c/2026-09-02/12345.shtml'
        before, after = '<div class="right_wrap"><div class="con"><ul><li>', '</li></ul></div></div>'
        row = f'<a href="{href}" title="{title}">缩略标题</a><span class="fr">{published}</span>'
        pager = f'''<input id="PageInp" value="{current}"><span class="pageCount">{total}</span>
        <script>PageIndex=PageIndex>{total}?{total}:PageIndex;var path='index_${{PageIndex}}.shtml';</script>'''
    else:
        raise AssertionError(id_)
    return before + row + after + pager + '<a href="/private.xlsx">名单附件不得索引</a><table><tr><td>名单正文不得索引</td></tr></table>'


class ExpansionWestTests(unittest.TestCase):
    def test_every_registered_layout_extracts_metadata_only(self):
        for source in EXPANSION_WEST_SOURCES:
            with self.subTest(source=source['id']):
                rows, nxt = parse_expansion_west(directory(source['id']), source, source['url'])
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['title'], '2025年度模拟单位公开招聘拟聘用公示')
                self.assertEqual(rows[0]['published'], '2026-09-02')
                self.assertEqual(rows[0]['exam_year'], 2025)
                self.assertEqual(rows[0]['source_id'], source['id'])
                self.assertIsNotNone(nxt)
                self.assertNotIn('正文', str(rows))
                self.assertNotIn('xlsx', str(rows))

    def test_first_second_terminal_and_repeated_homepage(self):
        for source in EXPANSION_WEST_SOURCES:
            id_ = source['id']
            with self.subTest(source=id_):
                first = 1 if id_ in {'yn_hr_recruit','qh_hr_recruit','gs_exam_recruit','xj_hr_civil','xj_hr_recruit','bt_exam_civil','bt_exam_recruit'} else 0
                _, second = parse_expansion_west(directory(id_), source, source['url'])
                with self.assertRaises(ValueError):
                    parse_expansion_west(directory(id_), source, second)
                _, last = parse_expansion_west(directory(id_, current=first+1), source, second)
                self.assertIsNone(parse_expansion_west(directory(id_, current=first+2), source, last)[1])

    def test_unknown_dates_remain_unknown_and_dates_do_not_pollute_title(self):
        for published in ['', '2026-02-30', '待确认']:
            for id_ in ['sn_hr_notices','yn_gov_civil','gs_exam_recruit']:
                with self.subTest(source=id_, published=published):
                    source = SOURCES[id_]
                    rows, _ = parse_expansion_west(directory(id_, published=published, title='模拟公开招聘公告'), source, source['url'])
                    self.assertIsNone(rows[0]['published'])
                    self.assertIsNone(rows[0]['exam_year'])
                    self.assertEqual(rows[0]['title'], '模拟公开招聘公告')

    def test_mixed_directories_filter_unrelated_titles_but_keep_pagination(self):
        for id_ in ['xz_hr_notices','sn_hr_notices']:
            source = SOURCES[id_]
            rows, nxt = parse_expansion_west(directory(id_, title='办公设备采购结果公告'), source, source['url'])
            self.assertEqual(rows, [])
            self.assertIsNotNone(nxt)

    def test_recognizable_template_failure_is_not_zero(self):
        for source in EXPANSION_WEST_SOURCES:
            with self.subTest(source=source['id']), self.assertRaises(ValueError):
                parse_expansion_west('<html>系统升级中</html>', source, source['url'])
        source = SOURCES['gz_hr_recruit']
        for html in [directory().replace('right-list-box', 'changed-layout'),
                     directory().replace('createPageHTML', 'changedPaging'),
                     directory(total=0), directory().replace('"html"', '"pdf"')]:
            with self.assertRaises(ValueError):
                parse_expansion_west(html, source, source['url'])

    def test_official_url_allowlist_rejects_external_files_and_other_columns(self):
        source = SOURCES['gz_hr_recruit']
        invalid = ['https://attacker.example/202609/t20260902_123.html',
                   source['url'] + '202609/t20260902_123.pdf',
                   source['url'] + '202609/t20260902_123.html?download=1',
                   'https://rst.guizhou.gov.cn/other/202609/t20260902_123.html',
                   source['url'].replace('https:', 'http:') + '202609/t20260902_123.html']
        for href in invalid:
            with self.subTest(href=href), self.assertRaises(ValueError):
                parse_expansion_west(directory(href=href), source, source['url'])

    def test_directory_requests_cannot_change_host_or_category(self):
        for source in EXPANSION_WEST_SOURCES:
            for url in [source['url'].replace('https:', 'http:'),
                        source['url'].replace('https://', 'https://attacker.example/'),
                        source['url'] + '#fragment']:
                with self.subTest(source=source['id'],url=url), self.assertRaises(ValueError):
                    parse_expansion_west(directory(source['id']), source, url)
        source = SOURCES['yn_hr_recruit']
        for suffix in ['&ClassID=603', '&page=1&page=2', '&extra=1']:
            with self.assertRaises(ValueError):
                parse_expansion_west(directory('yn_hr_recruit'), source, source['url']+suffix)

    def test_xinjiang_can_link_another_column_and_infer_exam_kind(self):
        source = SOURCES['xj_hr_recruit']
        rows, _ = parse_expansion_west(directory(source['id'], title='中央机关及其直属机构2026年度考试录用公务员公告'), source, source['url'])
        self.assertEqual(rows[0]['kind'], '国考')
        rows, _ = parse_expansion_west(directory(source['id'], title='自治区2026年度考试录用公务员公告'), source, source['url'])
        self.assertEqual(rows[0]['kind'], '省考')

    def test_gansu_legacy_article_ids_are_not_lost_on_older_pages(self):
        source = SOURCES['gs_exam_recruit']
        html = directory(source['id']).replace('a'*32, 'N082111171680')
        rows, _ = parse_expansion_west(html, source, source['url'])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['url'].endswith('article_N082111171680.shtml'))
        for value in ['N08211117168','N0821111716800','../../../private']:
            with self.assertRaises(ValueError):
                parse_expansion_west(html.replace('N082111171680',value), source, source['url'])

    def test_unknown_source_or_replaced_configuration_is_rejected(self):
        source = SOURCES['gz_hr_recruit']
        for edited in [dict(source,id='unreviewed'),dict(source,url='https://example.test/')]:
            with self.assertRaises(ValueError):
                parse_expansion_west(directory(), edited, edited['url'])

    def test_bingtuan_static_limit_stays_explicitly_partial(self):
        for id_ in ['bt_exam_civil','bt_exam_recruit']:
            source = SOURCES[id_]
            self.assertFalse(source['history'])
            self.assertEqual(source['max_pages'],10)
            self.assertIn('10页之后',source['history_note'])
            url = source['url'] + 'index_10.shtml'
            rows, nxt = parse_expansion_west(directory(id_,current=10,total=18),source,url)
            self.assertEqual(len(rows),1)
            self.assertIsNone(nxt)

    def test_ningxia_official_provenance_and_uncertain_archives_are_explicit(self):
        for id_ in ['nx_exam_civil','nx_exam_recruit']:
            self.assertEqual(SOURCES[id_]['provenance'],'https://hrss.nx.gov.cn/')
        for id_ in ['gz_hr_recruit','xz_hr_notices','sn_hr_notices']:
            self.assertFalse(SOURCES[id_]['history'])
            self.assertTrue(SOURCES[id_]['history_note'])

    def test_mixed_xinjiang_columns_are_selected_for_each_known_category(self):
        from wuzhong.notices import compatible, validate_filters
        for sid in ['xj_hr_civil','xj_hr_recruit']:
            for kind in ['省考','国考','事业单位']:
                filters=validate_filters(dict(year_from=2026,region='新疆',area_scope='province',kind=kind))
                self.assertTrue(compatible(SOURCES[sid],filters))

    def test_valid_article_with_invalid_title_is_not_silently_dropped(self):
        s=SOURCES['yn_gov_civil']
        for title in ['', '长'*501]:
            html=directory('yn_gov_civil',total=1,title=title).replace('缩略标题','')
            with self.assertRaisesRegex(ValueError,'标题'):
                parse_expansion_west(html,s,s['url'])


if __name__ == '__main__':
    unittest.main()
