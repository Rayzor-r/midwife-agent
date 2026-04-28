# Testing Patterns

**Analysis Date:** 2026-04-28

## Test Framework

**Runner:**
- None. No test framework is installed or configured.
- No `pytest`, `unittest`, `nose`, or other test runner found in `requirements.txt`
- No `pytest.ini`, `setup.cfg`, `tox.ini`, or `pyproject.toml` with test configuration

**Assertion Library:**
- None.

**Run Commands:**
```bash
# No test commands defined.
# To add pytest, install it and run:
pytest                        # Run all tests
pytest -v                     # Verbose
pytest --cov=. --cov-report=term-missing  # Coverage
```

## Test File Organization

**Location:**
- No test files exist in the repository. No `tests/` directory, no `*_test.py` or `test_*.py` files.

**What would follow project style if tests were added:**
- Co-located alongside each integration module or in a top-level `tests/` directory
- Named `test_calendar_integration.py`, `test_gmail_integration.py`, `test_note_tidy.py`, `test_drive_integration.py`, `test_main.py`

## Test Structure

**Suite Organization:**
- Not established. No existing test suites.

**Patterns to follow when adding tests:**
```python
# Recommended pattern matching project style
import pytest
from unittest.mock import MagicMock, patch

class TestListEvents:
    def test_returns_formatted_events(self):
        ...

    def test_raises_runtime_error_on_http_error(self):
        ...
```

## Mocking

**Framework:**
- None currently in use. `unittest.mock` from the standard library is the appropriate choice given no test infrastructure exists.

**What to mock when tests are written:**

External Google API calls require mocking at the `googleapiclient.discovery.build` level:
```python
# Pattern for calendar_integration.py
from unittest.mock import MagicMock, patch

@patch("calendar_integration.build")
def test_list_events(mock_build):
    mock_svc = MagicMock()
    mock_build.return_value = mock_svc
    mock_svc.events().list().execute.return_value = {"items": [...]}
    ...
```

Anthropic API calls require mocking the `anthropic.Anthropic` or `anthropic.AsyncAnthropic` client:
```python
@patch("note_tidy.anthropic.Anthropic")
def test_tidy_note_text(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(type="text", text="tidied output")],
        model="claude-sonnet-4-5"
    )
    ...
```

**What to mock:**
- All `googleapiclient.discovery.build(...)` calls in `calendar_integration.py`, `gmail_integration.py`, `drive_integration.py`, `note_tidy.py`
- All `anthropic.Anthropic(...)` and `anthropic.AsyncAnthropic(...)` clients in `main.py`, `note_tidy.py`, `email_watcher.py`
- `requests.get/post/patch/delete` in `outlook_integration.py`
- `os.getenv(...)` when testing credential-loading paths (`get_google_credentials`, `get_ms_token`)
- `pdfplumber.open(...)` and `docx.Document(...)` in file extraction functions

**What NOT to mock:**
- Pure logic functions with no I/O: `chunk_text` (`main.py:62`), `search_documents` (`main.py:99`), `_parse_duration` (`calendar_integration.py:80`), `_fmt` (`calendar_integration.py:88`), `_fmt_message` (`gmail_integration.py:68`), `_fmt_email` (`outlook_integration.py:117`), `credentials_to_dict` (`calendar_integration.py:56`)
- Flag extraction logic in `tidy_note_text` (`note_tidy.py:143-156`)

## Fixtures and Factories

**Test Data:**
- No fixtures defined. Recommended pattern when adding tests:

```python
# Suggested fixture style — flat, no factory libraries
import pytest

@pytest.fixture
def mock_google_creds():
    from unittest.mock import MagicMock
    creds = MagicMock()
    creds.valid = True
    creds.expired = False
    return creds

@pytest.fixture
def sample_calendar_event():
    return {
        "id": "evt_abc123",
        "summary": "Antenatal visit",
        "start": {"dateTime": "2026-05-01T10:00:00+12:00"},
        "end":   {"dateTime": "2026-05-01T10:45:00+12:00"},
        "description": "",
        "location": "",
        "status": "confirmed",
        "htmlLink": "https://calendar.google.com/...",
    }

@pytest.fixture
def sample_gmail_message():
    return {
        "id": "msg_xyz",
        "threadId": "thread_xyz",
        "snippet": "Hi, I have a question about my appointment.",
        "labelIds": ["INBOX"],
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Appointment query"},
                {"name": "From",    "value": "patient@example.com"},
                {"name": "To",      "value": "midwife@example.com"},
                {"name": "Date",    "value": "Mon, 28 Apr 2026 09:00:00 +1200"},
            ],
            "mimeType": "text/plain",
            "body": {"data": "SGksIEkgaGF2ZSBhIHF1ZXN0aW9u"},  # base64
        },
    }
```

**Location:**
- No fixtures directory exists. Recommended: `tests/conftest.py` for shared fixtures.

## Coverage

**Requirements:** None enforced. No coverage configuration or CI pipeline.

**View Coverage:**
```bash
# After installing pytest-cov:
pytest --cov=. --cov-report=term-missing --cov-report=html
```

**Current estimated coverage:** 0% (no tests exist).

**High-priority areas for coverage:**
- `main.py:chunk_text` — pure function, easy to unit test boundary cases
- `main.py:search_documents` — pure scoring function, testable without mocks
- `calendar_integration.py:_parse_duration` — pure lookup, trivially testable
- `calendar_integration.py:_fmt` — pure dict normalisation
- `gmail_integration.py:_fmt_message`, `_decode_body` — pure transformations
- `outlook_integration.py:_fmt_email` — pure dict normalisation
- `note_tidy.py:tidy_note_text` flag-extraction block (lines 143-156) — pure string parsing

## Test Types

**Unit Tests:**
- Not present. Should cover pure functions (formatters, chunking, scoring, flag extraction) without any mocking.

**Integration Tests:**
- Not present. Would require mocked Google/Anthropic clients. Recommended scope: full request cycle for `_run_tool`, `create_event`, `create_draft`, `tidy_note_text`.

**E2E Tests:**
- Not applicable at current maturity. No test infrastructure exists.

## Common Patterns

**Async Testing:**
```python
# For FastAPI endpoints using AsyncAnthropic (main.py:chat)
import pytest
from httpx import AsyncClient
from main import app

@pytest.mark.asyncio
async def test_chat_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/api/chat", json={"messages": [{"role": "user", "content": "hello"}]})
    assert resp.status_code == 500
```

**Error Testing:**
```python
# Pattern matching project's RuntimeError wrapping of HttpError
from unittest.mock import MagicMock, patch
from googleapiclient.errors import HttpError
import calendar_integration

@patch("calendar_integration.build")
def test_list_events_raises_on_http_error(mock_build):
    mock_svc = MagicMock()
    mock_build.return_value = mock_svc
    mock_svc.events().list().execute.side_effect = HttpError(
        resp=MagicMock(status=403, reason="Forbidden"), content=b"Forbidden"
    )
    with pytest.raises(RuntimeError, match="Calendar error"):
        calendar_integration.list_events(MagicMock(), days_ahead=7)
```

**Credentials guard testing:**
```python
# All integration entrypoints guard on None credentials
# _run_tool (main.py:359) returns {"error": "..."} dict rather than raising
@patch("main.get_google_credentials", return_value=None)
def test_run_tool_no_creds(mock_creds):
    from main import _run_tool
    result = _run_tool("list_calendar_events", {})
    assert "error" in result
    assert "not connected" in result["error"].lower()
```

---

*Testing analysis: 2026-04-28*
