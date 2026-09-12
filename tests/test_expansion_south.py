import unittest
from wuzhong.expansion_south import EXPANSION_SOUTH_SOURCES, parse_expansion_south

SOURCES={s['id']:s for s in EXPANSION_SOUTH_SOURCES}


def fixture(source, page=1, last=2, title='2025年事业单位拟聘公示', stamp='2026-02-28', link=None):
    base=source['url']; current=base+('index.html' if page==1 else f'index_{page}.html')
    last_url=base+('index.html' if last==1 else f'index_{last}.html')
    link=link or base+'content/post_123.html'
    return (f'<ul><li><a href="{link}" title="{title}">{title}</a><span class="time">{stamp}</span></li></ul>'
            f'<a class="current" href="{current}">{page}</a><a class="last" href="{last_url}">最后一页</a>'
            +(f'<a class="next" href="{base}index_{page+1}.html">下一页</a>' if page<last else ''))


class SouthTests(unittest.TestCase):
    def test_metadata_fields_dates_and_terminal(self):
        s=SOURCES['gdzz_civil']; rows,nxt=parse_expansion_south(fixture(s),s,s['url'])
        self.assertEqual(len(rows),1);r=rows[0]
        self.assertEqual((r['published'],r['exam_year'],r['kind'],r['stage']),('2026-02-28',2025,'事业单位','录聘公示'))
        self.assertEqual(set(r),{'id','source_id','source','owner','title','url','published','exam_year','kind','region','stage'})
        self.assertEqual(nxt,s['url']+'index_2.html')
        self.assertIsNone(parse_expansion_south(fixture(s,2),s,nxt)[1])

    def test_wrong_page_missing_next_and_unsafe_paths_fail(self):
        s=SOURCES['gdzz_civil']; html=fixture(s)
        for h,u in [(html,s['url']+'index_2.html'),(html.replace('class="next"','class="lost"'),s['url']),
                    (html,s['url']+'index_1.html'),(html,'https://example.org/index.html'),
                    (html,s['url']+'index.html?url=elsewhere')]:
            with self.subTest(u=u),self.assertRaises(ValueError):parse_expansion_south(h,s,u)

    def test_short_and_markup_titles_missing_dates_and_external_exclusion(self):
        s=SOURCES['dongguan_recruitment'];html=fixture(s,title='特别提醒',stamp='',link=s['url'].replace('https:','http:')+'bzwryzp/content/post_1.html')
        rows,_=parse_expansion_south(html,s,s['url']);self.assertIsNone(rows[0]['published']);self.assertIsNone(rows[0]['exam_year'])
        self.assertTrue(rows[0]['url'].startswith('https:'))
        rows,_=parse_expansion_south(fixture(s,link='https://other.example/content/post_1.html'),s,s['url'])
        self.assertEqual(rows,[])
        rows,_=parse_expansion_south(fixture(s,title='2026年&lt;br/&gt;拟聘公示',stamp='2026-02-30'),s,s['url'])
        self.assertNotIn('<br',rows[0]['title']);self.assertIsNone(rows[0]['published'])

    def test_empty_or_duplicate_directory_does_not_claim_completion(self):
        s=SOURCES['foshan_public'];html=fixture(s)
        for h in ['<html>访问校验</html>',html.replace('post_123.html','list.xlsx'),html.replace('</ul>',html.split('</ul>')[0]+'</ul>')]:
            with self.subTest(h=h[:40]),self.assertRaises(ValueError):parse_expansion_south(h,s,s['url'])

    def test_moe_preserves_current_window_and_counts(self):
        s=SOURCES['moe_civil'];html='<script>var recordCount=1;var pageSize=20;var currentPage=1;</script><ul><li><a href="../../tongzhi/202510/t20251015_123.html">2026年公务员招录公告</a><span>2025-10-15</span></li></ul>'
        rows,nxt=parse_expansion_south(html,s,s['url'])
        self.assertEqual((rows[0]['exam_year'],rows[0]['published'],rows[0]['kind']),(2026,'2025-10-15','国考'))
        self.assertIsNone(nxt);self.assertFalse(s['history'])
        for h in [html.replace('recordCount=1','recordCount=2'),html.replace('recordCount=1','recordCount=21')]:
            with self.assertRaises(ValueError):parse_expansion_south(h,s,s['url'])

    def test_personnel_public_notice_without_proposed_word_is_classified(self):
        from wuzhong.notices import stage
        self.assertEqual(stage('某事业单位2026年特聘人员公示名单'),'录聘公示')
        self.assertEqual(stage('某事业单位2026年招聘岗位公示'),'招录信息')

    def test_title_date_is_not_a_publication_date(self):
        s=SOURCES['gdzz_civil'];rows,_=parse_expansion_south(fixture(s,title='关于2025-06-07招聘考试的通知',stamp=''),s,s['url'])
        self.assertIsNone(rows[0]['published'])

    def test_dongguan_changed_same_site_paths_fail_even_when_page_has_external_links(self):
        s=SOURCES['dongguan_recruitment']
        with self.assertRaisesRegex(ValueError,'路径发生变化'):
            parse_expansion_south(fixture(s,link='https://dghrss.dg.gov.cn/changed-column/content/post_1.html'),s,s['url'])


if __name__=='__main__':unittest.main()
