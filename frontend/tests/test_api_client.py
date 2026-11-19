import json
import unittest
from unittest.mock import patch

from frontend.api.client import ApiClient


class ResponseStub:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({"ok": True}).encode("utf-8")


class ApiClientTests(unittest.TestCase):
    def test_request_sends_bearer_token(self):
        client = ApiClient("http://127.0.0.1:8000")
        client.set_access_token("test-token")

        with patch(
            "frontend.api.client.urllib.request.urlopen",
            return_value=ResponseStub(),
        ) as urlopen:
            result = client.request("/api/historial-lecturas")

        request = urlopen.call_args.args[0]
        self.assertEqual(result, {"ok": True})
        self.assertEqual(
            request.get_header("Authorization"),
            "Bearer test-token",
        )

    def test_request_without_token_has_no_authorization_header(self):
        client = ApiClient("http://127.0.0.1:8000")

        with patch(
            "frontend.api.client.urllib.request.urlopen",
            return_value=ResponseStub(),
        ) as urlopen:
            client.request("/api/historial-lecturas")

        request = urlopen.call_args.args[0]
        self.assertIsNone(request.get_header("Authorization"))
