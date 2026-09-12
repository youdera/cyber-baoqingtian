import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import urlparse

import requests
from notice_app import create_app
from wuzhong.source_audit import audit, probe
from wuzhong.source_catalog import catalog
from wuzhong.notices import SOURCES


class SourceAuditTests(unittest.TestCase):
    def test_catalog_is_fixed_unique_https_and_separates_candidates(self):
        rows=catalog()
        self.assertEqual(len(rows),76)
        self.assertEqual(len({x['id'] for x in rows}),len(rows))
        self.assertEqual(sum(x['enabled'] for x in rows),18)
        self.assertTrue(all(urlparse(x['url']).scheme=='https' for x in rows))
        for source in rows:
            host=urlparse(source['url']).hostname
            if not host.endswith('.gov.cn'):
                self.assertEqual(host,'www.scpta.com.cn')
                self.assertEqual(source['provenance'],'https://rst.sc.gov.cn/')
            if source.get('listing_url'):
                self.assertEqual(urlparse(source['listing_url']).scheme,'https')
                self.assertEqual(urlparse(source['listing_url']).hostname,host)
        self.assertEqual({s['id'] for s in rows if s['enabled']},{s['id'] for s in SOURCES})

    def test_portal_probe_discovers_navigation_without_following_links(self):
        accessed=[]
        class FakeFetcher:
            def __init__(self, source, cancel):self.session=Mock()
            def get(self,url):
                accessed.append(url)
                return '''<title>模拟官方门户</title><a href="/jobs/">事业单位公开招聘</a>
                <a href="/private.xlsx">拟聘公示</a><a href="https://example.com/jobs/">招聘公告</a>
                <a href="/article/">2026年招聘公告</a><table><td>虚构个人字段不得保存</td></table>'''
        source=dict(id='test',name='模拟',url='https://www.stats.gov.cn/',enabled=False,portal=True)
        result=probe(source,threading.Event(),FakeFetcher)
        self.assertEqual(accessed,[source['url']])
        self.assertEqual(result['discovered'],[dict(title='事业单位公开招聘',url='https://www.stats.gov.cn/jobs/')])
        self.assertNotIn('个人字段',json.dumps(result,ensure_ascii=False))

    def test_portals_show_partial_connections_without_becoming_collectors(self):
        rows={s['id']:s for s in catalog()}
        shanxi=rows['portal_3fd1bb7e59']
        self.assertFalse(shanxi['enabled'])
        self.assertEqual(set(shanxi['linked_source_ids']),{'shanxi_gwy','shanxi_sydw','shanxi_sydw_jobs'})
        self.assertEqual(len(rows['portal_d1bc4e04bf']['linked_source_ids']),6)
        self.assertEqual(rows['portal_b3edb90a87']['linked_source_ids'],['yangjiang_civil'])

    def test_probe_preserves_tls_failure(self):
        class FailingFetcher:
            def __init__(self,source,cancel):self.session=Mock()
            def get(self,url):raise requests.exceptions.SSLError('fixture')
        row=probe(catalog()[0],threading.Event(),FailingFetcher)
        self.assertEqual(row['status'],'failed')
        self.assertIn('TLS',row['reason'])

    def test_audit_appends_history_and_reads_handoff(self):
        source=catalog()[0]
        sample=dict(id=source['id'],name=source['name'],status='failed',recognized=0,reason='模拟失败')
        with tempfile.TemporaryDirectory() as root:
            Path(root,'HANDOFF.md').write_text('模拟交接',encoding='utf-8')
            with patch('wuzhong.source_audit.catalog',return_value=[source]),patch('wuzhong.source_audit.probe',return_value=sample):
                audit(root,root);audit(root,root)
            self.assertEqual(len(Path(root,'source-audit-history.jsonl').read_text(encoding='utf-8').splitlines()),2)
            result=json.loads(Path(root,'source-audit.json').read_text(encoding='utf-8'))
            self.assertEqual(result['results'][0]['status'],'failed')
            self.assertTrue(result['handoff_digest'])

    def test_api_auth_and_shared_collection_lock(self):
        with tempfile.TemporaryDirectory() as root:
            app=create_app(root);client=app.test_client();state=client.get('/api/notices/state').json
            self.assertEqual(len(state['catalog']),76)
            self.assertEqual(client.post('/api/notices/source-audit').status_code,403)
            engine=app.extensions['engine'];engine.lock.acquire()
            try:self.assertEqual(client.post('/api/notices/source-audit',headers={'X-Local-Token':state['token']}).status_code,409)
            finally:engine.lock.release()


if __name__=='__main__':unittest.main()
