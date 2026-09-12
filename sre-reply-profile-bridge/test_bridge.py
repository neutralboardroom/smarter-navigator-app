import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import app as bridge


class BridgeTemplateTests(unittest.TestCase):
    def test_replaces_generic_membership_link_and_greeting(self):
        body = "Hi {{FirstName}},\n\nReview membership:\nhttps://franklinnavigator.com/business-membership/\n"
        result = bridge.exact_profile_only_body(body)
        self.assertIn("Hi {{Outreach_Greeting}},", result)
        self.assertIn("{{Profile_URL}}", result)
        self.assertNotIn("business-membership", result)
        self.assertEqual(result.count("{{Profile_URL}}"), 1)

    def test_adds_profile_link_if_missing(self):
        result = bridge.exact_profile_only_body("Hello {{FirstName}},\n\nA short note.")
        self.assertIn("Hi {{Outreach_Greeting}},", result)
        self.assertEqual(result.count("{{Profile_URL}}"), 1)

    def test_blocks_other_franklin_destination(self):
        with self.assertRaises(RuntimeError):
            bridge.exact_profile_only_body(
                "Hi {{FirstName}},\nhttps://franklinnavigator.com/community/"
            )


if __name__ == "__main__":
    unittest.main()
