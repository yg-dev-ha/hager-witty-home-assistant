"""Offline regression tests; no Hager account and no charger commands."""
import asyncio
import importlib
import json
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import AsyncMock

# Load the transport in isolation, without importing Home Assistant's setup.
ROOT = Path(__file__).resolve().parents[1]
pkg = types.ModuleType('witty_under_test')
pkg.__path__ = [str(ROOT / 'custom_components/hager_witty')]
sys.modules[pkg.__name__] = pkg
api = importlib.import_module('witty_under_test.api')
models = importlib.import_module('witty_under_test.models')

class Response:
    def __init__(self, status, payload):
        self.status, self.payload = status, payload
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        pass
    async def text(self):
        return json.dumps(self.payload)
    async def json(self, **kwargs):
        return self.payload

class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        status, payload = self.responses.pop(0)
        return Response(status, payload)

class OAuthTests(unittest.IsolatedAsyncioTestCase):
    def client(self, session, **kwargs):
        return api.HagerWittyApi(session, access_token='old', refresh_token='refresh',
            expires_at=time.time()+3600, token_endpoint='https://example.test/token', **kwargs)

    def test_callback_state_and_destination(self):
        callback = api.REDIRECT_URI + '?code=abc&state=expected'
        self.assertEqual(api.parse_authorization_input(callback, 'expected'), 'abc')
        self.assertEqual(api.parse_authorization_input('raw-code', 'expected'), 'raw-code')
        self.assertEqual(api.parse_authorization_input('padded-code==', 'expected'), 'padded-code==')
        for bad in [api.REDIRECT_URI+'?code=abc', callback+'&state=other',
                    callback+'&code=other', callback.replace('expected','wrong'),
                    'https://example.test/callback?code=abc&state=expected']:
            with self.subTest(bad=bad), self.assertRaises(api.WittyAuthError):
                api.parse_authorization_input(bad, 'expected')

    async def test_rejection_rotates_persists_and_retries(self):
        session = Session((401, {'secret':'hidden'}),
            (200, {'access_token':'new','refresh_token':'rotated','expires_in':3600}),
            (200, {'Device':{'Id':'charger'}}))
        saved = AsyncMock()
        client = self.client(session, token_update_callback=saved)
        await client.async_get_user_data()
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(session.calls[-1][2]['headers']['Authorization'], 'bearer new')
        self.assertEqual(saved.call_args.args[0]['refresh_token'], 'rotated')
        self.assertTrue(all(c[2]['allow_redirects'] is False for c in session.calls))

    async def test_concurrent_forced_refresh_rotates_once(self):
        session = Session((200, {'access_token':'new','refresh_token':'rotated','expires_in':3600}))
        client = self.client(session)
        await asyncio.gather(*(client.async_refresh_tokens(force=True, rejected_access_token='old') for _ in range(5)))
        self.assertEqual(len(session.calls), 1)

    async def test_invalid_grant_requires_reauth_without_leaking_body(self):
        client = self.client(Session((400, {'error':'invalid_grant','secret':'do-not-log'})))
        with self.assertRaises(api.WittyAuthError) as ctx:
            await client.async_refresh_tokens(force=True)
        self.assertNotIn('do-not-log', str(ctx.exception))
        self.assertNotIn('do-not-log', str(ctx.exception.__cause__))

    async def test_gateway_auth_error_is_transient(self):
        client = self.client(Session((403, {'error':'policy_denied'})))
        with self.assertRaises(api.WittyConnectionError):
            await client.async_refresh_tokens(force=True)

    async def test_persistent_resource_403_does_not_request_reauth(self):
        client = self.client(Session((403, {}), (200, {'access_token':'new','expires_in':3600}), (403, {})))
        with self.assertRaises(api.WittyApiError):
            await client.async_get_user_data()
        self.assertEqual(client.token_data()['refresh_token'], 'refresh')

    async def test_command_400_is_not_retried_or_logged(self):
        session = Session((400, {'secret':'do-not-log'}))
        with self.assertRaises(api.WittyApiError) as ctx:
            await self.client(session).async_control('a/b', 'stop')
        self.assertEqual(len(session.calls), 1)
        self.assertTrue(session.calls[0][1].endswith('/a%2Fb/stop-charging'))
        self.assertNotIn('do-not-log', str(ctx.exception))

    async def test_malformed_refresh_preserves_credentials(self):
        for payload in [{}, {'access_token':'new','expires_in':'invalid'}, {'access_token':'new','expires_in':0}]:
            client = self.client(Session((200, payload)))
            before = client.token_data()
            with self.subTest(payload=payload), self.assertRaises(api.WittyApiError):
                await client.async_refresh_tokens(force=True)
            self.assertEqual(before, client.token_data())

    async def test_bad_device_payload_rejected(self):
        for payload in [[], {}, {'Device':{}}, {'Device':{'Name':'not-an-id'}}]:
            with self.subTest(payload=payload), self.assertRaises(api.WittyApiError):
                await self.client(Session((200, payload))).async_get_user_data()

    async def test_redirect_is_not_followed(self):
        with self.assertRaises(api.WittyApiError):
            await self.client(Session((302, {}))).async_get_user_data()

class StateTests(unittest.TestCase):
    def test_observed_and_unknown_states(self):
        for code, expected, controllable in [(2006,False,False),(2007,False,True),(2009,True,True),(2008,None,False),(None,None,False),('bad',None,False)]:
            data = {'Device':{'StatusEvent':{'Type':code}, 'ChargingSession':{'EndDate':None}}}
            with self.subTest(code=code):
                self.assertIs(models.is_charging(data), expected)
                self.assertEqual(models.is_charge_control_available(data), controllable)

    def test_camel_case_payload(self):
        self.assertTrue(models.is_charging({'device':{'statusEvent':{'type':'2009'}}}))

if __name__ == '__main__':
    unittest.main()
