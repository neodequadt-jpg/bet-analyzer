"""Unit tests for resolver network functions (_get_session, _fetch_events_for_date) with mocking."""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock, call
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scoring.resolver import _get_session, _fetch_events_for_date, THESPORTSDB


class TestGetSession(unittest.TestCase):
    """_get_session MUST ignore env proxies (ARTEM-PRETHEORY E1)."""

    def test_session_without_proxy(self):
        class FakeSession:
            def __init__(self):
                self.proxies = {}

        with patch.dict(os.environ, clear=True):
            with patch('scoring.resolver.requests.Session', FakeSession):
                session = _get_session()
                self.assertEqual(session.proxies, {})
                self.assertIsInstance(session, FakeSession)

    def test_session_ignores_http_proxy(self):
        """HTTP_PROXY in env MUST NOT be picked up."""
        with patch.dict(os.environ, {'HTTP_PROXY': 'http://proxy.example.com:8080'}, clear=True):
            with patch('scoring.resolver.requests.Session') as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session
                _get_session()
                mock_session_class.assert_called_once()
                # proxies not assigned by our code — MagicMock default attr is not dict,
                # so assert trust_env False and that .proxies was never set
                self.assertFalse(mock_session.trust_env)

    def test_session_ignores_https_proxy(self):
        with patch.dict(os.environ, {
            'HTTPS_PROXY': 'https://secureproxy.example.com:8443',
            'HTTP_PROXY': 'http://proxy.example.com:8080',
        }, clear=True):
            with patch('scoring.resolver.requests.Session') as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session
                _get_session()
                self.assertFalse(mock_session.trust_env)

    def test_session_trust_env_false(self):
        """Key invariant: trust_env=False, so requests lib itself also ignores env."""
        with patch.dict(os.environ, {'HTTPS_PROXY': 'https://proxy.example.com:443'}, clear=True):
            with patch('scoring.resolver.requests.Session') as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session
                _get_session()
                self.assertIs(mock_session.trust_env, False)


class TestFetchEventsForDate(unittest.TestCase):
    def setUp(self):
        self.mock_session = MagicMock()
        self.mock_response = MagicMock()
        self.mock_session.get.return_value = self.mock_response

    def test_successful_fetch(self):
        """_fetch_events_for_date should return events list on successful API response."""
        mock_events = [
            {"strHomeTeam": "Slovakia", "strAwayTeam": "Moldova", "intHomeScore": "2", "intAwayScore": "1"},
            {"strHomeTeam": "Germany", "strAwayTeam": "Greece", "intHomeScore": "0", "intAwayScore": "0"}
        ]
        self.mock_response.status_code = 200
        self.mock_response.json.return_value = {"events": mock_events}
        
        result = _fetch_events_for_date(self.mock_session, "2026-09-26")
        
        self.mock_session.get.assert_called_once_with(
            f"{THESPORTSDB}/eventsday.php?d=2026-09-26&s=Soccer",
            timeout=20
        )
        self.assertEqual(result, mock_events)

    def test_successful_fetch_empty_events(self):
        """_fetch_events_for_date should return empty list when events is empty."""
        self.mock_response.status_code = 200
        self.mock_response.json.return_value = {"events": []}
        
        result = _fetch_events_for_date(self.mock_session, "2026-09-26")
        
        self.assertEqual(result, [])

    def test_successful_fetch_no_events_key(self):
        """_fetch_events_for_date should return empty list when events key is missing."""
        self.mock_response.status_code = 200
        self.mock_response.json.return_value = {}
        
        result = _fetch_events_for_date(self.mock_session, "2026-09-26")
        
        self.assertEqual(result, [])

    def test_non_200_status(self):
        """_fetch_events_for_date should return empty list on non-200 status code."""
        self.mock_response.status_code = 404
        self.mock_response.json.side_effect = ValueError("No JSON")
        
        result = _fetch_events_for_date(self.mock_session, "2026-09-26")
        
        self.assertEqual(result, [])

    def test_request_exception(self):
        """_fetch_events_for_date should return empty list and print on request exception."""
        self.mock_session.get.side_effect = Exception("Connection failed")
        
        with patch('builtins.print') as mock_print:
            result = _fetch_events_for_date(self.mock_session, "2026-09-26")
        
        self.mock_session.get.assert_called_once_with(
            f"{THESPORTSDB}/eventsday.php?d=2026-09-26&s=Soccer",
            timeout=20
        )
        mock_print.assert_called_once_with("[resolver] fetch 2026-09-26: Connection failed")
        self.assertEqual(result, [])

    def test_json_decode_exception(self):
        """_fetch_events_for_date should return empty list on JSON decode error."""
        self.mock_response.status_code = 200
        self.mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        
        with patch('builtins.print') as mock_print:
            result = _fetch_events_for_date(self.mock_session, "2026-09-26")
        
        self.assertEqual(result, [])

    def test_timeout_handling(self):
        """_fetch_events_for_date should handle timeout exceptions gracefully."""
        self.mock_session.get.side_effect = TimeoutError("Request timed out")
        
        with patch('builtins.print') as mock_print:
            result = _fetch_events_for_date(self.mock_session, "2026-09-26")
        
        mock_print.assert_called_once_with("[resolver] fetch 2026-09-26: Request timed out")
        self.assertEqual(result, [])

    def test_invalid_date_format(self):
        """_fetch_events_for_date should work with any date string format."""
        self.mock_response.status_code = 200
        self.mock_response.json.return_value = {"events": []}
        
        result = _fetch_events_for_date(self.mock_session, "2026-01-01")
        
        self.mock_session.get.assert_called_once_with(
            f"{THESPORTSDB}/eventsday.php?d=2026-01-01&s=Soccer",
            timeout=20
        )
        self.assertEqual(result, [])


