import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("FN_UNSUBSCRIBE_SIGNING_SECRET", "unit-test-secret-only")
os.environ.setdefault("FN_SUPPRESSION_TEST_EMAIL", "reachrgnow1@gmail.com")
os.environ.setdefault("FN_SUPPRESSION_TEST_SEND_ON_STARTUP", "false")
os.environ.setdefault("FN_SUPPRESSION_TEST_CHECK_ON_STARTUP", "false")
os.environ.setdefault("FN_SUPPRESSION_TEST_RESTORE_ON_STARTUP", "false")
os.environ.setdefault("FN_SUPPRESSION_TEST_LEAN_COPY", "false")

import app
import suppression_test_tools as tools


class SuppressionTestHarnessTests(unittest.TestCase):
    def test_test_address_is_isolated_from_owner_address(self):
        self.assertEqual(tools._test_email(), "reachrgnow1@gmail.com")
        self.assertNotEqual(tools._test_email(), app.legacy.FN_OUTREACH_OWNER_TEST_EMAIL.lower())

    def test_send_path_targets_only_alt_email_and_uses_no_prospect_key(self):
        fake_client = object()
        with patch.object(tools, "_test_state", return_value={"senderWouldBlock": False}), \
             patch.object(tools.legacy, "_imap_connect") as imap_connect, \
             patch.object(tools.legacy, "_ledger_reserve", return_value=True), \
             patch.object(tools.legacy, "_ledger_mark_sent"), \
             patch.object(tools.legacy, "send_franklin_smtp_message", return_value="<suppression-test@test>") as send:
            imap_connect.return_value.__enter__.return_value = fake_client
            message_id = tools.send_suppression_test_preview_once()
        self.assertEqual(message_id, "<suppression-test@test>")
        args, kwargs = send.call_args
        self.assertEqual(args[0], "reachrgnow1@gmail.com")
        self.assertNotIn("outreach_key", kwargs)
        self.assertNotIn("bcc_email", kwargs)

    def test_lean_first_touch_is_owner_only_and_less_sales_heavy(self):
        fake_client = object()
        with patch.object(tools, "SUPPRESSION_TEST_LEAN_COPY", True), \
             patch.object(tools, "_test_state", return_value={"senderWouldBlock": False}), \
             patch.object(tools.legacy, "_imap_connect") as imap_connect, \
             patch.object(tools.legacy, "_ledger_reserve", return_value=True), \
             patch.object(tools.legacy, "_ledger_mark_sent"), \
             patch.object(tools.legacy, "send_franklin_smtp_message", return_value="<lean-test@test>") as send:
            imap_connect.return_value.__enter__.return_value = fake_client
            message_id = tools.send_suppression_test_preview_once()
        self.assertEqual(message_id, "<lean-test@test>")
        args, kwargs = send.call_args
        self.assertEqual(args[0], "reachrgnow1@gmail.com")
        self.assertIn("Hi Roger,", args[2])
        self.assertIn("increase your visibility in the Franklin community", args[2])
        self.assertNotIn("$35/year", args[2])
        self.assertNotIn("coupons, specials, sales", args[2])
        self.assertIn("commercial community-outreach email", args[2])
        self.assertIn("html_body", kwargs)
        self.assertNotIn("outreach_key", kwargs)

    def test_restore_deletes_only_exact_allowlisted_suppression_markers(self):
        client = MagicMock()
        client.select.return_value = ("OK", [b""])
        client.search.side_effect = [
            ("OK", [b"1 2"]),
            ("OK", [b""]),
        ]
        marker = b"X-Franklin-Suppression-Email: reachrgnow1@gmail.com\r\n\r\n"
        client.fetch.return_value = ("OK", [(b"header", marker)])
        client.store.return_value = ("OK", [b""])
        client.expunge.return_value = ("OK", [b"1", b"2"])

        before = {
            "email": "reachrgnow1@gmail.com",
            "suppressed": True,
            "domainSuppressed": False,
            "orgDomainHold": False,
            "orgDomainSuppression": False,
            "senderWouldBlock": True,
        }
        after = {
            "email": "reachrgnow1@gmail.com",
            "suppressed": False,
            "domainSuppressed": False,
            "orgDomainHold": False,
            "orgDomainSuppression": False,
            "senderWouldBlock": False,
        }
        with patch.object(tools, "_test_state", side_effect=[before, after]), \
             patch.object(tools.legacy, "_imap_connect") as imap_connect, \
             patch.object(tools.legacy, "_ensure_suppression_mailbox"):
            imap_connect.return_value.__enter__.return_value = client
            result = tools.restore_suppression_test_address_once()

        self.assertEqual(result["email"], "reachrgnow1@gmail.com")
        self.assertEqual(result["deletedMarkers"], 2)
        self.assertEqual(result["remainingMarkerIds"], [])
        self.assertTrue(result["testOnlyRestore"])
        expected_search = (
            None,
            "HEADER",
            "X-Franklin-Suppression-Email",
            "reachrgnow1@gmail.com",
        )
        self.assertEqual(client.search.call_count, 2)
        self.assertEqual(client.search.call_args_list[0].args, expected_search)
        self.assertEqual(client.search.call_args_list[1].args, expected_search)
        self.assertEqual(client.store.call_count, 2)
        for call in client.store.call_args_list:
            self.assertEqual(call.args[1], "+FLAGS.SILENT")
            self.assertEqual(call.args[2], "(\\Deleted)")
        client.expunge.assert_called_once()

    def test_restore_refuses_domain_suppression(self):
        with patch.object(
            tools,
            "_test_state",
            return_value={
                "email": "reachrgnow1@gmail.com",
                "suppressed": True,
                "domainSuppressed": True,
                "orgDomainHold": False,
                "orgDomainSuppression": False,
                "senderWouldBlock": True,
            },
        ), patch.object(tools.legacy, "_imap_connect") as imap_connect:
            result = tools.restore_suppression_test_address_once()
        self.assertIsNone(result)
        imap_connect.assert_not_called()

    def test_non_allowlisted_test_address_fails_closed(self):
        with patch.object(tools, "SUPPRESSION_TEST_EMAIL", "someoneelse@example.com"):
            with self.assertRaises(RuntimeError):
                tools._test_email()


if __name__ == "__main__":
    unittest.main()
