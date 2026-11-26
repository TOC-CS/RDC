"""Exercise actual persistent HTTP connections, without device operations."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import threading
import unittest
from types import SimpleNamespace
from rdc.mobile import Mobile, MAX_RESPONSE_BYTES
from rdc.errors import RDCError

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *_args):
        pass
    def _handle(self):
        server=self.server
        if self.command=="POST":
            self.rfile.read(int(self.headers.get("Content-Length",0)))
        server.requests.append((self.command,self.path))
        if self.path.endswith("/drop"):
            self.close_connection=True
            self.connection.shutdown(socket.SHUT_RDWR)
            return
        if self.path.endswith("/redirect"):
            self.send_response(307)
            self.send_header("Location","/driver/redirected")
            self.send_header("Content-Length","0")
            self.end_headers()
            return
        if self.path.endswith("/truncated"):
            data=b'{"value":{"ok":true}}'
            self.send_response(200)
            self.send_header("Content-Length",str(len(data)+8))
            self.end_headers()
            self.wfile.write(data)
            self.wfile.flush()
            self.close_connection=True
            return
        if self.path.endswith("/ambiguous-framing"):
            self.send_response(200)
            self.send_header("Content-Length","4")
            self.send_header("Transfer-Encoding","chunked")
            self.end_headers()
            self.wfile.write(b'14\r\n{"value":{"ok":true}}\r\n0\r\n\r\n')
            self.close_connection=True
            return
        if self.path.endswith("/invalid-json"):
            data=b'invalid'
            self.send_response(200)
            self.send_header("Content-Length",str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        status=404 if self.path.endswith("/expired") else 200
        data=json.dumps({"value":{"error":"invalid session id"}} if status==404 else {"value":{"ok":True}}).encode()
        self.send_response(status)
        if self.path.endswith("/oversize"):
            self.send_header("Content-Length",str(MAX_RESPONSE_BYTES+1))
            self.end_headers()
            self.close_connection=True
            return
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    do_GET=do_POST=do_DELETE=_handle
class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self):
        self.accepted=0
        self.requests=[]
        self.connections=[]
        super().__init__(("127.0.0.1",0),Handler)
    def get_request(self):
        sock,addr=super().get_request()
        self.accepted+=1
        self.connections.append(sock)
        return sock,addr

class PersistentNativeHTTPTests(unittest.TestCase):
    def setUp(self):
        self.server=Server()
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.profile={"platformName":"iOS","automationName":"XCUITest",
                      "endpoint":"http://127.0.0.1:%s/driver"%self.server.server_port,
                      "capabilities":{"appium:udid":"fixture-device","appium:bundleId":"org.example.fixture"}}
        self.mobile=Mobile(SimpleNamespace(mobile_profiles={"fixture":self.profile}))
    def tearDown(self):
        self.mobile.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
    def request(self,path="/status",method="GET",body=None):
        return self.mobile._http(self.profile,method,path,body,timeout=2)
    def test_reuses_exact_endpoint_connection_without_replay(self):
        for i in range(3):
            self.assertEqual(self.request(),{"ok":True})
        self.assertEqual(self.server.accepted,1)
        self.assertEqual(self.server.requests,[("GET","/driver/status")]*3)
    def test_lost_mutation_response_never_retried(self):
        self.request()
        with self.assertRaises(RDCError) as ctx:
            self.request("/drop","POST",{"fixture":1})
        self.assertEqual(ctx.exception.code,"mobile_unavailable")
        self.assertEqual(self.server.requests.count(("POST","/driver/drop")),1)
        self.assertEqual(self.request(),{"ok":True})
        self.assertEqual(self.server.accepted,2)
    def test_redirect_not_followed(self):
        with self.assertRaises(RDCError) as ctx:
            self.request("/redirect","POST",{})
        self.assertEqual(ctx.exception.code,"mobile_driver_error")
        self.assertEqual(self.server.requests,[("POST","/driver/redirect")])
    def test_invalid_session_mapping_preserved(self):
        with self.assertRaises(RDCError) as ctx:self.request("/expired")
        self.assertEqual(ctx.exception.code,"mobile_session_gone")
    def test_oversize_header_refused_without_waiting_for_body(self):
        with self.assertRaises(RDCError) as ctx:self.request("/oversize")
        self.assertEqual(ctx.exception.code,"output_limit")
    def test_different_configured_origins_have_separate_connections(self):
        other=Server()
        thread=threading.Thread(target=other.serve_forever,daemon=True);thread.start()
        try:
            self.request()
            p={**self.profile,"endpoint":"http://127.0.0.1:%s/driver"%other.server_port}
            self.assertEqual(self.mobile._http(p,"GET","/status",timeout=2),{"ok":True})
            self.request()
            self.assertEqual(self.server.accepted,1)
            self.assertEqual(other.accepted,1)
        finally:other.shutdown();other.server_close();thread.join(timeout=3)
    def test_adapter_close_releases_reused_connections(self):
        self.request()
        self.mobile.close()
        self.assertFalse(self.mobile._native_http_connections)
    def test_truncated_valid_json_is_never_accepted_as_complete(self):
        with self.assertRaises(RDCError) as ctx:self.request("/truncated","POST",{})
        self.assertEqual(ctx.exception.code,"mobile_unavailable")
        self.assertEqual(self.server.requests.count(("POST","/driver/truncated")),1)
        self.assertEqual(self.request(),{"ok":True})
        self.assertEqual(self.server.accepted,2)
    def test_ambiguous_message_framing_rejected(self):
        with self.assertRaises(RDCError) as ctx:self.request("/ambiguous-framing")
        self.assertEqual(ctx.exception.code,"mobile_protocol_error")
    def test_malformed_json_releases_connection_before_next_request(self):
        with self.assertRaises(RDCError) as ctx:self.request("/invalid-json")
        self.assertEqual(ctx.exception.code,"mobile_protocol_error")
        self.assertFalse(self.mobile._native_http_connections)
        self.request()
        self.assertEqual(self.server.accepted,2)

    def test_closed_session_does_not_reuse_socket_from_restarted_driver(self):
        self.assertEqual(self.request(),{"ok":True})
        self.mobile._destroy({"profile":"fixture","driver_id":"first-session"})
        # A service restart closes its accepted streams. Its replacement can
        # listen on the same endpoint, but cannot recover the previous socket.
        for connection in list(self.server.connections):
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
        try:
            value=self.request("/new-session","POST",{})
        except RDCError as exc:
            self.fail("A completed session retained a stale socket: "+exc.code)
        self.assertEqual(value,{"ok":True})
        self.assertEqual(self.server.requests.count(("POST","/driver/new-session")),1)
        self.assertEqual(self.server.accepted,2)
