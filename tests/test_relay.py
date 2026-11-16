"""Durable outbound relay contracts. No real credential or gateway is used."""
import hashlib
from contextlib import asynccontextmanager
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import anyio
import httpx2
from mcp import types

from rdc.relay import (
    Gateway, Journal, Operation, RelayConfig, RelayError, RelayMissingOperation, RelayPermanentError,
    RelayPump, RelayTransientError, error_result, validate_gateway_url,
    validate_worker_url, run_relay, _worker_session,
)


SECRET = 'device-secret-that-must-stay-private-' + 'd' * 40
SITE_SECRET = 'site-service-token-that-must-stay-private-' + 's' * 40
CATALOG = {'rdc_fixture_write': {'type': 'object', 'properties': {'text': {'type': 'string'}}, 'required': ['text'], 'additionalProperties': False}}


def config(**overrides):
    return RelayConfig(**({'gateway_url': 'https://relay.example.test', 'device_id': 'device-test',
        'device_key': SECRET, 'sites_service_token': SITE_SECRET} | overrides))


def operation(identifier='op-test-1', arguments=None, *, name='rdc_fixture_write', remaining=30000):
    request = json.dumps({'name': name, 'arguments': arguments if arguments is not None else {'text': 'hello'}}, separators=(',', ':'))
    server_time = int(time.time() * 1000)
    return Operation.from_wire({'operation_id': identifier, 'claim_id': 'claim-' + identifier,
        'request_json': request, 'request_sha256': hashlib.sha256(request.encode()).hexdigest(),
        'expires_at_ms': server_time + remaining}, server_time)


class FakeWorker:
    def __init__(self, error=None):
        self.calls = []; self.error = error
    async def call_tool(self, name, arguments, **kwargs):
        self.calls.append((name, arguments))
        if self.error: raise self.error
        return types.CallToolResult(content=[types.TextContent(type='text', text='done')], structured_content={'ok': True, 'text': arguments.get('text')})


class FakeGateway:
    def __init__(self, failures=0):
        self.failures = failures; self.results = []; self.polls = []
    async def submit(self, operation, result_json):
        self.results.append((operation.operation_id, result_json))
        if self.failures:
            self.failures -= 1; raise RelayTransientError('Gateway connection interrupted.')
    async def poll(self, claim=True):
        self.polls.append(claim)
        return None, .25


class RelayObservationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.journal = Journal(Path(self.directory.name) / 'relay.sqlite3', 'observer-test')
        self.catalog = CATALOG | {'rdc_preview_activity': {
            'type': 'object', 'properties': {}, 'additionalProperties': False}}

    def tearDown(self):
        self.journal.close()
        self.directory.cleanup()

    def test_activity_is_claimed_and_delivered_before_blocked_primary_finishes(self):
        async def run():
            started, release, observed = anyio.Event(), anyio.Event(), anyio.Event()
            primary = operation('primary-blocked')
            activity = operation('activity-live', {}, name='rdc_preview_activity')
            calls = []
            class Worker:
                async def call_tool(inner, name, arguments, **kwargs):
                    calls.append(name)
                    if name == 'rdc_fixture_write':
                        started.set()
                        await release.wait()
                    return types.CallToolResult(content=[], structured_content={'ok': True, 'source': name})
            class GatewayFixture(FakeGateway):
                supports_activity_observer = True
                async def poll(inner, claim=True, observation_only=False):
                    self.assertTrue(claim)
                    self.assertTrue(observation_only)
                    return (activity if not inner.polls else None), .25
                async def submit(inner, op, result_json):
                    inner.polls.append(True)
                    await super().submit(op, result_json)
                    if op.operation_id == activity.operation_id:
                        observed.set()
            gateway = GatewayFixture(failures=1)
            pump = RelayPump(config(), self.journal, gateway, Worker(), self.catalog)
            with patch('rdc.relay.OBSERVER_POLL_SECONDS', .01, create=True):
                async with anyio.create_task_group() as tasks:
                    tasks.start_soon(pump.handle, primary)
                    await started.wait()
                    with anyio.fail_after(1):
                        await observed.wait()
                    self.assertEqual(self.journal.get(primary.operation_id)['state'], 'executing')
                    self.assertEqual(self.journal.get(activity.operation_id)['state'], 'delivered')
                    self.assertEqual(calls, ['rdc_fixture_write', 'rdc_preview_activity'])
                    self.assertEqual(gateway.results[0], gateway.results[1])
                    release.set()
            await pump.flush()
            self.assertFalse(pump.worker_lost)
            self.assertEqual(self.journal.get(primary.operation_id)['state'], 'delivered')
        anyio.run(run)

    def test_observer_rejects_mutation_before_touching_existing_primary_identity(self):
        primary = operation('same-primary')
        self.journal.remember(primary)
        self.journal.mark_executing(primary.operation_id)
        worker, gateway = FakeWorker(), FakeGateway()
        pump = RelayPump(config(), self.journal, gateway, worker, self.catalog)
        async def run():
            with self.assertRaises(RelayPermanentError):
                await pump.observe(primary)
        anyio.run(run)
        self.assertEqual(worker.calls, [])
        self.assertEqual(self.journal.get(primary.operation_id)['state'], 'executing')
        self.assertIsNone(self.journal.get(primary.operation_id)['result_json'])

    def test_observer_failure_does_not_mark_primary_worker_lost_or_replay(self):
        worker, gateway = FakeWorker(error=RuntimeError('private details')), FakeGateway()
        pump = RelayPump(config(), self.journal, gateway, worker, self.catalog)
        activity = operation('activity-error', {}, name='rdc_preview_activity')
        async def run():
            await pump.observe(activity)
            await pump.observe(activity)
        anyio.run(run)
        self.assertFalse(pump.worker_lost)
        self.assertEqual(worker.calls, [('rdc_preview_activity', {})])
        self.assertEqual(gateway.results[0], gateway.results[1])
        self.assertNotIn('private details', gateway.results[0][1])
        self.assertEqual(json.loads(gateway.results[0][1])['structuredContent']['error']['code'], 'outcome_unknown')

    def test_primary_completion_cancels_observer_into_retained_terminal_result(self):
        async def run():
            started, observer_started, release = anyio.Event(), anyio.Event(), anyio.Event()
            primary = operation('primary-finishes')
            activity = operation('activity-cancelled', {}, name='rdc_preview_activity')
            calls = []
            class Worker:
                async def call_tool(inner, name, arguments, **kwargs):
                    calls.append(name)
                    if name == 'rdc_fixture_write':
                        started.set()
                        await release.wait()
                        return types.CallToolResult(content=[], structured_content={'ok': True, 'value': 'actual primary result'})
                    observer_started.set()
                    await anyio.sleep_forever()
            class GatewayFixture(FakeGateway):
                supports_activity_observer = True
                async def poll(inner, claim=True, observation_only=False):
                    self.assertTrue(observation_only)
                    return activity, .25
            gateway = GatewayFixture()
            pump = RelayPump(config(), self.journal, gateway, Worker(), self.catalog)
            with patch('rdc.relay.OBSERVER_POLL_SECONDS', .01, create=True):
                async with anyio.create_task_group() as tasks:
                    tasks.start_soon(pump.handle, primary)
                    await started.wait()
                    with anyio.fail_after(1):
                        await observer_started.wait()
                    release.set()
            self.assertEqual(self.journal.get(activity.operation_id)['state'], 'ready')
            await pump.flush()
            await pump.observe(activity)
            self.assertFalse(pump.worker_lost)
            self.assertEqual(calls, ['rdc_fixture_write', 'rdc_preview_activity'])
            primary_result = json.loads(next(value for identifier, value in gateway.results if identifier == primary.operation_id))
            self.assertEqual(primary_result['structuredContent']['value'], 'actual primary result')
            observed_result = json.loads(next(value for identifier, value in gateway.results if identifier == activity.operation_id))
            self.assertEqual(observed_result['structuredContent']['error']['code'], 'observation_interrupted')
        anyio.run(run)

    def test_observer_retains_schema_deadline_and_local_allowlist(self):
        worker, gateway = FakeWorker(), FakeGateway()
        pump = RelayPump(config(), self.journal, gateway, worker, self.catalog)
        cases = [operation('activity-schema', {'unexpected': True}, name='rdc_preview_activity'),
                 operation('activity-expired', {}, name='rdc_preview_activity', remaining=-1)]
        async def run():
            for op in cases:
                await pump.observe(op)
            restricted = RelayPump(config(allowed_tools=('rdc_fixture_write',)), self.journal, gateway, worker, self.catalog)
            await restricted.observe(operation('activity-forbidden', {}, name='rdc_preview_activity'))
        anyio.run(run)
        self.assertEqual(worker.calls, [])
        codes = [json.loads(result)['structuredContent']['error']['code'] for _, result in gateway.results]
        self.assertEqual(codes, ['invalid_arguments', 'operation_expired', 'tool_forbidden'])

    def test_gateway_requires_observer_advertisement_before_sending_a_claim(self):
        requests = []
        def respond(request):
            requests.append(json.loads(request.content))
            return httpx2.Response(200, json={'ok': True, 'device_id': 'device-test',
                'server_time_ms': int(time.time()*1000), 'operation': None})
        async def run():
            async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as client:
                gateway = Gateway(config(), client)
                await gateway.poll(claim=False)
                self.assertFalse(gateway.supports_activity_observer)
                with self.assertRaises(RelayPermanentError):
                    await gateway.poll(observation_only=True)
        anyio.run(run)
        self.assertEqual(len(requests), 1)
        self.assertFalse(requests[0]['claim'])
        self.assertNotIn('observation_only', requests[0])

    def test_gateway_observer_claim_requires_explicit_activity_only_confirmation(self):
        requests = []
        def respond(request):
            payload = json.loads(request.content)
            requests.append(payload)
            return httpx2.Response(200, json={'ok': True, 'device_id': 'device-test',
                'server_time_ms': int(time.time()*1000), 'operation': None,
                'observation_tools': ['rdc_preview_activity'],
                'observation_only': payload.get('observation_only') is True and len(requests) == 2})
        async def run():
            async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as client:
                gateway = Gateway(config(), client)
                await gateway.poll(claim=False)
                self.assertTrue(gateway.supports_activity_observer)
                await gateway.poll(observation_only=True)
                with self.assertRaises(RelayPermanentError):
                    await gateway.poll(observation_only=True)
        anyio.run(run)
        self.assertEqual(len(requests), 3)
        self.assertTrue(requests[1]['claim'])
        self.assertTrue(requests[1]['observation_only'])


class RelayDurabilityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'relay.sqlite3'
        self.journal = Journal(self.path, 'scope-test')
        self.worker = FakeWorker(); self.gateway = FakeGateway()
        self.pump = RelayPump(config(), self.journal, self.gateway, self.worker, CATALOG)

    def tearDown(self):
        self.journal.close(); self.directory.cleanup()

    def test_repeated_operation_is_executed_once(self):
        op = operation()
        async def run():
            await self.pump.handle(op)
            await self.pump.handle(op)
            await self.pump.flush()
        anyio.run(run)
        self.assertEqual(self.worker.calls, [('rdc_fixture_write', {'text': 'hello'})])
        self.assertEqual(len(self.gateway.results), 1)
        self.assertEqual(self.journal.get(op.operation_id)['state'], 'delivered')

    def test_result_upload_retry_reuses_exact_result_without_reexecution(self):
        self.gateway.failures = 1
        async def run():
            await self.pump.handle(operation())
            with self.assertRaises(RelayTransientError): await self.pump.flush()
            self.assertEqual(self.journal.get('op-test-1')['state'], 'ready')
            await self.pump.flush()
        anyio.run(run)
        self.assertEqual(len(self.worker.calls), 1)
        self.assertEqual(self.gateway.results[0], self.gateway.results[1])
        self.assertEqual(self.journal.get('op-test-1')['state'], 'delivered')

    def test_crash_after_dispatch_is_reported_unknown_and_never_replayed(self):
        op = operation()
        self.journal.remember(op)
        self.journal.mark_executing(op.operation_id)
        self.journal.close()
        self.journal = Journal(self.path, 'scope-test')
        self.journal.recover()
        self.pump = RelayPump(config(), self.journal, self.gateway, self.worker, CATALOG)
        async def run():
            await self.pump.handle(op)
            await self.pump.flush()
        anyio.run(run)
        self.assertEqual(self.worker.calls, [])
        result = json.loads(self.gateway.results[-1][1])
        self.assertTrue(result['isError'])
        self.assertEqual(result['structuredContent']['error']['code'], 'outcome_unknown')

    def test_crash_before_dispatch_is_not_automatically_executed(self):
        op = operation()
        self.journal.remember(op); self.journal.recover()
        anyio.run(self.pump.handle, op)
        self.assertEqual(self.worker.calls, [])
        result = json.loads(self.journal.get(op.operation_id)['result_json'])
        self.assertEqual(result['structuredContent']['error']['code'], 'interrupted_before_dispatch')

    def test_identifier_reuse_with_different_request_is_rejected(self):
        self.journal.remember(operation())
        async def run():
            with self.assertRaises(RelayPermanentError):
                await self.pump.handle(operation(arguments={'text': 'different'}))
        anyio.run(run)
        self.assertEqual(self.worker.calls, [])

    def test_uncertain_worker_exception_redacts_error_and_does_not_replay(self):
        self.worker.error = RuntimeError('Authorization Bearer ' + SECRET + ' URL https://secret.test/' + SITE_SECRET)
        async def run():
            await self.pump.handle(operation())
            await self.pump.handle(operation())
            await self.pump.flush()
        anyio.run(run)
        self.assertEqual(len(self.worker.calls), 1)
        result_json = self.gateway.results[0][1]
        self.assertNotIn(SECRET, result_json); self.assertNotIn(SITE_SECRET, result_json)
        self.assertIn('outcome_unknown', result_json)

    def test_catalog_schema_allowlist_and_expiry_gate_before_dispatch(self):
        cases = [operation('bad-schema', {'text': 12}), operation('unknown-tool', name='rdc_owner_approve'), operation('expired-op', remaining=-1)]
        async def run():
            for op in cases: await self.pump.handle(op)
        anyio.run(run)
        self.assertEqual(self.worker.calls, [])
        for op in cases:
            result = json.loads(self.journal.get(op.operation_id)['result_json'])
            self.assertTrue(result['isError'])
        self.assertEqual(json.loads(self.journal.get('expired-op')['result_json'])['structuredContent']['error']['code'], 'operation_expired')
        restricted = RelayPump(config(allowed_tools=('rdc_system_status',)), self.journal, self.gateway, self.worker, CATALOG)
        anyio.run(restricted.handle, operation('not-allowed'))
        self.assertEqual(self.worker.calls, [])

    def test_result_retention_keeps_execution_tombstone(self):
        op = operation(); self.journal.remember(op); self.journal.mark_executing(op.operation_id)
        encoded = json.dumps(error_result('fixture', 'x' * 2000, op.operation_id))
        self.journal.complete(op.operation_id, encoded); self.journal.delivered(op.operation_id)
        self.journal.prune_results(max_bytes=1)
        self.assertIsNone(self.journal.get(op.operation_id)['result_json'])
        anyio.run(self.pump.handle, op)
        self.assertEqual(self.worker.calls, [])
        self.assertEqual(json.loads(self.journal.get(op.operation_id)['result_json'])['structuredContent']['error']['code'], 'result_expired')

    def test_result_that_exceeds_escaped_upload_envelope_is_replaced_before_persistence(self):
        class LargeWorker(FakeWorker):
            async def call_tool(self, name, arguments, **kwargs):
                self.calls.append((name, arguments))
                # The result is about 10 MiB, but escaping it inside result_json
                # would produce an HTTP request exceeding the 16 MiB limit.
                return {'content': [{'type': 'text', 'text': '\\' * (5 * 1024 * 1024)}]}

        worker = LargeWorker()
        pump = RelayPump(config(), self.journal, self.gateway, worker, CATALOG)
        async def run():
            await pump.handle(operation())
            stored = self.journal.get('op-test-1')['result_json']
            self.assertLess(len(stored.encode()), 4096)
            self.assertEqual(json.loads(stored)['structuredContent']['error']['code'], 'result_too_large')
            await pump.flush()
            await pump.handle(operation())
        anyio.run(run)
        self.assertEqual(len(worker.calls), 1)
        self.assertEqual(len(self.gateway.results), 1)

    def test_older_oversized_outbox_is_recovered_without_dispatch_or_restart_loop(self):
        op = operation()
        self.journal.remember(op); self.journal.mark_executing(op.operation_id)
        oversized = json.dumps({'content': [{'type': 'text', 'text': '\\' * (5 * 1024 * 1024)}]}, separators=(',', ':'))
        self.journal.complete(op.operation_id, oversized)
        uploads = []
        async def handler(request):
            uploads.append(json.loads(request.content))
            self.assertLess(len(request.content), 4096)
            return httpx2.Response(200, json={'ok': True, 'operation_id': op.operation_id, 'status': 'completed'})
        async def run():
            async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as client:
                gateway = Gateway(config(), client)
                pump = RelayPump(config(), self.journal, gateway, self.worker, CATALOG)
                await pump.flush()
        anyio.run(run)
        self.assertEqual(self.worker.calls, [])
        self.assertEqual(len(uploads), 1)
        self.assertEqual(json.loads(uploads[0]['result_json'])['structuredContent']['error']['code'], 'result_too_large')
        self.assertEqual(self.journal.get(op.operation_id)['state'], 'delivered')

    def test_retired_uploads_remain_unacknowledged_without_blocking_unrelated_results(self):
        frame = operation('retired-frame', name='rdc_preview_frame')
        mutation = operation('missing-mutation')
        fresh = operation('fresh-result')
        original = json.dumps({'content': [], 'structuredContent': {'ok': True}})
        for op in (frame, mutation, fresh):
            self.journal.remember(op); self.journal.mark_executing(op.operation_id)
            self.journal.complete(op.operation_id, original)
        async def handler(request):
            body = json.loads(request.content)
            if body['operation_id'] == fresh.operation_id:
                return httpx2.Response(200, json={'ok': True, 'operation_id': fresh.operation_id, 'status': 'completed'})
            return httpx2.Response(404, json={'ok': False, 'error': {'code': 'operation_not_found', 'message': 'The operation was not found.'}})
        async def run():
            async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as client:
                pump = RelayPump(config(), self.journal, Gateway(config(), client), self.worker, CATALOG)
                try:
                    await pump.flush()
                except RelayPermanentError as exc:
                    self.fail(f'A retired operation blocked unrelated work: {exc}')
        with self.assertLogs('rdc.relay', level='WARNING') as messages:
            anyio.run(run)
        for op in (frame, mutation):
            row = self.journal.get(op.operation_id)
            self.assertEqual(row['state'], 'undeliverable')
            self.assertEqual(row['result_json'], original)
            self.assertEqual(row['request_json'], op.request_json)
            self.assertIn(op.operation_id, '\n'.join(messages.output))
        self.assertEqual(self.journal.get(fresh.operation_id)['state'], 'delivered')
        self.assertEqual(self.worker.calls, [])

    def test_retired_operation_cannot_reexecute_after_restart_reappearance_or_payload_pruning(self):
        old = operation('old-mutation')
        uploads = []
        class MissingGateway(FakeGateway):
            async def submit(self, op, result_json):
                uploads.append(op.operation_id)
                if op.operation_id == old.operation_id:
                    raise RelayMissingOperation('Gateway operation is retired.')

        gateway = MissingGateway()
        async def first_run():
            pump = RelayPump(config(), self.journal, gateway, self.worker, CATALOG)
            await pump.handle(old)
            try:
                await pump.flush()
            except RelayPermanentError as exc:
                self.fail(f'A retired operation stopped the pump: {exc}')
        with self.assertLogs('rdc.relay', level='WARNING'):
            anyio.run(first_run)
        self.assertEqual(self.worker.calls, [('rdc_fixture_write', {'text': 'hello'})])
        retained = self.journal.get(old.operation_id)['result_json']
        self.journal.close()
        self.journal = Journal(self.path, 'scope-test')
        self.journal.recover()
        self.assertEqual(self.journal.get(old.operation_id)['result_json'], retained)
        self.journal.prune_results(max_bytes=1)
        row = self.journal.get(old.operation_id)
        self.assertEqual(row['state'], 'undeliverable')
        self.assertIsNone(row['result_json'])
        self.assertIsNone(row['request_json'])
        self.assertEqual(row['request_sha256'], old.request_sha256)
        self.assertEqual(row['claim_id'], old.claim_id)
        async def resumed():
            pump = RelayPump(config(), self.journal, gateway, self.worker, CATALOG)
            await pump.handle(old)
            await pump.handle(operation('new-mutation', {'text': 'new action'}))
            await pump.flush()
        anyio.run(resumed)
        self.assertEqual(self.worker.calls, [('rdc_fixture_write', {'text': 'hello'}),
                                            ('rdc_fixture_write', {'text': 'new action'})])
        self.assertEqual(uploads, ['old-mutation', 'new-mutation'])
        self.assertEqual(self.journal.get(old.operation_id)['state'], 'undeliverable')
        self.assertEqual(self.journal.get('new-mutation')['state'], 'delivered')

    def test_delayed_poll_response_cannot_extend_operation_start_deadline(self):
        original = operation('delayed-response')
        server_time = int(time.time() * 1000)
        wire = {key: getattr(original, key) for key in ('operation_id', 'claim_id', 'request_json', 'request_sha256')}
        wire['expires_at_ms'] = server_time + 100
        async def handler(request):
            await anyio.sleep(.2)
            return httpx2.Response(200, json={'ok': True, 'device_id': 'device-test',
                'server_time_ms': server_time, 'operation': wire, 'poll_after_ms': 250})
        async def run():
            async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as client:
                claimed, _ = await Gateway(config(), client).poll()
                await self.pump.handle(claimed)
        anyio.run(run)
        self.assertEqual(self.worker.calls, [])
        stored = json.loads(self.journal.get(original.operation_id)['result_json'])
        self.assertEqual(stored['structuredContent']['error']['code'], 'operation_expired')

    def test_journal_cannot_be_rebound_to_another_gateway_device(self):
        self.journal.close()
        with self.assertRaises(RelayPermanentError): Journal(self.path, 'different-scope')
        self.journal = Journal(self.path, 'scope-test')


