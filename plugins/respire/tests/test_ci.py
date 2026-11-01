#!/usr/bin/env python3
"""Portable, isolated hook tests. No real engine discovery or user data access."""
import importlib.util
import json
import os
import re
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from unittest import mock
import unittest

ROOT = Path(__file__).resolve().parents[1]
SECRET = 'sk-' + 'q7xkwm2vbnr8tzc41p9e'


def allowed_process(executable, argv, expected_argv, windows):
    """Match only the complete expected invocation, including all arguments.

    CPython's Windows audit event receives executable=None and the already
    list2cmdline-encoded string; POSIX receives an executable and an argv list.
    """
    if executable != expected_argv[0] and not (windows and executable is None):
        return False
    if isinstance(argv, (list, tuple)):
        return list(argv) == expected_argv
    return windows and isinstance(argv, str) and argv == subprocess.list2cmdline(expected_argv)


# Run the unmodified hook with a subprocess allowlist. A failure cannot silently
# fall through to a real rsrs executable, even on machines where one is installed.
# TEST_EXPECTED_ARGV is an ORDERED SEQUENCE of argv lists: every subprocess must
# match the next expected invocation exactly (store now legitimately chains
# remember -> show read-back / remember -> list verification).
LAUNCHER = r'''
import json, os, pathlib, runpy, sys
case = pathlib.Path(os.environ['RESPITE_CONFIG']).resolve().parent
expected = os.environ['TEST_ENGINE']
expected_argv = json.loads(os.environ['TEST_EXPECTED_ARGV'])
assert isinstance(expected_argv, list)  # 空序列=零引擎调用（R3 终案：Stop 不查引擎，任何 subprocess 即拒绝）
for argv in expected_argv:
    assert isinstance(argv, list) and argv[0] == expected
config = json.loads(pathlib.Path(os.environ['RESPITE_CONFIG']).read_text(encoding="utf-8"))
assert config['rsrs'] == expected and os.access(expected, os.X_OK)
sys.path.insert(0, str(pathlib.Path(os.environ['TEST_HOOK']).parents[1] / 'tests'))
from test_ci import allowed_process
state = {'next': 0}
def audit(event, args):
    if event == 'subprocess.Popen':
        executable, argv, cwd, env = args
        index = state['next']
        if index >= len(expected_argv) or not allowed_process(executable, argv, expected_argv[index], os.name == 'nt'):
            pathlib.Path(os.environ['TEST_DENIED']).write_text('unexpected subprocess')
            raise SystemExit(91)
        state['next'] += 1
    elif event.startswith('socket.') or event in ('os.system', 'os.posix_spawn', 'os.exec'):
        pathlib.Path(os.environ['TEST_DENIED']).write_text('unexpected external action')
        raise SystemExit(92)
sys.addaudithook(audit)
sys.argv = [os.environ['TEST_HOOK'], os.environ['TEST_EVENT']]
runpy.run_path(sys.argv[0], run_name='__main__')
'''


def stop_denied(raw: str) -> bool:
    """WorkBuddy Stop 阻塞契约：hookSpecificOutput.permissionDecision == deny。"""
    doc = json.loads(raw)
    return doc.get('hookSpecificOutput', {}).get('permissionDecision') == 'deny'