class TestIntegrationWithSession(unittest.TestCase):
    """Integration tests that mock both session creation and its usage."""
    
    def test_fetch_events_with_env_proxy_ignored(self):
        """Integration: env proxy present, session still fetches normally (trust_env=False)."""
        with patch.dict(os.environ, {'HTTPS_PROXY': 'https://proxy.example.com:443'}, clear=True):
            with patch('scoring.resolver.requests.Session') as mock_session_class:
                mock_session = MagicMock()
                mock_response = MagicMock()
                mock_session_class.return_value = mock_session
                mock_session.get.return_value = mock_response

                session = _get_session()
                self.assertFalse(session.trust_env)

                mock_response.status_code = 200
                mock_response.json.return_value = {"events": [{"test": "data"}]}

                result = _fetch_events_for_date(session, "2026-09-26")

                mock_session.get.assert_called_once_with(
                    f"{THESPORTSDB}/eventsday.php?d=2026-09-26&s=Soccer",
                    timeout=20
                )
                self.assertEqual(result, [{"test": "data"}])

    def test_multiple_calls_reuse_session(self):
        """Test that multiple _fetch_events_for_date calls use the same session."""
        mock_session = MagicMock()

        resp1 = MagicMock(status_code=200)
        resp1.json.return_value = {"events": [{"first": "call"}]}
        resp2 = MagicMock(status_code=200)
        resp2.json.return_value = {"events": [{"second": "call"}]}
        mock_session.get.side_effect = [resp1, resp2]

        result1 = _fetch_events_for_date(mock_session, "2026-09-26")
        result2 = _fetch_events_for_date(mock_session, "2026-09-27")

        self.assertEqual(mock_session.get.call_count, 2)
        url1 = mock_session.get.call_args_list[0][0][0]
        url2 = mock_session.get.call_args_list[1][0][0]
        self.assertIn("2026-09-26", url1)
        self.assertIn("2026-09-27", url2)
        self.assertEqual(result1, [{"first": "call"}])
        self.assertEqual(result2, [{"second": "call"}])


if __name__ == "__main__":
    unittest.main()