class RelayBoundaryTests(unittest.TestCase):
    def test_urls_reject_credentials_redirect_shaping_and_nonlocal_worker(self):
        for url in ('http://gateway.test', 'https://user:password@gateway.test', 'https://gateway.test/?token=secret', 'https://gateway.test/#secret', 'https://gateway.test/a/../b', 'https://gateway.test/a%2fb', 'https://gateway.test/\n'):
            with self.subTest(url=url), self.assertRaises(RelayPermanentError): validate_gateway_url(url)
        self.assertEqual(validate_gateway_url('https://gateway.test/rdc/'), 'https://gateway.test/rdc')
        for url in ('http://external.test/mcp', 'http://0.0.0.0/mcp', 'http://user:secret@127.0.0.1/mcp', 'http://127.0.0.1/mcp?token=secret'):
            with self.subTest(url=url), self.assertRaises(RelayPermanentError): validate_worker_url(url)
        self.assertEqual(validate_worker_url('http://127.0.0.1:8765/mcp'), 'http://127.0.0.1:8765/mcp')

    def test_private_config_validation_and_secret_repr(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'relay.json'
            path.write_text(json.dumps({'gateway_url':'https://gateway.test', 'device_id':'device-test', 'device_key':SECRET, 'sites_service_token':SITE_SECRET}))
            path.chmod(0o600)
            loaded = RelayConfig.load(path)
            self.assertNotIn(SECRET, repr(loaded)); self.assertNotIn(SITE_SECRET, repr(loaded))
            if __import__('os').name != 'nt':
                path.chmod(0o644)
                with self.assertRaises(RelayPermanentError): RelayConfig.load(path)

    def test_request_hash_and_duplicate_json_keys_rejected(self):
        op = operation()
        raw = dict(operation_id=op.operation_id, claim_id=op.claim_id, request_json=op.request_json, request_sha256='0'*64, expires_at_ms=op.expires_at_ms)
        with self.assertRaises(RelayPermanentError): Operation.from_wire(raw, int(time.time()*1000))
        raw['request_json'] = '{"name":"rdc_fixture_write","name":"rdc_owner_approve","arguments":{}}'
        raw['request_sha256'] = hashlib.sha256(raw['request_json'].encode()).hexdigest()
        with self.assertRaises(RelayPermanentError): Operation.from_wire(raw, int(time.time()*1000))

    def test_javascript_numeric_and_unicode_request_digest_survives_python_decoding(self):
        # Generated by the actual gateway's exported sha256(JSON.stringify(...)).
        # Python would spell 1e-7 differently if it reserialized these arguments.
        raw = '{"name":"rdc_pointer","arguments":{"x":1e-7,"y":1,"text":"Café 🌍 日本語"}}'
        digest = '4426a3b3da1408a06e5d9539faafbfab51b80dec9e79c1b2b1d2ccb554cfabdb'
        wire = {'operation_id': 'js-python-fixture', 'claim_id': 'js-python-claim',
                'request_json': raw, 'request_sha256': digest, 'expires_at_ms': 30001}
        op = Operation.from_wire(wire, 1)
        self.assertEqual(op.request_json, raw)
        self.assertEqual(op.request_sha256, digest)
        self.assertEqual(op.request['arguments'], {'x': 1e-7, 'y': 1.0, 'text': 'Café 🌍 日本語'})

    def test_gateway_headers_are_separate_no_redirect_and_redacted_error(self):
        seen = []
        async def handler(request):
            seen.append(request)
            return httpx2.Response(302, headers={'Location': 'https://other.test/' + SECRET}, text=SITE_SECRET)
        async def run():
            async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler), trust_env=False, follow_redirects=False) as client:
                gateway = Gateway(config(), client)
                with self.assertRaises(RelayPermanentError) as failure: await gateway.poll()
                self.assertNotIn(SECRET, str(failure.exception)); self.assertNotIn(SITE_SECRET, str(failure.exception))
        anyio.run(run)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].headers['X-RDC-Device-Key'], SECRET)
        self.assertEqual(seen[0].headers['OAI-Sites-Authorization'], 'Bearer ' + SITE_SECRET)
        self.assertNotIn('Authorization', seen[0].headers)

    def test_arbitrary_404_does_not_retire_a_frame_upload(self):
        async def handler(request):
            return httpx2.Response(404, json={'error': {'code': 'wrong_route'}})
        async def run():
            async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as client:
                with self.assertRaises(RelayPermanentError):
                    await Gateway(config(), client).submit(operation(name='rdc_preview_frame'), json.dumps({'content': []}))
        anyio.run(run)


