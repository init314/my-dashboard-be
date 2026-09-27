"""Exercises the MCP wire protocol and loopback credential boundary without external services."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).parents[2] / 'main/resources/studio/assistant_mcp.py'
spec = importlib.util.spec_from_file_location('assistant_mcp', SCRIPT)
mcp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcp)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *unused): pass

    def do_GET(self):
        self.server.requests.append((self.path, self.headers.get('Cookie')))
        if self.path in ('/', '/dashboard/'):
            body = b'<html><head><meta name="csrf-token" content="fixture-csrf"><meta name="csrf-header" content="X-CSRF-TOKEN"></head></html>'
            status = 200
        elif self.path.startswith('/api/v1/calendar/events'):
            body = json.dumps([dict(title='Fixture event')]).encode()
            status = 200
        elif self.path == '/api/v1/cloud/preview?path=%2Freport.txt':
            body = json.dumps(dict(content='Fixture text')).encode()
            status = 200
        else:
            body, status = b'{}', 401
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(body)

    def change(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        self.server.mutations.append(dict(method=self.command, path=self.path, body=body,
                                         headers=dict(self.headers)))
        status = self.server.write_status
        if self.headers.get('X-CSRF-TOKEN') != 'fixture-csrf': status = 403
        self.send_response(status)
        if status == 302: self.send_header('Location', 'http://example.com/never-follow')
        self.end_headers()
        if status != 204: self.wfile.write(json.dumps(dict(ok=True)).encode())

    do_POST = do_PUT = do_PATCH = do_DELETE = change


class AssistantMcpTest(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.requests = []
        self.server.mutations = []
        self.server.write_status = 200
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.base = 'http://127.0.0.1:%d/api/v1' % self.server.server_port
        self.cookie = 'JSESSIONID=offline-fixture'
        self.client = mcp.DashboardClient(self.base, self.cookie)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()

    def test_wire_initialize_list_and_calendar_call(self):
        messages = [dict(jsonrpc='2.0', id=1, method='initialize', params=dict(protocolVersion='2025-03-26')),
                    dict(jsonrpc='2.0', method='notifications/initialized'),
                    dict(jsonrpc='2.0', id=2, method='tools/list'),
                    dict(jsonrpc='2.0', id=3, method='tools/call', params=dict(name='calendar_events', arguments={'from':'2026-09-26','to':'2026-09-27'}))]
        environment = dict(os.environ, DASHBOARD_ASSISTANT_URL=self.base, DASHBOARD_ASSISTANT_COOKIE=self.cookie)
        output = subprocess.run([sys.executable, str(SCRIPT)], input='\n'.join(json.dumps(value) for value in messages) + '\n',
                                text=True, capture_output=True, env=environment, timeout=5)
        self.assertEqual(output.returncode, 0, output.stderr)
        frames = [json.loads(line) for line in output.stdout.splitlines()]
        self.assertEqual([frame['id'] for frame in frames], [1, 2, 3])
        self.assertEqual(frames[0]['result']['protocolVersion'], '2025-03-26')
        tools = frames[1]['result']['tools']
        self.assertEqual(len(tools), 12)
        writes = [tool for tool in tools if not tool['annotations']['readOnlyHint']]
        self.assertEqual([tool['name'] for tool in writes], ['dashboard_request', 'dashboard_upload'])
        self.assertTrue(all(tool['annotations']['destructiveHint'] for tool in writes))
        self.assertIn('Fixture event', frames[2]['result']['content'][0]['text'])
        self.assertNotIn(self.cookie, output.stdout + output.stderr)
        self.assertEqual(self.server.requests[0][1], self.cookie)

    def test_expired_login_returns_safe_tool_error(self):
        result = mcp.dispatch(self.client, dict(id=1, method='tools/call', params=dict(name='timetables')))
        self.assertTrue(result['result']['isError'])
        self.assertIn('로그인이 만료', result['result']['content'][0]['text'])
        self.assertNotIn(self.cookie, json.dumps(result))

    def test_text_and_download_links_use_relative_authenticated_routes(self):
        result = mcp.call_tool(self.client, 'read_file', dict(path='/report.txt'))
        self.assertEqual(result['content'], 'Fixture text')
        self.assertEqual(result['downloadUrl'], '/api/v1/cloud/content?path=%2Freport.txt')
        self.assertTrue(result['untrusted'])
        self.assertNotIn('127.0.0.1', result['downloadUrl'])

    def test_unknown_tools_fields_and_invalid_dates_do_not_make_requests(self):
        for name, arguments in [('delete_file', {'path':'/report.txt'}), ('timetables', {'cookie':'invalid'}),
                                ('calendar_events', {'from':'2026-09-27','to':'2026-09-26'}), ('read_file', {'path':['invalid']})]:
            result = mcp.dispatch(self.client, dict(id=1, method='tools/call', params=dict(name=name, arguments=arguments)))
            self.assertTrue(result['result']['isError'])
        self.assertEqual(self.server.requests, [])

    def test_cookies_can_only_be_sent_to_loopback(self):
        for url in ['http://example.com:80/api/v1', 'https://127.0.0.1:80/api/v1', 'http://127.0.0.1:80/api/v1?redirect=x']:
            with self.assertRaises(mcp.ToolError): mcp.DashboardClient(url, self.cookie)

    def test_json_mutations_use_session_csrf_and_accept_empty_success(self):
        body = dict(title='한글 문서', blocks=[dict(content='첫 줄\n다음 줄', checked=False)], parentId=None)
        for method, status in [('POST', 201), ('PUT', 200), ('PATCH', 200), ('DELETE', 204)]:
            self.server.write_status = status
            result = mcp.call_tool(self.client, 'dashboard_request', dict(method=method, path='/notes/fixture', body=body))
            self.assertEqual(result['status'], status)
            self.assertEqual(result['data'], None if status == 204 else dict(ok=True))
            sent = self.server.mutations[-1]
            self.assertEqual(sent['method'], method)
            self.assertEqual(sent['headers']['Cookie'], self.cookie)
            self.assertEqual(sent['headers']['X-CSRF-TOKEN'], 'fixture-csrf')
            self.assertEqual(json.loads(sent['body']), body)
            self.assertNotIn('fixture-csrf', json.dumps(result))
        self.assertEqual(self.server.requests, [('/', self.cookie)])

    def test_get_query_escaping_does_not_fetch_csrf(self):
        result = mcp.call_tool(self.client, 'dashboard_request', dict(method='GET', path='/calendar/events',
                               query=dict(query='a & b/한글', overwrite=False, ids=['a','b'])))
        self.assertEqual(result['status'], 200)
        self.assertEqual(self.server.requests, [('/api/v1/calendar/events?query=a+%26+b%2F%ED%95%9C%EA%B8%80&overwrite=false&ids=a&ids=b', self.cookie)])

    def test_context_path_is_preserved_for_csrf_and_mutations(self):
        client = mcp.DashboardClient(self.base.replace('/api/v1', '/dashboard/api/v1'), self.cookie)
        client.request('POST', '/clips', body=dict(text='fixture'))
        self.assertEqual(self.server.requests, [('/dashboard/', self.cookie)])
        self.assertEqual(self.server.mutations[0]['path'], '/dashboard/api/v1/clips')

    def test_invalid_mutation_routes_types_and_methods_make_no_requests(self):
        for path in ['https://example.com', '//example.com', '/../logout', '/%25252e%25252e/logout',
                     '/notes?x=1', '/notes#x', '/notes%3fx=1', '/notes\\x', '/%0d%0aHost:evil']:
            with self.assertRaises(mcp.ToolError): self.client.request('POST', path)
        for extra in [dict(method='TRACE'), dict(body='raw'), dict(query=[]), dict(query=dict(nested={})),
                      dict(query=dict(value=None)), dict(query=dict(value=float('nan'))), dict(cookie='leak')]:
            arguments = dict(method='POST', path='/notes')
            arguments.update(extra)
            with self.assertRaises(mcp.ToolError): mcp.call_tool(self.client, 'dashboard_request', arguments)
        with self.assertRaises(mcp.ToolError): self.client.request('GET', '/notes', body={})
        self.assertEqual(self.server.requests, [])
        self.assertEqual(self.server.mutations, [])

    def test_write_failures_and_redirects_are_not_retried(self):
        for status in (302, 401, 403, 409, 500):
            self.server.write_status = status
            result = mcp.dispatch(self.client, dict(id=1, method='tools/call', params=dict(name='dashboard_request',
                                                  arguments=dict(method='POST', path='/notes', body={}))))
            self.assertTrue(result['result']['isError'])
            self.assertNotIn(self.cookie, json.dumps(result))
        self.assertEqual(len(self.server.mutations), 5)
        self.assertEqual(self.server.requests, [('/', self.cookie)])

    def test_missing_csrf_never_sends_mutation(self):
        with patch.object(self.client, 'exchange', return_value=(200, dict(content='<html>login</html>'))):
            with self.assertRaises(mcp.ToolError): self.client.request('POST', '/notes')
        self.assertEqual(self.server.mutations, [])

    def test_upload_streams_binary_multipart_with_session_csrf(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'fixture.bin'
            content = b'\0\xff\r\n' * 32768
            source.write_bytes(content)
            result = mcp.call_tool(self.client, 'dashboard_upload', dict(path='/cloud/uploads', filePath=str(source),
                                                                       query=dict(path='/fixture', overwrite=False)))
        self.assertEqual(result['status'], 200)
        sent = self.server.mutations[0]
        self.assertEqual(sent['path'], '/api/v1/cloud/uploads?path=%2Ffixture&overwrite=false')
        self.assertEqual(sent['headers']['Cookie'], self.cookie)
        self.assertEqual(sent['headers']['X-CSRF-TOKEN'], 'fixture-csrf')
        self.assertEqual(int(sent['headers']['Content-Length']), len(sent['body']))
        self.assertNotIn('Transfer-Encoding', sent['headers'])
        self.assertIn(b'name="file"; filename="fixture.bin"', sent['body'])
        self.assertIn(content, sent['body'])
        self.assertNotIn(str(source), json.dumps(result))

    def test_upload_requires_existing_absolute_file(self):
        with self.assertRaises(mcp.ToolError): self.client.upload('/cloud/uploads', 'relative.txt')
        self.assertEqual(self.server.requests, [])
        self.assertEqual(self.server.mutations, [])

    def test_context_reads_only_contract_catalog_and_reports_missing_mount(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(mcp, 'SOURCE_ROOT', Path(directory)):
            root = Path(directory)
            (root / 'docs/api').mkdir(parents=True)
            (root / 'docs/api/endpoints.md').write_text('POST /api/v1/notes', encoding='utf-8')
            (root / '.env').write_text('SECRET=must-not-read', encoding='utf-8')
            result = mcp.call_tool(self.client, 'dashboard_context', {})
            self.assertTrue(result['sourceAvailable'])
            self.assertTrue(result['sourceWritable'])
            self.assertEqual(result['endpoints'], 'POST /api/v1/notes')
            self.assertNotIn('must-not-read', json.dumps(result))
        with patch.object(mcp, 'SOURCE_ROOT', Path(directory)):
            self.assertFalse(mcp.dashboard_context()['sourceAvailable'])
        self.assertEqual(self.server.requests, [])

    def test_web_rejects_private_mixed_addresses_and_unsafe_protocols(self):
        addresses = [(2,1,6,'',('127.0.0.1',80)), (2,1,6,'',('93.184.216.34',80))]
        with patch.object(mcp.socket, 'getaddrinfo', return_value=addresses):
            with self.assertRaises(mcp.ToolError): mcp.public_target('https://example.com')
        for url in ['file:///etc/passwd', 'https://user:password@example.com', 'http://example.com:7088']:
            with self.assertRaises(mcp.ToolError): mcp.public_target(url)

    def test_html_text_excludes_scripts_and_style(self):
        parser = mcp.PageText()
        parser.feed('<title>Title</title><script>secret()</script><style>hidden</style><p>Visible</p>')
        self.assertEqual(parser.title, ['Title'])
        self.assertEqual(parser.parts, ['Visible'])

    def test_remote_scan_is_bounded_and_results_keep_download_links(self):
        class FakeClient:
            count = 0
            def get(self, path, query):
                self.count += 1
                return dict(entries=[dict(name='report', path=query['path'].rstrip('/') + '/report', directory=False),
                                     dict(name='folder', path=query['path'].rstrip('/') + '/folder', directory=True)])
            def download_url(self, path, device): return '/api/v1/devices/' + device + '/files/content'
        client = FakeClient()
        result = mcp.find_files(client, dict(deviceId='remote', query='report'))
        self.assertEqual(client.count, 40)
        self.assertTrue(result['truncated'])
        self.assertEqual(len(result['entries']), 40)
        self.assertTrue(all('downloadUrl' in entry for entry in result['entries']))


if __name__ == '__main__': unittest.main()
