"""Narrow TLS compatibility and readable failure categories."""
import ssl

import requests
from requests.adapters import HTTPAdapter


class P256Adapter(HTTPAdapter):
    """Use standard P-256 without relaxing certificate or TLS validation."""
    @staticmethod
    def _context():
        context = ssl.create_default_context()
        context.set_ecdh_curve('prime256v1')
        return context

    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_context'] = self._context()
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        # Target TLS uses the same verified context through explicit proxies.
        # HTTPS proxy TLS itself keeps the library's normal validation.
        proxy_kwargs['ssl_context'] = self._context()
        return super().proxy_manager_for(proxy, **proxy_kwargs)


def failure_reason(error, phase='directory'):
    prefix = 'robots规则请求：' if phase == 'robots' else '公告目录请求：'
    if isinstance(error, requests.exceptions.SSLError):
        message = str(error)
        labels = {
            'CERTIFICATE_VERIFY_FAILED': '证书验证失败',
            'BAD_ECPOINT': 'TLS曲线协商失败（BAD_ECPOINT）',
            'UNSAFE_LEGACY_RENEGOTIATION_DISABLED': '网站使用客户端不接受的旧式TLS重协商',
            'SSLV3_ALERT_HANDSHAKE_FAILURE': 'TLS握手被对端拒绝',
            'TLSV1_UNRECOGNIZED_NAME': 'TLS主机名协商被对端拒绝',
            'UNEXPECTED_EOF_WHILE_READING': 'TLS连接被对端提前关闭',
        }
        reason = next((text for key,text in labels.items() if key in message), 'TLS验证或握手失败')
        return prefix+reason+'；证书验证保持开启。'
    if isinstance(error, requests.Timeout): return prefix+'连接或读取超时；不等于栏目没有公告。'
    if isinstance(error, requests.HTTPError):
        code = error.response.status_code if error.response is not None else '未知'
        return prefix+f'HTTP {code}；本次未完成读取。'
    if isinstance(error, requests.ConnectionError): return prefix+'连接失败或远端断开；原因尚未确定。'
    if isinstance(error, ValueError): return prefix+str(error)
    return prefix+'读取未完成，请检查运行环境。'
