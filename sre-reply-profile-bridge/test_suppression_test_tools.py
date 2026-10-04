import os
import unittest
from unittest.mock import patch

os.environ.setdefault("FN_UNSUBSCRIBE_SIGNING_SECRET", "unit-test-secret-only")
os.environ.setdefault("FN_SUPPRESSION_TEST_EMAIL", "reachrgnow1@gmail.com")
os.environ.setdefault("FN_SUPPRESSION_TEST_SEND_ON_STARTUP", "false")
os.environ.setdefault("FN_SUPPRESSION_TEST_CHECK_ON_STARTUP", "false")

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

    def test_non_allowlisted_test_address_fails_closed(self):
        with patch.object(tools, "SUPPRESSION_TEST_EMAIL", "someoneelse@example.com"):
            with self.assertRaises(RuntimeError):
                tools._test_email()


if __name__ == "__main__":
    unittest.main()
