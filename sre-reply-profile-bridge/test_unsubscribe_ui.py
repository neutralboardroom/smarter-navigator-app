import os
import unittest
from unittest.mock import patch

os.environ.setdefault("FN_UNSUBSCRIBE_SIGNING_SECRET", "unit-test-secret-only")

import app as candidate
import unsubscribe_ui


class UnsubscribeUiTests(unittest.TestCase):
    def test_visible_get_is_confirmation_only(self):
        token = candidate.legacy.make_unsubscribe_token("test@example.com")
        with patch.object(candidate.legacy, "persist_unsubscribe") as persist:
            response = unsubscribe_ui.visible_unsubscribe_v253(token)
        body = response.body.decode("utf-8")
        self.assertIn("You have not been unsubscribed yet.", body)
        self.assertIn("Confirm unsubscribe", body)
        self.assertIn("email-security scanners", body)
        self.assertIn('method="post"', body)
        persist.assert_not_called()

    def test_rfc_one_click_route_remains_registered(self):
        matches = []
        for route in candidate.legacy.app.router.routes:
            path = getattr(route, "path", "")
            methods = set(getattr(route, "methods", set()) or set())
            if path == "/unsubscribe/one-click/{token}" and "POST" in methods:
                matches.append(route)
        self.assertEqual(len(matches), 1)

    def test_visible_routes_are_replaced_once(self):
        get_routes = []
        post_routes = []
        for route in candidate.legacy.app.router.routes:
            path = getattr(route, "path", "")
            methods = set(getattr(route, "methods", set()) or set())
            if path == "/unsubscribe/{token}" and "GET" in methods:
                get_routes.append(route)
            if path == "/unsubscribe/confirm/{token}" and "POST" in methods:
                post_routes.append(route)
        self.assertEqual(len(get_routes), 1)
        self.assertEqual(len(post_routes), 1)


if __name__ == "__main__":
    unittest.main()
