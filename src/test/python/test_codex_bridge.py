"""App Server protocol contract tests with an executable, offline CLI fixture."""
import json
from pathlib import Path
import tempfile
import types
import unittest

RESOURCE = Path(__file__).parents[2] / 'main/resources/studio'
remote = types.ModuleType('codex_remote')
exec((RESOURCE / 'remote.py').read_text().replace('# CODEX_BRIDGE', (RESOURCE / 'codex_bridge.py').read_text())
     .replace('# ASSISTANT_MCP', 'ASSISTANT_MCP_PROGRAM = ' + repr((RESOURCE / 'assistant_mcp.py').read_text())), remote.__dict__)

FIXTURE = '''#!/usr/bin/python3
import json,sys,os
def send(**v): print(json.dumps(v),flush=True)
thread=dict(id='thread-1',cwd=os.getcwd(),turns=[])
for line in sys.stdin:
 f=json.loads(line);m=f.get('method');p=f.get('params',{});result={}
 if m=='initialize': result={}
 elif m=='mcpServerStatus/list': result={'data':[dict(name='dashboard_assistant',authStatus='unsupported',tools={'current_time':{},'timetables':{}}),dict(name='offline',authStatus='bearerToken',tools={})]}
 elif m=='model/list': result={'data':[dict(model='fixture',displayName='Fixture',isDefault=True,defaultReasoningEffort='medium',supportedReasoningEfforts=[dict(reasoningEffort='medium',description='Balanced')])]}
 elif m=='thread/start' or m=='thread/resume':
  if os.environ.get('DASHBOARD_ASSISTANT_COOKIE'):
   assert p['sandbox']=='danger-full-access'
   assert p['approvalPolicy']=='never'
   assert 'dashboard_assistant MCP' in p['developerInstructions']
   assert os.environ['DASHBOARD_ASSISTANT_COOKIE'] not in json.dumps(p)+str(sys.argv)
   assert 'mcp_servers.dashboard_assistant.env_vars=' in ' '.join(sys.argv)
  result={'thread':thread,'model':'fixture'}
 elif m=='thread/read':
  if p['threadId']=='foreign': thread['cwd']='/other-project'
  result={'thread':thread}
 elif m=='turn/start':
  turn=dict(id='turn-1',status='inProgress',items=[])
  send(id=f['id'],result={'turn':turn})
  send(method='turn/started',params={'turn':turn})
  send(id=900,method='item/commandExecution/requestApproval',params=dict(threadId=thread['id'],turnId=turn['id'],itemId='cmd',command='echo safe',reason='Run command?'))
  continue
 elif f.get('id')==900 and not m:
  assert f['result']['decision']=='decline'
  item=dict(id='answer',type='agentMessage',text='Request declined safely')
  send(method='item/completed',params={'item':item})
  turn=dict(id='turn-1',status='completed',items=[item]);thread['turns']=[turn]
  send(method='turn/completed',params={'turn':turn})
  continue
 if 'id' in f: send(id=f['id'],result=result)
'''


class CodexBridgeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        cli = self.root / 'codex'; cli.write_text(FIXTURE); cli.chmod(0o755)
        self.old_path = remote.env['PATH']; remote.env['PATH'] = str(self.root) + ':' + self.old_path
        self.events = []
        self.old_emit = remote.emit
        remote.emit = lambda **event: self.events.append(event)

    def tearDown(self):
        remote.env['PATH'] = self.old_path; remote.emit = self.old_emit; self.temp.cleanup()

    def test_dynamic_models(self):
        result = remote.codex_action(self.root, 'codex-models', {})
        self.assertEqual(result['assistant']['models'][0]['id'], 'fixture')
        self.assertEqual(result['assistant']['models'][0]['efforts'][0]['reasoningEffort'], 'medium')

    def test_mcp_availability_is_independent_of_oauth_support(self):
        servers = remote.codex_action(self.root, 'codex-connections', {})['assistant']['connections']
        self.assertEqual(servers[0], dict(name='dashboard_assistant', status='available', toolCount=2, authStatus='unsupported'))
        self.assertEqual(servers[1]['status'], 'noTools')

    def test_new_session_is_draft_until_first_turn(self):
        result = remote.codex_action(self.root, 'codex-thread-new', {})
        self.assertEqual(result['assistant']['thread']['id'], '')

    def test_turn_approval_and_authoritative_history(self):
        def receive(**value):
            self.events.append(value)
            event = value.get('assistant', {})
            if event.get('kind') == 'interaction':
                remote.controls.put(dict(type='approval', requestId=event['interaction']['id'], decision='decline'))
        remote.emit = receive
        result = remote.codex_action(self.root, 'codex-run', dict(prompt='test', model='fixture'))
        self.assertEqual(result['assistant']['status'], 'completed')
        self.assertEqual(result['assistant']['thread']['turns'][0]['items'][0]['text'], 'Request declined safely')
        self.assertIn('answered', [e['assistant']['kind'] for e in self.events])

    def test_foreign_thread_and_file_context_rejected(self):
        with self.assertRaises(remote.Failure) as error:
            remote.codex_action(self.root, 'codex-thread-read', dict(threadId='foreign'))
        self.assertEqual(error.exception.status, 403)
        with self.assertRaises(remote.Failure):
            remote.codex_input(self.root, dict(prompt='test', context=[dict(kind='file', path='/etc/passwd')]))

    def test_home_assistant_keeps_credentials_out_of_config_and_forces_full_access(self):
        def receive(**value):
            self.events.append(value)
            event = value.get('assistant', {})
            if event.get('kind') == 'interaction':
                remote.controls.put(dict(type='approval', requestId=event['interaction']['id'], decision='decline'))
        remote.emit = receive
        result = remote.codex_action(self.root, 'codex-run', dict(prompt='today', mode='read-only'),
                                    dict(baseUrl='http://127.0.0.1:8080/api/v1', sessionCookie='JSESSIONID=offline-session'))
        self.assertEqual(result['assistant']['status'], 'completed')
        self.assertNotIn('offline-session', json.dumps(result))
        self.assertEqual(remote.clean('offline-session'), '[redacted]')

    def test_mcp_results_are_projected_without_credentials(self):
        remote.secrets_to_redact.add('fixture-secret')
        item = remote.assistant_item(dict(id='tool', type='mcpToolCall', server='dashboard_assistant', tool='calendar_events',
                                         result=dict(content=[dict(type='text', text='Event fixture-secret')])))
        self.assertIn('calendar_events', item['text'])
        self.assertNotIn('fixture-secret', item['text'])

    def test_command_started_with_null_output_does_not_abort_turn(self):
        item = remote.assistant_item(dict(id='command-started', type='commandExecution', status='inProgress',
                                         command='pwd', aggregatedOutput=None, exitCode=None, durationMs=None))
        self.assertEqual(item['command'], 'pwd')
        self.assertEqual(item['output'], '')
        self.assertEqual(item['status'], 'inProgress')
        completed = remote.assistant_item(dict(id='command-started', type='commandExecution', status='completed',
                                              command='pwd', aggregatedOutput='/workspace/dashboard\n'))
        self.assertEqual(completed['output'], '/workspace/dashboard\n')

    def test_account_snapshots_match_the_dashboard_rate_limit_list(self):
        limits = remote.account_rate_limits(dict(rateLimitsByLimitId={'model': dict(limitName='Model', primary=dict(usedPercent=15.5, resetsAt=100, windowDurationMins=300))}))
        self.assertEqual(limits, [dict(id='model:primary', name='Model · 기본 한도', usedPercent=15.5, resetsAt=100, windowDurationMins=300)])
        self.assertEqual(remote.account_rate_limits({}), [])

    def test_reset_duration_can_be_missing_and_notification_uses_safe_projection(self):
        snapshot = dict(limitId='codex', primary=dict(usedPercent=0, resetsAt=None), secondary=None)
        limits = remote.account_rate_limits(dict(rateLimits=snapshot))
        self.assertEqual(limits[0]['usedPercent'], 0)
        self.assertIsNone(limits[0]['windowDurationMins'])
        self.assertIsNone(limits[0]['resetsAt'])
        bridge = remote.CodexBridge(self.root)
        try:
            bridge.frames.put(dict(method='account/rateLimits/updated', params=dict(rateLimits=snapshot)))
            bridge.pump()
            self.assertEqual(self.events[-1]['assistant']['rateLimits'], limits)
            self.assertEqual(limits[0]['id'], 'codex:primary')
        finally:
            bridge.close()

    def test_only_reasoning_summary_is_projected(self):
        item = remote.assistant_item(dict(id='r', type='reasoning', summary=['Progress'], content=['hidden reasoning']))
        self.assertEqual(item['text'], 'Progress')
        self.assertNotIn('hidden reasoning', json.dumps(item))

    def test_context_snapshot_and_limits(self):
        (self.root / 'main.py').write_text('print(1)')
        inputs = remote.codex_input(self.root, dict(prompt='test', context=[dict(kind='file', path='main.py')]))
        self.assertIn('print(1)', inputs[1]['text'])
        with self.assertRaises(remote.Failure):
            remote.codex_input(self.root, dict(prompt='test', context=[dict(kind='image', dataUrl='https://remote/image.png')]))


if __name__ == '__main__': unittest.main()
