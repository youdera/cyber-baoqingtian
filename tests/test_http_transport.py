import ssl
import threading
import unittest
from unittest.mock import MagicMock, patch

import requests

from wuzhong.http_transport import P256Adapter, failure_reason
from wuzhong.notices import Fetcher, Stopped


class TransportTests(unittest.TestCase):
    def test_curve_adapter_keeps_certificate_hostname_and_protocol_validation(self):
        adapter=P256Adapter()
        context=adapter.poolmanager.connection_pool_kw['ssl_context']
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertGreaterEqual(context.minimum_version,ssl.TLSVersion.TLSv1_2)
        self.assertEqual(context.maximum_version,ssl.TLSVersion.MAXIMUM_SUPPORTED)
        adapter.close()

    def test_explicit_proxy_target_uses_the_verified_compatibility_context(self):
        adapter=P256Adapter();manager=adapter.proxy_manager_for('http://proxy.example:8080')
        context=manager.connection_pool_kw['ssl_context']
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
        self.assertGreaterEqual(context.minimum_version,ssl.TLSVersion.TLSv1_2)
        adapter.close()

    def reader(self):
        f=Fetcher({'url':'https://www.stats.gov.cn/'},threading.Event())
        f.cancel=MagicMock();f.cancel.is_set.return_value=False;f.cancel.wait.return_value=False
        return f

    def response(self,code=404):
        r=MagicMock();r.__enter__.return_value=r;r.is_redirect=False;r.status_code=code
        return r

    @patch('wuzhong.notices.socket.getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',443))])
    def test_bad_ecpoint_uses_one_compatible_retry(self,dns):
        f=self.reader()
        with patch.object(f.session,'get',side_effect=[requests.exceptions.SSLError('BAD_ECPOINT'),self.response()]) as get,patch.object(f.session,'mount') as mount:
            self.assertEqual(f.raw('https://www.stats.gov.cn/robots.txt'),('',404))
            self.assertEqual(get.call_count,2);mount.assert_called_once()
            self.assertEqual(mount.call_args.args[0],'https://www.stats.gov.cn/')
            self.assertEqual(f.transport_mode,'p256_compat')
            for call in get.call_args_list:
                self.assertFalse(call.kwargs['allow_redirects'])
                self.assertNotIn('verify',call.kwargs)
        f.session.close()

    @patch('wuzhong.notices.socket.getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',443))])
    def test_certificate_and_other_tls_failures_are_not_retried_with_different_settings(self,dns):
        for reason in ['CERTIFICATE_VERIFY_FAILED','UNSAFE_LEGACY_RENEGOTIATION_DISABLED','SSLV3_ALERT_HANDSHAKE_FAILURE']:
            f=self.reader()
            with patch.object(f.session,'get',side_effect=requests.exceptions.SSLError(reason)) as get,patch.object(f.session,'mount') as mount:
                with self.assertRaises(requests.exceptions.SSLError): f.raw('https://www.stats.gov.cn/robots.txt')
                self.assertEqual(get.call_count,1);mount.assert_not_called()
            f.session.close()

    @patch('wuzhong.notices.socket.getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',443))])
    def test_compatibility_retry_is_bounded_and_cancellable(self,dns):
        f=self.reader()
        with patch.object(f.session,'get',side_effect=requests.exceptions.SSLError('BAD_ECPOINT')) as get:
            with self.assertRaises(requests.exceptions.SSLError): f.raw('https://www.stats.gov.cn/robots.txt')
            self.assertEqual(get.call_count,2)
        f.session.close()
        f=self.reader();f.cancel.wait.return_value=True
        with patch.object(f.session,'get',side_effect=requests.exceptions.SSLError('BAD_ECPOINT')) as get:
            with self.assertRaises(Stopped):f.raw('https://www.stats.gov.cn/robots.txt')
            self.assertEqual(get.call_count,1)
        f.session.close()

    def test_robots_denial_still_stops_before_directory_request(self):
        f=self.reader()
        with patch.object(f,'raw',return_value=('User-agent: *\nDisallow: /',200)) as raw:
            with self.assertRaisesRegex(ValueError,'不允许'):f.get('https://www.stats.gov.cn/jobs/')
            raw.assert_called_once_with('https://www.stats.gov.cn/robots.txt')
        f.session.close()

    def test_errors_identify_request_phase_without_claiming_site_is_empty(self):
        response=requests.Response();response.status_code=403
        self.assertIn('robots规则请求：HTTP 403',failure_reason(requests.HTTPError(response=response),'robots'))
        self.assertIn('旧式TLS重协商',failure_reason(requests.exceptions.SSLError('UNSAFE_LEGACY_RENEGOTIATION_DISABLED')))
        self.assertIn('公告目录请求：连接或读取超时',failure_reason(requests.Timeout()))
        self.assertIn('原因尚未确定',failure_reason(requests.ConnectionError()))


if __name__=='__main__':unittest.main()