class RelayTransportTests(unittest.TestCase):
    def test_idle_poll_backoff_reduces_call_rate_and_resets_immediately_on_work(self):
        """Run the real loop and journal with a virtual wait boundary, not real delays."""
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'state'; state.mkdir(mode=0o700)
            (state / 'agent-token').write_text('agent-fixture-' + 'a' * 48)
            (state / 'agent-token').chmod(0o600)
            cfg = Path(directory) / 'relay.json'
            cfg.write_text(json.dumps({'gateway_url': 'https://relay.example.test', 'device_id': 'device-test',
                'device_key': SECRET, 'sites_service_token': SITE_SECRET})); cfg.chmod(0o600)
            worker = FakeWorker()
            scheduled_waits, poll_times = [], []
            virtual_time = 0.0
            original_sleep = anyio.sleep

            @asynccontextmanager
            async def worker_session(config, token):
                yield worker, CATALOG

            async def run():
                stop = anyio.Event()
                replies = [(None, .25)] * 8 + [(operation('wake-one'), .25),
                    (None, .25), (None, 1.5), (operation('wake-two'), .25), (None, .25)]
                class GatewayFixture(FakeGateway):
                    async def poll(self, claim=True):
                        if not claim:
                            return None, .25
                        poll_times.append(virtual_time)
                        reply = replies.pop(0)
                        if not replies: stop.set()
                        return reply
                gateway = GatewayFixture()

                async def clocked_sleep(seconds):
                    nonlocal virtual_time
                    if not anyio.get_current_task().name.endswith('._heartbeat'):
                        scheduled_waits.append(seconds)
                        virtual_time += seconds
                    await original_sleep(0)

                with patch('rdc.relay.Gateway', return_value=gateway), \
                     patch('rdc.relay._worker_session', worker_session), \
                     patch('rdc.relay.anyio.sleep', clocked_sleep):
                    await run_relay(cfg, state, stop_event=stop)

            anyio.run(run)
            self.assertEqual(scheduled_waits[:8], [.25, .5, 1, 2, 4, 5, 5, 5])
            self.assertGreaterEqual(poll_times[8], 22, 'Eight idle polls must not remain a four-per-second loop')
            self.assertEqual(poll_times[9], poll_times[8], 'After work, the next claim must have no idle delay')
            self.assertEqual(scheduled_waits[8:], [.25, 1.5, .25], 'Activity resets local delay while preserving the server minimum')
            self.assertEqual(worker.calls, [('rdc_fixture_write', {'text': 'hello'})] * 2)

    def test_legacy_session_delete_has_a_finite_socket_read_deadline(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading

        delete_started = threading.Event(); release_delete = threading.Event()
        class LegacyWorker(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def respond(self, value=None, status=200, session=False):
                raw = json.dumps(value).encode() if value is not None else b''
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                if session: self.send_header('Mcp-Session-Id', 'legacy-fixture-session')
                self.end_headers()
                if raw: self.wfile.write(raw)
            def do_POST(self):
                value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                method = value['method']; response = {'jsonrpc': '2.0', 'id': value.get('id')}
                if method == 'server/discover':
                    response['error'] = {'code': -32601, 'message': 'Legacy fixture'}
                elif method == 'initialize':
                    response['result'] = {'protocolVersion': '2025-11-25', 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'rdc-fixture', 'version': '1'}}
                elif method == 'notifications/initialized':
                    self.respond(status=202); return
                elif method == 'tools/list':
                    response['result'] = {'tools': [{'name': 'rdc_system_status', 'inputSchema': {'type': 'object'}}]}
                elif method == 'tools/call':
                    response['result'] = {'content': [], 'structuredContent': {'ok': True, 'device_id': 'device-test'}}
                else:
                    response['error'] = {'code': -32601, 'message': 'Unknown fixture method'}
                self.respond(response, session=method == 'initialize')
            def do_GET(self):
                self.respond(status=405)
            def do_DELETE(self):
                delete_started.set()
                release_delete.wait(5)
                try: self.respond(status=204)
                except (BrokenPipeError, ConnectionResetError): pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), LegacyWorker)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        async def run():
            paired = config(worker_url=f'http://127.0.0.1:{server.server_port}/mcp', tool_timeout=.1)
            # A stalled DELETE must finish from its own socket deadline. This
            # outer deadline detects a transport that would otherwise hang.
            with anyio.fail_after(3):
                async with _worker_session(paired, 'fixture-agent-token'):
                    pass
        try:
            anyio.run(run)
            self.assertTrue(delete_started.is_set())
        finally:
            release_delete.set(); server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_real_mcp_worker_reconnect_and_result_retry_do_not_repeat_or_close_worker(self):
        from tests.test_proxy import BrowserWorkerFixture, running_worker

        class Worker(BrowserWorkerFixture):
            def catalog(self):
                return [{'name':'rdc_system_status','description':'Fixture identity',
                         'inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
                        {'name':'rdc_fixture_write','description':'Fixture write','inputSchema':CATALOG['rdc_fixture_write']}]
            def call(self, name, arguments):
                if name == 'rdc_system_status':
                    return {'ok':True,'device_id':'device-test'}
                self.calls.append((name, arguments)); self.sources['result'] = arguments['text']
                return {'ok':True,'text':arguments['text']}

        worker = Worker()
        agent_token = 'agent-only-' + 'a' * 48
        with tempfile.TemporaryDirectory() as directory, running_worker(worker, agent_token) as url:
            state = Path(directory) / 'state'; state.mkdir(mode=0o700)
            (state / 'agent-token').write_text(agent_token); (state / 'agent-token').chmod(0o600)
            cfg = Path(directory) / 'relay.json'
            cfg.write_text(json.dumps({'gateway_url':'https://relay.example.test','device_id':'device-test',
                'device_key':SECRET,'sites_service_token':SITE_SECRET,'worker_url':url+'/mcp'})); cfg.chmod(0o600)
            uploads = []; claimed = False
            original_client = httpx2.AsyncClient

            async def run():
                stop = anyio.Event()
                async def handler(request):
                    nonlocal claimed
                    self.assertNotIn(agent_token, request.content.decode())
                    self.assertEqual(request.headers['X-RDC-Device-Key'], SECRET)
                    self.assertEqual(request.headers['OAI-Sites-Authorization'], 'Bearer '+SITE_SECRET)
                    self.assertNotIn('authorization', request.headers)
                    body = json.loads(request.content)
                    if request.url.path.endswith('/device/poll'):
                        now = int(time.time()*1000)
                        op = None
                        if body['claim'] and not claimed:
                            claimed = True; item = operation()
                            op = {key:getattr(item,key) for key in ('operation_id','claim_id','request_json','request_sha256','expires_at_ms')}
                        return httpx2.Response(200,json={'ok':True,'device_id':'device-test','server_time_ms':now,'operation':op,'poll_after_ms':250})
                    uploads.append(body)
                    if len(uploads)==1: return httpx2.Response(503,json={'error':'temporary fixture outage'})
                    stop.set()
                    return httpx2.Response(200,json={'ok':True,'operation_id':body['operation_id'],'status':'completed','duplicate':True})
                def client_factory(*args, **kwargs):
                    if 'Authorization' not in kwargs.get('headers', {}):
                        kwargs['transport'] = httpx2.MockTransport(handler)
                    return original_client(*args, **kwargs)
                with patch('rdc.relay.httpx2.AsyncClient', side_effect=client_factory):
                    with anyio.fail_after(10):
                        await run_relay(cfg, state, stop_event=stop)
            anyio.run(run)
            self.assertEqual(worker.calls, [('rdc_fixture_write', {'text':'hello'})])
            self.assertEqual(worker.sources['result'], 'hello')
            self.assertEqual(len(uploads), 2)
            self.assertEqual(uploads[0], uploads[1])
            self.assertFalse(worker.closed)
            self.assertFalse((state / 'owner-token').exists())
    def test_gateway_ack_and_body_limits_are_checked(self):
        async def handler(request):
            if request.url.path.endswith('/device/result'):
                return httpx2.Response(200, json={'ok':True,'operation_id':'wrong-operation','status':'completed'})
            return httpx2.Response(200, headers={'Content-Length':str(16*1024*1024+1)}, content=b'{}')
        async def run():
            async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as client:
                gateway = Gateway(config(), client)
                with self.assertRaises(RelayPermanentError): await gateway.poll()
                with self.assertRaises(RelayPermanentError): await gateway.submit(operation(), json.dumps(error_result('fixture','fixture')))
        anyio.run(run)


if __name__ == '__main__':
    unittest.main()

class RelayDiagnosticTests(RelayDurabilityTests):
    """Repeat durability contracts with a failing observer as well as outcome checks."""
    def setUp(self):
        super().setUp()
        self.events = []
        class Recorder:
            def record(inner, component, event, tool=None):
                self.events.append((component, event, tool))
        self.pump = RelayPump(config(), self.journal, self.gateway, self.worker, CATALOG, diagnostics=Recorder())

    def test_unknown_and_upload_retry_are_distinct_and_never_replay(self):
        self.worker.error = RuntimeError('synthetic-password /private')
        self.gateway.failures = 1
        async def run():
            await self.pump.handle(operation())
            with self.assertRaises(RelayTransientError): await self.pump.flush()
            await self.pump.flush()
        anyio.run(run)
        names = [row[1] for row in self.events]
        self.assertIn('outcome_unknown', names)
        self.assertIn('result_upload_retry', names)
        self.assertIn('result_uploaded', names)
        self.assertEqual(len(self.worker.calls), 1)
        self.assertNotIn('synthetic-password', json.dumps(self.events))

    def test_broken_reporter_cannot_change_delivery_or_reexecute(self):
        class Broken:
            def record(self, *args): raise RuntimeError('secret')
        self.pump.diagnostics = Broken()
        async def run():
            await self.pump.handle(operation())
            await self.pump.flush()
            await self.pump.handle(operation())
        anyio.run(run)
        self.assertEqual(len(self.worker.calls), 1)
        self.assertEqual(len(self.gateway.results), 1)

    def test_reconnection_report_requires_a_successful_authenticated_poll(self):
        events = []
        class Recorder:
            def __init__(self, *args): pass
            def record(self, component, event, tool=None): events.append(event)
            def close(self): pass
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory); state.chmod(0o700)
            (state / 'agent-token').write_text('agent-fixture-' + 'a' * 48)
            (state / 'agent-token').chmod(0o600)
            cfg = state / 'config.json'
            cfg.write_text(json.dumps({'gateway_url': 'https://relay.example.test', 'device_id': 'device-test',
                'device_key': SECRET, 'sites_service_token': SITE_SECRET})); cfg.chmod(0o600)
            sessions = 0
            @asynccontextmanager
            async def session(*args):
                nonlocal sessions
                sessions += 1
                if sessions <= 2: raise RelayTransientError('synthetic-password')
                yield FakeWorker(), CATALOG
            async def run():
                stop = anyio.Event()
                class GatewayFixture(FakeGateway):
                    async def poll(inner, claim=True):
                        self.assertNotIn('reconnected', events)
                        stop.set()
                        return None, .25
                async def instant_sleep(seconds): pass
                with patch('rdc.relay.Diagnostics', Recorder), patch('rdc.relay._worker_session', session), \
                        patch('rdc.relay.Gateway', return_value=GatewayFixture()), patch('rdc.relay.anyio.sleep', instant_sleep):
                    await run_relay(cfg, state, stop_event=stop)
            anyio.run(run)
        self.assertEqual(events.count('connection_interrupted'), 2)
        self.assertEqual(events.count('reconnect_attempt'), 2)
        self.assertEqual(events.count('reconnected'), 1)
        self.assertGreater(events.index('reconnected'), events.index('reconnect_attempt'))


class RelayUnsupportedDiagnosticTests(RelayDurabilityTests):
    def setUp(self):
        super().setUp()
        from rdc.diagnostics import Diagnostics
        self.capability = patch.object(Diagnostics, '_supported', return_value=False)
        self.capability.start()
        self.diagnostics = Diagnostics(self.directory.name)
        self.pump.diagnostics = self.diagnostics

    def tearDown(self):
        self.diagnostics.close()
        self.capability.stop()
        super().tearDown()
