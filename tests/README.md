# Test Suite for astrbot-lark-group-daily-analysis

This directory contains comprehensive tests for the Lark group daily analysis plugin.

## Test Structure

### test_lark_integration.py
Tests for Lark platform integration components (Requirements: 1.1, 2.2, 3.1)
- LarkClientManager initialization and client access
- UserInfoCache caching and fallback mechanisms
- MessageFetcher pagination and filtering
- MessageParser for different message types (text, post, system)

### test_analysis_accuracy.py
Tests for analysis accuracy (Requirements: 4.2, 4.3, 4.4, 10.1, 10.2, 10.3, 10.4)
- TopicsAnalyzer: Verify topics use actual names and are detailed
- UsersAnalyzer: Verify user titles use actual names and include avatars
- QuotesAnalyzer: Verify quotes are properly attributed with avatars
- StatisticsCalculator: Verify accurate metrics calculation

### test_report_generation.py
Tests for report generation (Requirements: 10.1, 10.2, 10.3, 10.4, 10.5)
- Text format report generation
- Image format report generation with avatars
- PDF format report generation (if available)
- Fallback mechanisms when generation fails
- Handling of empty data

### test_error_scenarios.py
Tests for error handling (Requirements: 8.1, 8.2, 8.3, 8.5)
- API failures and timeouts
- Malformed message data
- LLM failures and invalid responses
- Fallback mechanisms
- Error logging

## Running Tests

### Install Dependencies
```bash
pip install pytest pytest-asyncio
```

### Run All Tests
```bash
# From the plugin root directory
python -m pytest tests/ -v

# Or from the tests directory
pytest -v
```

### Run Specific Test File
```bash
pytest tests/test_lark_integration.py -v
pytest tests/test_analysis_accuracy.py -v
pytest tests/test_report_generation.py -v
pytest tests/test_error_scenarios.py -v
```

### Run Specific Test Class or Method
```bash
pytest tests/test_lark_integration.py::TestLarkClientManager -v
pytest tests/test_lark_integration.py::TestLarkClientManager::test_init_with_valid_adapter -v
```

### Run with Coverage
```bash
pip install pytest-cov
pytest tests/ --cov=src --cov-report=html
```

## Test Fixtures

Common fixtures are defined in `conftest.py`:
- `mock_lark_context`: Mock AstrBot context with Lark adapter
- `sample_user_info`: Sample UserInfo object
- `sample_parsed_messages`: Sample ParsedMessage list for testing

## Manual Testing Checklist

While automated tests cover most functionality, some aspects require manual testing with a real Lark group:

### 16.1 Lark Integration
- [ ] Test with real Lark group
- [ ] Verify message fetching works
- [ ] Verify user names are correct (not truncated IDs)
- [ ] Verify avatars are fetched and displayed

### 16.2 Analysis Accuracy
- [ ] Verify topics are relevant and detailed
- [ ] Verify user titles use actual names
- [ ] Verify quotes are properly attributed
- [ ] Verify statistics are accurate

### 16.3 Report Generation
- [ ] Test text format output
- [ ] Test image format with avatars
- [ ] Test PDF format if available
- [ ] Verify all data is displayed correctly

### 16.4 Error Scenarios
- [ ] Test with API failures (disconnect network)
- [ ] Test with malformed messages
- [ ] Test with LLM failures
- [ ] Verify fallback mechanisms work

## Notes

- Tests use mocking to avoid requiring actual Lark API access
- Async tests use `pytest-asyncio` plugin
- Some tests verify logging behavior
- Error handling tests ensure graceful degradation
