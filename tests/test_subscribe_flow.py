"""tests/test_subscribe_flow.py — Unit tests for Telegram Stars subscribe flow.

Covers: cmd_subscribe, _handle_pre_checkout, _handle_successful_payment.
unittest + unittest.mock only, no network. Mock tg_post / is_premium / grant_premium.
"""

import time
import unittest
from unittest.mock import patch, MagicMock, call

import tg_bot


class TestCmdSubscribeNonPremium(unittest.TestCase):
    """a) cmd_subscribe: not-premium → tg_post called with sendInvoice, XTR, amount=200"""

    @patch("tg_bot.tg_post")
    @patch("tg_bot.is_premium", return_value=False)
    def test_sends_invoice_when_not_premium(self, mock_is_premium, mock_tg_post):
        result = tg_bot.cmd_subscribe(12345)
        # dispatch expects "" when invoice is sent
        self.assertEqual(result, "")
        mock_tg_post.assert_called_once()
        args = mock_tg_post.call_args
        method = args[0][0]
        json_data = args[0][1]
        self.assertEqual(method, "sendInvoice")
        self.assertEqual(json_data["chat_id"], 12345)
        self.assertEqual(json_data["currency"], "XTR")
        self.assertEqual(json_data["prices"][0]["amount"], 200)
        self.assertNotIn("provider_token", json_data)
        # payload starts with premium_30d_
        self.assertTrue(json_data["payload"].startswith("premium_30d_"))


class TestCmdSubscribePremium(unittest.TestCase):
    """b) cmd_subscribe: premium → tg_post NOT called, answer contains 'активен'"""

    @patch("tg_bot.tg_post")
    @patch("tg_bot._load_subscribers")
    @patch("tg_bot.is_premium", return_value=True)
    def test_returns_active_message_when_premium(self, mock_is_premium, mock_load, mock_tg_post):
        mock_load.return_value = {
            "12345": {"expiry_ts": time.time() + 86400, "paid_ts": 0,
                      "total_stars": 200, "purchase_count": 1}
        }
        result = tg_bot.cmd_subscribe(12345)
        mock_tg_post.assert_not_called()
        self.assertIn("активен", result)


class TestHandlePreCheckoutValid(unittest.TestCase):
    """c) _handle_pre_checkout: valid payload → ok=True"""

    @patch("tg_bot.tg_post")
    def test_valid_payload_ok_true(self, mock_tg_post):
        pq = {
            "id": 42,
            "from": {"id": 12345},
            "invoice_payload": "premium_30d_12345_1700000000",
        }
        tg_bot._handle_pre_checkout(pq)
        mock_tg_post.assert_called_once_with("answerPreCheckoutQuery", {
            "pre_checkout_query_id": 42,
            "ok": True,
        })


class TestHandlePreCheckoutInvalid(unittest.TestCase):
    """d) _handle_pre_checkout: invalid payload → ok=False"""

    @patch("tg_bot.tg_post")
    def test_invalid_payload_ok_false(self, mock_tg_post):
        pq = {
            "id": 43,
            "from": {"id": 12345},
            "invoice_payload": "something_else",
        }
        tg_bot._handle_pre_checkout(pq)
        mock_tg_post.assert_called_once_with("answerPreCheckoutQuery", {
            "pre_checkout_query_id": 43,
            "ok": False,
        })


class TestHandleSuccessfulPaymentGrant(unittest.TestCase):
    """e) _handle_successful_payment: calls grant_premium(days=30, stars=200)"""

    @patch("tg_bot.send_message")
    @patch("tg_bot.grant_premium")
    def test_grant_premium_called(self, mock_grant, mock_send):
        msg = {
            "chat": {"id": 12345},
            "successful_payment": {
                "total_amount": 200,
                "invoice_payload": "premium_30d_12345_1700000000",
            },
        }
        tg_bot._handle_successful_payment(msg)
        mock_grant.assert_called_once_with(12345, days=30, stars=200)


class TestHandleSuccessfulPaymentMessage(unittest.TestCase):
    """f) _handle_successful_payment: send_message with 'активирован'"""

    @patch("tg_bot.send_message")
    @patch("tg_bot.grant_premium")
    def test_send_message_activated(self, mock_grant, mock_send):
        msg = {
            "chat": {"id": 12345},
            "successful_payment": {
                "total_amount": 200,
                "invoice_payload": "premium_30d_12345_1700000000",
            },
        }
        tg_bot._handle_successful_payment(msg)
        mock_send.assert_called_once()
        sent_text = mock_send.call_args[0][1]
        self.assertIn("активирован", sent_text)


if __name__ == "__main__":
    unittest.main()
