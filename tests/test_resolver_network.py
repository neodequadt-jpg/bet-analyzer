"""Unit tests for resolver network functions (_get_session, _fetch_events_for_date) with mocking."""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock, call
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scoring.resolver import _get_session, _fetch_events_for_date, THESPORTSDB


class TestGetSession(unittest.TestCase):
    def test_session_without_proxy(self):
        """_get_session should create a Session without touching .proxies when no env."""
        class FakeSession:
            def __init__(self):
                self.proxies = {}

        with patch.dict(os.environ, clear=True):
            with patch('scoring.resolver.requests.Session', FakeSession) as mock_cls:
                session = _get_session()
                # proxies remains default empty dict, code did not assign
                self.assertEqual(session.proxies, {})
                self.assertIsInstance(session, FakeSession)

    def test_session_with_http_proxy(self):
        """_get_session should set both http and https proxies when HTTP_PROXY is set."""
        with patch.dict(os.environ, {'HTTP_PROXY': 'http://proxy.example.com:8080'}):
            with patch('scoring.resolver.requests.Session') as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session
                
                session = _get_session()
                
                mock_session_class.assert_called_once()
                self.assertEqual(mock_session.proxies, {
                    'http': 'http://proxy.example.com:8080',
                    'https': 'http://proxy.example.com:8080'
                })
                self.assertEqual(session, mock_session)

    def test_session_with_https_proxy(self):
        """_get_session should prefer HTTPS_PROXY over HTTP_PROXY."""
        with patch.dict(os.environ, {
            'HTTPS_PROXY': 'https://secureproxy.example.com:8443',
            'HTTP_PROXY': 'http://proxy.example.com:8080'
        }):
            with patch('scoring.resolver.requests.Session') as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session
                
                session = _get_session()
                
                mock_session_class.assert_called_once()
                self.assertEqual(mock_session.proxies, {
                    'http': 'https://secureproxy.example.com:8443',
                    'https': 'https://secureproxy.example.com:8443'
                })
                self.assertEqual(session, mock_session)

    def test_session_proxy_only_https(self):
        """_get_session should use HTTPS_PROXY when only it is set."""
        with patch.dict(os.environ, {'HTTPS_PROXY': 'https://proxy.example.com:443'}):
            with patch('scoring.resolver.requests.Session') as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session
                
                session = _get_session()
                
                mock_session_class.assert_called_once()
                self.assertEqual(mock_session.proxies, {
                    'http': 'https://proxy.example.com:443',
                    'https': 'https://proxy.example.com:443'
                })
                self.assertEqual(session, mock_session)


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
    
    def test_fetch_events_with_proxy_integration(self):
        """Integration test: _get_session creates session with proxy, then _fetch_events_for_date uses it."""
        with patch.dict(os.environ, {'HTTPS_PROXY': 'https://proxy.example.com:443'}):
            with patch('scoring.resolver.requests.Session') as mock_session_class:
                mock_session = MagicMock()
                mock_response = MagicMock()
                mock_session_class.return_value = mock_session
                mock_session.get.return_value = mock_response
                
                # Create session with proxy
                session = _get_session()
                
                # Verify proxy was set
                self.assertEqual(session.proxies, {
                    'http': 'https://proxy.example.com:443',
                    'https': 'https://proxy.example.com:443'
                })
                
                # Now use the session to fetch events
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