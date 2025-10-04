# Testing Quick Start Guide

Get started with testing the Lark group daily analysis plugin in 5 minutes.

## 1. Install Dependencies

```bash
# Navigate to plugin directory
cd data/plugins/astrbot-lark-group-daily-analysis

# Install test dependencies
pip install pytest pytest-asyncio
```

## 2. Run Tests

### Option A: Use the Test Runner Script (Recommended)

```bash
# Run all tests
python run_tests.py

# Run with verbose output
python run_tests.py --verbose

# Run specific test file
python run_tests.py --test tests/test_lark_integration.py
```

### Option B: Use pytest Directly

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_lark_integration.py -v

# Run specific test class
pytest tests/test_lark_integration.py::TestLarkClientManager -v

# Run specific test method
pytest tests/test_lark_integration.py::TestLarkClientManager::test_init_with_valid_adapter -v
```

## 3. Interpret Results

### Successful Test Run
```
tests/test_lark_integration.py::TestLarkClientManager::test_init_with_valid_adapter PASSED
tests/test_lark_integration.py::TestLarkClientManager::test_get_client PASSED
...
======================== 60 passed in 2.34s ========================
```

### Failed Test Run
```
tests/test_lark_integration.py::TestLarkClientManager::test_init_with_valid_adapter FAILED
...
FAILED tests/test_lark_integration.py::TestLarkClientManager::test_init_with_valid_adapter
======================== 1 failed, 59 passed in 2.45s ========================
```

## 4. Manual Testing

For comprehensive testing with a real Lark group:

```bash
# Open the manual testing guide
cat TESTING_GUIDE.md

# Or open in your editor
code TESTING_GUIDE.md
```

Follow the step-by-step procedures in TESTING_GUIDE.md to test:
- Message fetching from real Lark groups
- User name and avatar accuracy
- Analysis quality
- Report generation
- Error handling

## 5. Coverage Report (Optional)

```bash
# Install coverage tool
pip install pytest-cov

# Run tests with coverage
python run_tests.py --coverage

# Or with pytest directly
pytest tests/ --cov=src --cov-report=html

# Open coverage report in browser
# Windows:
start htmlcov/index.html
# Linux/Mac:
open htmlcov/index.html
```

## Common Issues

### Issue: "ModuleNotFoundError: No module named 'pytest'"
**Solution:** Install pytest: `pip install pytest pytest-asyncio`

### Issue: "ModuleNotFoundError: No module named 'src'"
**Solution:** Run tests from the plugin root directory, not from tests/ directory

### Issue: Tests fail with import errors
**Solution:** Ensure all plugin dependencies are installed: `pip install -r requirements.txt`

### Issue: "No tests collected"
**Solution:** Make sure you're in the plugin root directory and test files start with `test_`

## Test File Overview

| File | Purpose | Test Count |
|------|---------|------------|
| test_lark_integration.py | Lark API integration | ~15 |
| test_analysis_accuracy.py | Analysis quality | ~15 |
| test_report_generation.py | Report generation | ~12 |
| test_error_scenarios.py | Error handling | ~18 |

## Next Steps

1. ✅ Run automated tests to verify code quality
2. 📋 Follow TESTING_GUIDE.md for manual testing
3. 📊 Review TEST_SUMMARY.md for detailed coverage
4. 🐛 Report any issues found

## Need Help?

- **Automated Tests:** Check test code in `tests/` directory
- **Manual Testing:** See TESTING_GUIDE.md
- **Test Coverage:** See TEST_SUMMARY.md
- **Test Results:** Check pytest output and logs

---

**Quick Commands Reference:**

```bash
# Run all tests
python run_tests.py

# Run specific test file
python run_tests.py --test tests/test_lark_integration.py

# Run with coverage
python run_tests.py --coverage

# Run quietly
python run_tests.py --quiet

# Manual testing guide
cat TESTING_GUIDE.md
```