class CredentialGuard(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='workbuddy-guard-')
        self.addCleanup(self.temp.cleanup)
        self.case = Path(self.temp.name)
        self.spy = self.case / 'spy.py'
        self.calls = self.case / 'calls.jsonl'
        self.log = self.case / 'hook.log'
        self.denied = self.case / 'denied'
        self.spy.write_text(r'''import json, os, sys, datetime, time
with open(os.environ['TEST_CALLS'], 'a', encoding='utf-8') as f:
    f.write(json.dumps(sys.argv[1:]) + '\n')
sub = sys.argv[1]
mode = os.environ.get('STUB_MODE', 'ok')
list_mode = os.environ.get('STUB_LIST', mode)
if mode == 'dead': sys.exit(7)
if mode == 'malformed': print('not json'); sys.exit(0)
if mode == 'hang': time.sleep(30)
if sub == 'recall':
    print(json.dumps({'status':'ok','details':[{'id':'cccccccccccccccc','title':'spy','score':0.9}]}))
elif sub == 'remember':
    if mode == 'warn':
        print(json.dumps({'status':'warn','summary':{'action':'created','id':'eeeeeeeeeeeeeeee'},
                          'errors':['parent (cause) cannot be resolved; stored independently']}))
        sys.exit(2)
    if mode == 'pending':
        print(json.dumps({'status':'pending','summary':{'state':'candidates','written':False},
                          'items':[{'name':'aaaabbbb','status':'pending',
                                    'value':'similarity=88% title=stub candidate',
                                    'action':'merge or attach'}],
                          'actions':['rsrs remember "<combined content>" --merge-ids "aaaabbbb"',
                                     'rsrs remember "<content>" --parent <candidate id>',
                                     'rsrs remember "<content>" --force to write as new entry']}))
        sys.exit(2)
    if mode == 'silent': sys.exit(0)
    if mode == 'ok_noid': print(json.dumps({'status':'ok','summary':{'action':'created'}})); sys.exit(0)
    if mode == 'ok_junkid': print(json.dumps({'status':'ok','summary':{'id':'zz!!not-hex'}})); sys.exit(0)
    # R3#2 反例：数字 id（JSON number，不得 str() 强转）与宽松 hex-连字符——都不是有效 id
    if mode == 'ok_numid': print(json.dumps({'status':'ok','summary':{'id':12345678}})); sys.exit(0)
    if mode == 'ok_dashid': print(json.dumps({'status':'ok','summary':{'id':'a-------'}})); sys.exit(0)
    if mode == 'bad_summary': print(json.dumps({'status':'ok','summary':'boom'})); sys.exit(0)
    if mode == 'skip_status': print(json.dumps({'status':'skip','summary':{}})); sys.exit(0)
    if mode == 'slow_garbage': time.sleep(2.5); print('garbage not json'); sys.exit(0)
    print(json.dumps({'status':'ok','summary':{'action':'created','id':'dddddddddddddddd'}}))
elif sub == 'show':
    if mode == 'show_fail':
        print(json.dumps({'status':'fail','errors':['not found']}))
        sys.exit(2)
    # 复审 R2#2 反例：ok 信封 + details 非 dict（数组/字符串）——readback 须降级 unavailable，
    # 不得抛 AttributeError 让主入口 fail-open 兜成空输出、吞掉已写回执
    if mode == 'show_badetails':
        print(json.dumps({'status':'ok','summary':{'id':sys.argv[2],'title':'stub'},'details':[{}]}))
        sys.exit(0)
    if mode == 'show_strdetails':
        print(json.dumps({'status':'ok','summary':{'id':sys.argv[2],'title':'stub'},'details':'str'}))
        sys.exit(0)
    title, content = 'stub', 'stub'
    try:
        for line in open(os.environ['TEST_CALLS'], encoding='utf-8').read().splitlines():
            call = json.loads(line)
            if call and call[0] == 'remember':
                content, title = call[1], call[3]
    except Exception:
        pass
    if mode == 'show_mismatch':
        title = title + ' (drifted)'
    if mode == 'show_wrongid':
        print(json.dumps({'status':'ok','summary':{'id':'99999999-9999-4999-8999-999999999999','title':title},
                          'details':{'entry':{'id':'99999999-9999-4999-8999-999999999999','title':title,'content':content}}}))
        sys.exit(0)
    # R3#2 反例：summary.id 正确但 entry.id='DIFFERENT'（复审点名的回读伪装路径）→ mismatch
    if mode == 'show_entrydiff':
        print(json.dumps({'status':'ok','summary':{'id':sys.argv[2],'title':title},
                          'details':{'entry':{'id':'DIFFERENT','title':title,'content':content}}}))
        sys.exit(0)
    # R3#2 反例：entry.id 缺失（三方 id 不齐）→ mismatch，不得 verified
    if mode == 'show_noentryid':
        print(json.dumps({'status':'ok','summary':{'id':sys.argv[2],'title':title},
                          'details':{'entry':{'title':title,'content':content}}}))
        sys.exit(0)
    # R3#2 反例：content 为数字 42（输入正文是字符串 "12345678"）——42 ≠ "42"，不强转匹配
    if mode == 'show_numcontent':
        print(json.dumps({'status':'ok','summary':{'id':sys.argv[2],'title':title},
                          'details':{'entry':{'id':sys.argv[2],'title':title,'content':42}}}))
        sys.exit(0)
    if mode == 'show_tail' and content:
        content = content[:40] + 'TAMPERED-TAIL'
    print(json.dumps({'status':'ok','summary':{'id':sys.argv[2],'title':title},
                      'details':{'entry':{'id':sys.argv[2],'title':title,'content':content}}}))
elif sub == 'status':
    print(json.dumps({'status':'ok','summary':{'session':{'has_token':True,'user':'stub'},'local_total':42}}))
elif sub == 'list':
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat() if list_mode == 'recent' else '2020-01-01T00:00:00Z'
    if list_mode == 'list_schema':
        print(json.dumps({'status':'ok','details':{'broken':True}}))
    elif list_mode == 'list_notimes':
        print(json.dumps({'status':'ok','details':[{'id':'record','no_dates':True}]}))
    else:
        print(json.dumps({'status':'fail'} if list_mode == 'failed' else {'status':'ok','details':[{'id':'record','updated_at':ts}]}))
else: sys.exit(1)
''', encoding="utf-8")
        if os.name == 'nt':
            self.engine = self.case / 'rsrs-spy.cmd'
            self.engine.write_text(f'@echo off\n"{sys.executable}" "{self.spy}" %*\n', encoding="utf-8")
        else:
            self.engine = self.case / 'rsrs-spy'
            self.engine.write_text(f'#!{sys.executable}\n' + self.spy.read_text(encoding="utf-8"), encoding="utf-8")
        self.engine.chmod(0o700)
        self.config = self.case / 'config.json'
        self.config.write_text(json.dumps({'rsrs': str(self.engine), 'session_rules': True}), encoding="utf-8")
        self.launcher = self.case / 'launcher.py'
        self.launcher.write_text(LAUNCHER, encoding="utf-8")
        self.env = {k: v for k, v in os.environ.items()
                    if k.upper() in {'PATH', 'SYSTEMROOT', 'WINDIR', 'PATHEXT', 'TEMP', 'TMP', 'COMSPEC'}}
        self.env.update(RESPITE_CONFIG=str(self.config), RESPITE_LOG=str(self.log),
                        HOME=str(self.case / 'home'), USERPROFILE=str(self.case / 'home'),
                        XDG_CONFIG_HOME=str(self.case / 'config'),
                        XDG_DATA_HOME=str(self.case / 'data'),
                        XDG_CACHE_HOME=str(self.case / 'cache'),
                        RESPITE_NUDGE_STATE=str(self.case / 'nudge'),
                        RESPITE_DATA=str(self.case / 'plugin-data'),
                        RESPITE_TURN_STATE=str(self.case / 'turn-state'),
                        CODEBUDDY_PLUGIN_DATA=str(self.case / 'plugin-data'),
                        TEST_ENGINE=str(self.engine), TEST_CALLS=str(self.calls),
                        TEST_DENIED=str(self.denied), TEST_HOOK=str(ROOT / 'hooks/respire.py'),
                        PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')

    def call(self, prompt='', event='UserPromptSubmit', mode='ok', active=False, every=1,
             session='s1', fast=False, extra_env=None, list_mode=None, skip=None, generation=None):
        config = {'rsrs': str(self.engine), 'session_rules': True, 'store_nudge_every': every}
        if skip is not None:
            config['skip_prefixes'] = skip
        self.config.write_text(json.dumps(config), encoding="utf-8")
        if event == 'Stop':
            args_seq = []  # R3 终案：Stop 完全不查引擎（空序列=零调用，任何 subprocess 即拒绝）
        elif event == 'SessionStart':
            args_seq = [['status','--json']]
        elif prompt.startswith(('记：','store:')):
            content = prompt.replace('：',':',1).split(':',1)[1].strip()
            argv = ['remember',content,'--title',content,'--importance','important','--json']
            if mode in ('ok','show_fail','show_mismatch','show_wrongid','show_tail',
                        'show_badetails','show_strdetails',
                        'show_entrydiff','show_noentryid','show_numcontent'):
                args_seq = [argv, ['show','dddddddddddddddd','--json']]
            elif mode == 'warn':
                args_seq = [argv, ['show','eeeeeeeeeeeeeeee','--json']]
            elif mode in ('silent','ok_noid','ok_junkid','ok_numid','ok_dashid','bad_summary'):  # 未知回执 → 只读核实 list
                args_seq = [argv, ['list','--limit','3','--json']]
            else:                    # pending / hang / skip_status / slow_garbage：不再有后续引擎调用
                args_seq = [argv]
        else:
            args_seq = [['recall',prompt,'--limit','5','--titles','--json']]
        env = dict(self.env, TEST_EXPECTED_ARGV=json.dumps([[str(self.engine)] + a for a in args_seq]),
                   TEST_EVENT=event, STUB_MODE=mode)
        if fast:
            env['RESPITE_TEST_FAST'] = '1'
        if extra_env:
            env.update(extra_env)
        if list_mode is not None:
            env['STUB_LIST'] = list_mode
        payload = {'prompt':prompt,'hook_event_name':event,'stop_hook_active':active}
        if session is not None:
            payload['session_id'] = session
        if generation is not None:
            payload['generation_id'] = generation  # 官方 v2.144.0+ 字段
        result = subprocess.run([sys.executable, str(self.launcher)],
                                input=json.dumps(payload), text=True,
                                encoding='utf-8', capture_output=True, env=env,
                                cwd=self.case, timeout=40)
        self.assertFalse(self.denied.exists(), 'Isolation denied an external action')
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def recorded(self):
        return [json.loads(line) for line in self.calls.read_text(encoding="utf-8").splitlines()] if self.calls.exists() else []

    def positive_control(self):
        before = len(self.recorded())
        output = self.call('rsrs envelope structure recall')
        self.assertEqual(len(self.recorded()), before + 1, 'Live spy must record normal input')
        self.assertEqual(self.recorded()[-1][0], 'recall')
        self.assertIn('auto-recall', output)
        self.assertIn('matched 1 item(s)', output)
        self.assertIn('[0.90] spy', output)
        return output

    def test_normal_input_requires_live_spy(self):
        output = self.positive_control()
        self.assertIn('[0.90] spy', output)

    def test_credential_has_zero_calls_and_no_disclosure(self):
        self.positive_control()
        before = self.recorded()
        output = self.call('api_key = ' + SECRET + ' store this')
        self.assertIn('contains a credential', output)
        self.assertEqual(self.recorded(), before)
        self.assertNotIn(SECRET, output)
        self.assertNotIn(SECRET, self.log.read_text(encoding="utf-8"))
        entries = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]
        skipped = [entry for entry in entries if entry['out'] == 'secret_skip']
        self.assertEqual(len(skipped), 1)
        self.assertNotIn('d', skipped[0])

    def test_store_prefix_credential_is_blocked(self):
        self.positive_control()
        before = self.recorded()
        output = self.call('记：数据库密码 = hunter2u')
        self.assertIn('contains a credential', output)
        self.assertEqual(self.recorded(), before)
        self.assertNotIn('hunter2u', output + self.log.read_text(encoding="utf-8"))

    def test_dead_spy_must_fail_positive_control(self):
        # A valid executable that does not record/return JSON must never count as
        # proof of a zero-call guard. This explicitly exercises that failure.
        if os.name == 'nt':
            self.spy.write_text('import sys\nsys.exit(7)\n', encoding="utf-8")
        else:
            self.engine.write_text(f'#!{sys.executable}\nimport sys\nsys.exit(7)\n', encoding="utf-8")
        with self.assertRaisesRegex(AssertionError, 'Live spy must record normal input'):
            self.positive_control()

    def test_session_uses_only_stub_status(self):
        out = self.call(event='SessionStart')
        self.assertIn('respire memory layer', out)
        self.assertNotIn('not signed in', out)
        self.assertEqual([args[0] for args in self.recorded()], ['status'])

    def test_explicit_store_receipt_comes_from_stub(self):
        out = self.call('store: durable fixture fact')
        self.assertIn('respire · stored', out)
        self.assertIn('retitle dddddddd', out)
        self.assertIn('verified by read-back', out)
        self.assertEqual([args[0] for args in self.recorded()], ['remember', 'show'])

    def test_store_warn_is_written_not_refused(self):
        # CLI 契约：status=warn + 有效 id = 已提交但有警告（parent 未解析等）——
        # 不得误报「未接受」，更不得引导重发（重复写风险）
        out = self.call('store: durable fixture fact', mode='warn')
        self.assertIn('Saved with warnings', out)
        self.assertIn('parent (cause) cannot be resolved', out)
        self.assertIn('retitle eeeeeeee', out)
        self.assertNotIn('did not accept', out)
        self.assertEqual([args[0] for args in self.recorded()], ['remember', 'show'])

    def test_store_pending_relays_candidates_and_actions(self):
        # §7.2：pending 保留候选（含短 id）与引擎建议动作（改＞并＞挂＞存），不得缩成 parent/force 两项
        out = self.call('store: durable fixture fact', mode='pending')
        self.assertIn('store pending', out)
        self.assertIn('nothing was written', out)
        self.assertIn('[aaaabbbb]', out)
        self.assertIn('similarity=88% title=stub candidate', out)
        self.assertIn('merge or attach', out)
        self.assertIn('--merge-ids', out)
        self.assertIn('--force', out)
        self.assertEqual([args[0] for args in self.recorded()], ['remember'])

    def test_store_readback_states(self):
        # R11 写后核验：verified / mismatch / unavailable 三态都如实进回执
        self.assertIn('verified by read-back', self.call('store: durable fixture fact'))
        self.assertIn('DIFFERENT title/content',
                      self.call('store: durable fixture fact', mode='show_mismatch'))
        self.assertIn('Read-back unavailable',
                      self.call('store: durable fixture fact', mode='show_fail'))

    def test_store_unknown_receipt_never_demands_resend(self):
        # R10：坏回执 = 结果未知 → 只读核实；绝不当确定失败、绝不引导重发 remember
        out = self.call('store: durable fixture fact', mode='silent')
        self.assertIn('store unknown', out)
        self.assertIn('Do NOT resend', out)
        self.assertIn('rsrs list --limit 3', out)
        self.assertNotIn('did not accept', out)
        self.assertEqual([args[0] for args in self.recorded()], ['remember', 'list'])

    def test_store_timeout_is_unknown_and_makes_no_further_calls(self):
        # 超时 = 结果未知：回执只允许只读核实指引，不再发引擎调用（预算已耗尽）
        before = self.recorded()
        out = self.call('store: durable fixture fact', mode='hang', fast=True)
        self.assertIn('store unknown', out)
        self.assertIn('timed out', out)
        self.assertIn('Do NOT resend', out)
        self.assertEqual(len(self.recorded()) - len(before), 1)

    def test_stop_deny_and_reentry_zero_calls(self):
        out = self.call(event='Stop')
        self.assertTrue(stop_denied(out), out)
        self.assertIn('rsrs remember', json.loads(out)['reason'])
        before, count = self.recorded(), (self.case / 'nudge').read_text(encoding="utf-8")
        self.assertEqual(self.call(event='Stop', active=True), '')
        self.assertEqual(self.recorded(), before)
        self.assertEqual((self.case / 'nudge').read_text(encoding="utf-8"), count)

    def test_stop_every_third_request_and_disabled_zero_calls(self):
        for number in range(1, 7):
            self.call(f'ordinary input {number}')          # 每轮都是新请求：重新武装收尾预算
            raw = self.call(event='Stop', every=3)
            if number in (3, 6):
                self.assertTrue(stop_denied(raw), raw)
            else:
                self.assertEqual(raw, '')
        self.assertEqual([a[0] for a in self.recorded()].count('list'), 0)
        before = self.recorded()
        self.assertEqual(self.call(event='Stop', every=0), '')
        self.assertEqual(self.recorded(), before)
        self.assertEqual((self.case / 'nudge').read_text(encoding="utf-8"), '6')

    def test_stop_never_queries_engine(self):
        # 复核整改：Stop 完全不再查询引擎——无归属的全库时间抑制已移除，也没有查库失败强迫续跑路径
        for mode in ('ok', 'recent', 'failed', 'malformed'):
            self.call(f'request before stop {mode}')
            self.assertEqual(json.loads(self.call(event='Stop', mode=mode))['hookSpecificOutput']['permissionDecision'], 'deny', mode)
        self.assertEqual([a[0] for a in self.recorded()].count('list'), 0)

    def test_latch_is_per_session_and_permanent_until_new_prompt(self):
        self.call('session A first request', session='A')
        self.assertEqual(json.loads(self.call(event='Stop', session='A'))['hookSpecificOutput']['permissionDecision'], 'deny')
        self.call('session B unrelated request', session='B')
        self.assertEqual(json.loads(self.call(event='Stop', session='B'))['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertEqual(self.call(event='Stop', session='A'), '')  # A 的锁不被 B 消耗
        self.call('session A second request', session='A')
        self.assertEqual(json.loads(self.call(event='Stop', session='A'))['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_receipt_edge_cases_are_unknown_not_failed(self):
        for mode in ('ok_noid', 'ok_junkid', 'bad_summary'):
            out = self.call('store: edge fact', mode=mode)
            self.assertIn('store unknown', out, mode)
            self.assertIn('Do NOT resend', out, mode)
            self.assertNotIn('did not accept', out, mode)
            self.assertNotIn('Saved', out, mode)
        out = self.call('store: edge fact', mode='skip_status')
        self.assertIn('not stored', out)
        self.assertIn('never force a write', out)
        self.assertNotIn('did not accept', out)

    def test_readback_full_verification(self):
        out = self.call('store: full verify fact', mode='show_wrongid')
        self.assertIn('Saved:', out)
        self.assertIn('DIFFERENT', out)
        self.assertNotIn('verified by read-back', out)
        out = self.call('store: full verify fact tail', mode='show_tail')
        self.assertIn('DIFFERENT', out)
        self.assertNotIn('verified by read-back', out)
        out = self.call('store: full verify fact ok')
        self.assertIn('verified by read-back', out)

    def test_strict_id_whitelist_and_readback_types(self):
        # R3#2：数字 id 12345678（JSON number，不得 str() 强转）、"a-------"（宽松 hex-连字符）
        # 都不是有效 id → 回执 unknown（不 Saved、不引导重发）
        for mode in ('ok_numid', 'ok_dashid'):
            out = self.call('store: strict fact', mode=mode)
            self.assertIn('store unknown', out, mode)
            self.assertNotIn('Saved', out, mode)
            self.assertIn('Do NOT resend', out, mode)
        # 回读三方 id：summary.id 正确但 entry.id 错（'DIFFERENT'）/缺失 → mismatch，Saved 保留
        for mode in ('show_entrydiff', 'show_noentryid'):
            out = self.call('store: strict fact entry', mode=mode)
            self.assertIn('Saved:', out, mode)                    # 有效写回执保留
            self.assertIn('DIFFERENT', out, mode)
            self.assertNotIn('verified by read-back', out, mode)
            self.assertNotIn('Read-back unavailable', out, mode)  # 是 mismatch，不是 unavailable
        # 数字 content（42 ≠ "42"）不做强转匹配 → mismatch，Saved 保留
        out = self.call('store: strict fact num', mode='show_numcontent')
        self.assertIn('Saved:', out)
        self.assertIn('DIFFERENT', out)
        self.assertNotIn('verified by read-back', out)

    def test_slow_bad_receipt_respects_shared_budget(self):
        before = self.recorded()
        out = self.call('store: slow garbage fact', mode='slow_garbage',
                        extra_env={'RESPITE_HOOK_BUDGET_S': '4'})
        self.assertIn('store unknown', out)
        self.assertIn('Do NOT resend', out)
        self.assertEqual(len(self.recorded()) - len(before), 1)

    def test_verify_list_schema_failures_are_not_attribution(self):
        for mode in ('list_schema', 'list_notimes'):
            out = self.call('store: schema fact', mode='silent', list_mode=mode)
            self.assertIn('store unknown', out, mode)
            self.assertNotIn('may already be written', out, mode)
    def test_stop_after_hook_store_does_not_query_engine(self):
        # R3 终案：磁盘凭证免催已取消——store 成功后 Stop 仍催（deny），且零引擎查询
        self.call('store: durable fixture fact')
        before = self.recorded()
        self.assertTrue(stop_denied(self.call(event='Stop')))   # 不凭旧回执免催
        self.assertEqual(self.recorded(), before)               # 零引擎查询

    def test_turn_receipt_suppression_is_request_scoped(self):
        # R3 终案：磁盘凭证免催已取消——Stop 不凭任何旧记录免催；同请求二次 Stop 由 latch 放行
        self.call('store: durable fixture fact')
        self.assertTrue(stop_denied(self.call(event='Stop')))      # store 后仍催
        self.assertEqual(self.call(event='Stop'), '')              # 同请求二次 Stop：latch 放行
        self.call('another ordinary input without storing')        # 新请求：重新武装
        self.assertTrue(stop_denied(self.call(event='Stop')))

    def test_stop_once_per_request_latch(self):
        # WB-05：宿主未带 stop_hook_active 时，同一请求也至多催一次；新请求重新武装
        self.call('ordinary input')
        self.assertTrue(stop_denied(self.call(event='Stop')))
        before = self.recorded()
        self.assertEqual(self.call(event='Stop'), '')
        self.assertEqual(self.recorded(), before)
        self.call('fresh request after wrap-up')
        self.assertTrue(stop_denied(self.call(event='Stop')))

    def test_receipt_suppression_is_session_scoped(self):
        # 会话隔离（R3 终案后由 latch 保证）：A 会话的写回执/催存不影响 B 会话的收尾锁
        self.call('store: durable fixture fact', session='a')
        self.assertTrue(stop_denied(self.call(event='Stop', session='b')))

    def test_generation_replay_does_not_rearm_latch(self):
        # R4（官方 v2.144.0+ 契约）：同 generation 重投不重新武装；新 generation 同文本重新武装
        # 序列：同 gen UserPromptSubmit → Stop deny → 同 gen 重投 → Stop 放行 → 新 gen 同文本 → Stop deny
        g1 = 'gen-aaa-111'
        self.call('real question one', generation=g1)
        self.assertEqual(json.loads(self.call(event='Stop', generation=g1))
                         ['hookSpecificOutput']['permissionDecision'], 'deny')
        self.call('real question one', generation=g1)   # 同 gen 重投（迟到/重复投递）
        self.assertEqual(self.call(event='Stop', generation=g1), '')  # 未重新武装：放行
        g2 = 'gen-bbb-222'
        self.call('real question one', generation=g2)   # 新 generation：同文本也是新请求
        self.assertEqual(json.loads(self.call(event='Stop', generation=g2))
                         ['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_stale_generation_cannot_undo_new_protection(self):
        # 旧 generation 迟到到达：不撤销新 generation 已落锁/已催的状态
        g1, g2 = 'gen-old-1', 'gen-new-2'
        self.call('first question', generation=g1)
        self.call('second question', generation=g2)     # 新请求（rearm）
        self.call('first question', generation=g1)      # 旧 gen 迟到重投：不 rearm、不覆写 gen
        self.assertEqual(json.loads(self.call(event='Stop', generation=g2))
                         ['hookSpecificOutput']['permissionDecision'], 'deny')  # 新请求仍可催

    def test_no_generation_field_keeps_compatible_behavior(self):
        # 无 generation_id（旧宿主/旧版本）：每次非内部 UserPromptSubmit 重新武装（既有行为）
        self.call('legacy question one')
        self.assertEqual(json.loads(self.call(event='Stop'))
                         ['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertEqual(self.call(event='Stop'), '')     # latch：同请求一次
        self.call('legacy question one')                  # 重发（无身份）：按新请求处理
        self.assertEqual(json.loads(self.call(event='Stop'))
                         ['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_internal_prefix_prompt_does_not_rearm_latch(self):
        # 复审 R2#1 点名序列：真实请求→Stop deny→同会话内部 Recap（配置 skip_prefixes）→Stop
        # ——必须不再 deny（宿主未带 stop_hook_active 正是收尾锁要兜底的场景）。
        # 内部事件不 mark：不记请求代、不删锁、不发引擎调用。
        self.call('real request that will be nudged')
        self.assertTrue(stop_denied(self.call(event='Stop')))
        before = self.recorded()
        internal = 'Host internal recap: summarizing the session for the host task'
        self.assertEqual(self.call(internal, skip=['Host internal recap']), '')
        self.assertEqual(self.recorded(), before)          # 内部提示零引擎调用
        self.assertEqual(self.call(event='Stop'), '')      # 收尾锁未被内部 Recap 重新武装
        # 重放同一真实请求文本（宿主无请求身份可去重）：保守按新请求处理——重新武装
        # （重放本就视为新投递，锁只在无新真实请求时保持，不额外伤害）
        self.call('real request that will be nudged')
        self.assertTrue(stop_denied(self.call(event='Stop')))

    def test_store_readback_bad_details_type_keeps_receipt(self):
        # 复审 R2#2：show 回 status=ok 但 details 非 dict（数组/字符串）→ 回读降级 unavailable，
        # 不得抛 AttributeError 冒到主入口被兜成空输出、吞掉已写的 Saved 回执
        for mode in ('show_badetails', 'show_strdetails'):
            out = self.call('store: durable fixture fact', mode=mode)
            self.assertNotEqual(out, '', mode)                       # 回执没有消失
            self.assertIn('Saved:', out, mode)                       # 已写入如实保留
            self.assertIn('Read-back unavailable', out, mode)        # 核验如实降级
            self.assertNotIn('did not accept', out, mode)            # 不误报失败
            self.assertNotIn('DIFFERENT', out, mode)                 # 不误报 mismatch
            self.assertEqual([a[0] for a in self.recorded()][-2:], ['remember', 'show'], mode)

    def test_malformed_spy_cannot_pass_positive_control(self):
        self.positive_control()
        self.assertEqual(self.call('ordinary input', mode='malformed'), '')
        self.assertIn('parse_error', self.log.read_text(encoding="utf-8"))


class TurnStateFiles(unittest.TestCase):
    """复审 R2#3：会话独立状态文件 st_<sid>.json——共享 turn_map.json 的读-改-写回滚窗口
    不复存在。R3 终案后这些文件只是诊断轨迹（免催已取消、turn_stored 恒 False），本组
    同时钉住「轨迹按会话隔离不被回滚」与「任何磁盘状态都不再影响 Stop 决策」。
    直接驱动 hook 的状态函数（引擎路径由 CredentialGuard 覆盖），状态目录隔离。"""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            'respire_hook_under_test', ROOT / 'hooks' / 'respire.py')
        cls.hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.hook)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='workbuddy-state-')
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        patcher = mock.patch.dict(os.environ, {'RESPITE_TURN_STATE': str(self.dir)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_state_files_are_one_per_session_and_no_shared_map(self):
        self.hook.mark_prompt('a')
        self.hook.mark_prompt('b')
        names = sorted(p.name for p in self.dir.glob('st_*.json'))
        self.assertEqual(len(names), 2)
        self.assertIn('st_' + self.hook._sid_key('a') + '.json', names)
        self.assertIn('st_' + self.hook._sid_key('b') + '.json', names)
        self.assertFalse((self.dir / 'turn_map.json').exists())   # 共享 map 已删除

    def test_barrier_interleave_b_cannot_roll_back_a(self):
        # 复审确定性交错：A 上轮 prompt_ts=T-50, store_ts=T-10 → B 载入自己的快照
        # → A 新请求把 prompt_ts 推进到 T+50 → B 写回。共享 map 下 B 的整文件写回会把 A
        # 恢复成旧快照；独立文件下 B 只写 B 的文件。R3 终案：免催已取消（turn_stored 恒 False，
        # 复审#1 的同会话 RMW 屏障交错即使恢复旧凭证也不再影响任何决策）——本测试钉住
        # 轨迹隔离本身与恒 False 语义。
        now = time.time()
        self.hook._state_update('a', {'prompt_ts': now - 50.0})    # A 上轮请求
        self.hook.mark_store('a', now - 50.0)                      # A 上轮写回执（绑定同代）
        self.hook._state_update('a', {'store_ts': now - 10.0})     # 钉住确定性时钟：store 在 prompt 后
        self.assertFalse(self.hook.turn_stored('a'))               # 免催已取消：即使凭证「成立」也 False
        self.assertEqual(self.hook._state_load('b'), {})           # barrier：B 载入自己的空快照
        self.hook._state_update('a', {'prompt_ts': now + 50.0})    # A 新真实请求
        self.assertFalse(self.hook.turn_stored('a'))               # 恒 False
        self.hook._state_update('b', {'prompt_ts': now + 50.0})    # B 写回（旧共享 map 语义下整文件覆盖）
        self.assertEqual(self.hook._state_load('a').get('prompt_ts'), now + 50.0)  # A 的推进未丢
        self.assertFalse(self.hook.turn_stored('a'))               # 恒 False（B 的写回无从影响决策）

    def test_delayed_old_store_does_not_suppress_new_request(self):
        # R3 终案：免催已取消——无论请求代如何（旧代/新代凭证「成立」与否）turn_stored 恒 False，
        # 复审#1 的「旧请求延迟完成的写回执恢复免催」路径整体不存在了
        old_gen = self.hook.mark_prompt('s')
        self.hook.mark_store('s', old_gen)
        self.assertFalse(self.hook.turn_stored('s'))               # 免催已取消：旧轮内也 False
        self.hook.mark_prompt('s')                                  # 新请求（新代）
        self.hook.mark_store('s', old_gen)                          # 旧请求延迟完成的写（带旧代）
        self.assertFalse(self.hook.turn_stored('s'))                # 恒 False
        new_gen = self.hook.mark_prompt('s')                        # 再来一轮并正常存
        self.hook.mark_store('s', new_gen)
        self.assertFalse(self.hook.turn_stored('s'))                # 恒 False（回执仍诚实给模型）

    def test_concurrent_session_updates_never_lost(self):
        # A/B 并发更新不丢失：各会话独立文件，交错读写互不可见；R3 终案后轨迹完好即可，
        # 决策不读它（turn_stored 恒 False）
        sessions = ['session-%02d' % i for i in range(8)]

        def churn(name):
            for _ in range(25):
                gen = self.hook.mark_prompt(name)
                self.hook.mark_store(name, gen)

        threads = [threading.Thread(target=churn, args=(n,)) for n in sessions]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        for name in sessions:
            trace = self.dir / ('st_' + self.hook._sid_key(name) + '.json')
            self.assertTrue(trace.exists(), name)                  # 诊断轨迹仍在
            self.assertFalse(self.hook.turn_stored(name), name)    # 决策恒不受轨迹影响


class VersionConsistency(unittest.TestCase):
    def test_marketplace_manifest_and_hook_match(self):
        repo = ROOT.parents[1]
        market = json.loads((repo / '.codebuddy-plugin/marketplace.json').read_text(encoding="utf-8"))
        entry = next(item for item in market['plugins'] if item['name'] == 'respire')
        manifest = json.loads((ROOT / '.codebuddy-plugin/plugin.json').read_text(encoding="utf-8"))
        hook_version = re.search(r'^VERSION = "([^"]+)"', (ROOT / 'hooks/respire.py').read_text(encoding="utf-8"), re.M).group(1)
        self.assertEqual(entry['version'], manifest['version'])
        self.assertEqual(hook_version, manifest['version'])

    def test_validator_rejects_each_version_mismatch(self):
        repo = ROOT.parents[1]
        for component in ('marketplace', 'manifest', 'hook'):
            with self.subTest(component=component), tempfile.TemporaryDirectory(prefix='workbuddy-version-') as directory:
                fixture = Path(directory)
                shutil.copytree(ROOT, fixture / 'plugins/respire', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                shutil.copytree(repo / '.codebuddy-plugin', fixture / '.codebuddy-plugin')
                for name in ('README.md', 'CHANGELOG.md', 'LICENSE', 'install.sh'):
                    shutil.copy2(repo / name, fixture / name)
                if component == 'hook':
                    path = fixture / 'plugins/respire/hooks/respire.py'
                    path.write_text(re.sub(r'^VERSION = "[^"]+"', 'VERSION = "999.0.0"', path.read_text(encoding="utf-8"), count=1, flags=re.M), encoding="utf-8")
                else:
                    path = fixture / ('.codebuddy-plugin/marketplace.json' if component == 'marketplace'
                                      else 'plugins/respire/.codebuddy-plugin/plugin.json')
                    doc = json.loads(path.read_text(encoding="utf-8"))
                    if component == 'marketplace':
                        next(item for item in doc['plugins'] if item['name'] == 'respire')['version'] = '999.0.0'
                    else:
                        doc['version'] = '999.0.0'
                    path.write_text(json.dumps(doc), encoding="utf-8")
                env = {k:v for k,v in os.environ.items() if k.upper() in {'PATH','SYSTEMROOT','WINDIR','PATHEXT','TEMP','TMP','COMSPEC'}}
                env.update(HOME=str(fixture / 'home'), USERPROFILE=str(fixture / 'home'))
                result = subprocess.run([sys.executable, str(fixture / 'plugins/respire/scripts/validate_plugin.py')],
                                        text=True, encoding='utf-8', capture_output=True, env=env, timeout=30)
                self.assertEqual(result.returncode, 1)
                self.assertIn('version', (result.stdout + result.stderr).lower())


class ProcessAuditPolicy(unittest.TestCase):
    def test_windows_none_executable_and_exact_commandline_are_allowed(self):
        expected = [r'C:\temp\space name\rsrs-spy.cmd', 'recall', 'ordinary input', '--json']
        self.assertTrue(allowed_process(None, subprocess.list2cmdline(expected), expected, True))

    def test_posix_exact_executable_and_complete_argv_are_allowed(self):
        expected = ['/tmp/rsrs-spy', 'recall', 'ordinary input', '--json']
        self.assertTrue(allowed_process(expected[0], expected, expected, False))

    def test_other_programs_arguments_and_shell_additions_are_rejected(self):
        expected = [r'C:\temp\space name\rsrs-spy.cmd', 'recall', 'ordinary input', '--json']
        encoded = subprocess.list2cmdline(expected)
        for executable, argv, windows in (
                ('cmd.exe', encoded, True),
                ('python.exe', encoded, True),
                (None, encoded + ' & echo unwanted', True),
                (None, encoded + ' extra', True),
                (None, 'cmd.exe /c ' + encoded, True),
                (None, encoded.replace('rsrs-spy.cmd', 'rsrs-spy.cmd-other'), True),
                (None, encoded, False),
                (expected[0], expected + ['extra'], False),
        ):
            with self.subTest(executable=executable, argv=argv):
                self.assertFalse(allowed_process(executable, argv, expected, windows))


if __name__ == '__main__':
    unittest.main(verbosity=2)
