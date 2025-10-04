# Manual Testing Guide for Lark Group Daily Analysis Plugin

This guide provides step-by-step instructions for manually testing the refactored plugin with a real Lark group.

## Prerequisites

1. AstrBot instance running with Lark platform adapter configured
2. Access to a Lark group with message history
3. Bot added to the Lark group with appropriate permissions
4. Plugin installed and enabled

## Test 16.1: Lark Integration Testing

### Objective
Verify that the plugin correctly integrates with Lark API and fetches accurate data.

### Test Steps

#### 1. Test Message Fetching

**Command:** `/群分析` or `/历史消息示例`

**Expected Results:**
- ✅ Plugin successfully connects to Lark API
- ✅ Messages are fetched without errors
- ✅ Bot's own messages are filtered out
- ✅ Timestamps are correctly converted

**Verification:**
```
Check logs for:
- "Lark client manager initialized successfully"
- "Fetching messages from chat..."
- "Fetched X messages"
- No error messages about API failures
```

#### 2. Test User Name Fetching

**Command:** `/群分析`

**Expected Results:**
- ✅ User names are actual nicknames (e.g., "张三", "Alice")
- ❌ NOT truncated IDs (e.g., "User_ou_12345")
- ✅ User names appear in topics, titles, and quotes

**Verification:**
```
In the generated report, check:
- Topic participants show real names
- User titles show real names
- Quotes are attributed to real names
```

#### 3. Test Avatar Fetching

**Command:** `/群分析` (with image output format)

**Expected Results:**
- ✅ User avatars are fetched from Lark API
- ✅ Avatar URLs are valid (https://...)
- ✅ Avatars display in image/PDF reports
- ✅ Fallback to placeholder if avatar unavailable

**Verification:**
```
Check logs for:
- "Fetched user info for ou_xxx...: [actual name]"
- Avatar URLs in report data

In image report:
- User avatars visible next to names
- No broken image icons
```

#### 4. Test Cache Functionality

**Command:** Run `/群分析` twice in succession

**Expected Results:**
- ✅ First run: "Cache miss for user..."
- ✅ Second run: "Cache hit for user..."
- ✅ Faster execution on second run
- ✅ Same user names in both reports

**Verification:**
```
Check logs for cache behavior:
First run:
- "Cache miss for user ou_xxx..."
- "Fetched user info for ou_xxx..."

Second run (within 1 hour):
- "Cache hit for user ou_xxx... (age: X.Xs)"
```

### Test Results Template

```
Test 16.1: Lark Integration
Date: ___________
Tester: ___________

[ ] Message fetching works correctly
[ ] User names are actual nicknames (not IDs)
[ ] Avatars are fetched and displayed
[ ] Cache functionality works as expected

Issues Found:
_________________________________
_________________________________

Notes:
_________________________________
_________________________________
```

---

## Test 16.2: Analysis Accuracy Testing

### Objective
Verify that analysis results are accurate and use real user data.

### Test Steps

#### 1. Test Topics Analysis

**Command:** `/群分析` on a group with varied discussions

**Expected Results:**
- ✅ Topics are specific and detailed (not generic)
- ✅ Topic descriptions mention actual discussion points
- ✅ Participants listed by real names
- ✅ Topics reflect actual conversation themes

**Good Example:**
```
Topic: "Weekend Hiking Plan"
Participants: Alice, Bob, Charlie
Description: Alice proposed hiking at Mountain X this Saturday. 
Bob suggested meeting at 8 AM and bringing lunch. Charlie agreed 
and offered to drive. They decided to check weather on Friday.
```

**Bad Example:**
```
Topic: "General Discussion"
Participants: User_ou_12345, User_ou_67890
Description: Users talked about various things.
```

**Verification:**
```
Review each topic in the report:
- Does it mention specific details?
- Are names real (not IDs)?
- Does it reflect actual conversation?
```

#### 2. Test User Titles Analysis

**Command:** `/群分析`

**Expected Results:**
- ✅ User titles use actual names
- ✅ Titles reflect actual activity patterns
- ✅ Reasons are specific and accurate
- ✅ Metrics match actual behavior

**Verification:**
```
For each user title:
- Name: [Real name, not ID]
- Title: [Descriptive, e.g., "Night Owl Chatter"]
- Reason: [Specific, e.g., "Sent 80% of messages after 10 PM"]
- Metrics: [Check message count is reasonable]
```

#### 3. Test Quotes Analysis

**Command:** `/群分析`

**Expected Results:**
- ✅ Quotes are properly attributed to real names
- ✅ Quotes are actual messages from the conversation
- ✅ Reasons explain why quote was selected
- ✅ Avatars shown with quotes (in image format)

**Verification:**
```
For each quote:
- Content: [Actual message text]
- Sender: [Real name with avatar]
- Reason: [Specific explanation]

Cross-check:
- Find the actual message in chat history
- Verify it matches the quote
- Verify sender is correct
```

#### 4. Test Statistics Accuracy

**Command:** `/群分析` and manually count messages

**Expected Results:**
- ✅ Message count matches actual count
- ✅ Participant count is correct
- ✅ Peak hours reflect actual activity
- ✅ Character count is reasonable

**Verification:**
```
Compare report statistics with manual count:
- Total messages: Report [___] vs Actual [___]
- Participants: Report [___] vs Actual [___]
- Peak hour: Report [___] vs Actual [___]
```

### Test Results Template

```
Test 16.2: Analysis Accuracy
Date: ___________
Tester: ___________

[ ] Topics are detailed and use real names
[ ] User titles are accurate and specific
[ ] Quotes are properly attributed
[ ] Statistics match actual data

Issues Found:
_________________________________
_________________________________

Sample Topic Quality (1-5): ___
Sample User Title Quality (1-5): ___
Sample Quote Quality (1-5): ___
```

---

## Test 16.3: Report Generation Testing

### Objective
Verify that reports are generated correctly in all formats.

### Test Steps

#### 1. Test Text Format Report

**Configuration:** Set output format to "text"

**Command:** `/群分析`

**Expected Results:**
- ✅ Report is generated successfully
- ✅ All sections present (topics, users, quotes, stats)
- ✅ Formatting is readable
- ✅ All data is displayed correctly

**Verification:**
```
Check report contains:
[ ] Header with date range
[ ] Topics section with all topics
[ ] User titles section with all users
[ ] Quotes section with all quotes
[ ] Statistics section with metrics
[ ] Proper formatting (line breaks, sections)
```

#### 2. Test Image Format Report

**Configuration:** Set output format to "image"

**Command:** `/群分析`

**Expected Results:**
- ✅ Image is generated successfully
- ✅ User avatars are visible
- ✅ All data is displayed
- ✅ Layout is clean and readable
- ✅ Charts/visualizations are present

**Verification:**
```
Check image report:
[ ] User avatars displayed correctly
[ ] Text is readable (not too small)
[ ] Activity chart is present
[ ] All sections visible
[ ] No layout issues or overlaps
```

#### 3. Test PDF Format Report (if available)

**Configuration:** Set output format to "pdf"

**Command:** `/群分析`

**Expected Results:**
- ✅ PDF is generated successfully
- ✅ All content from image report is present
- ✅ PDF is downloadable and viewable

**Verification:**
```
Check PDF:
[ ] Opens without errors
[ ] All pages present
[ ] Content matches image report
[ ] Avatars and charts visible
```

#### 4. Test Fallback Mechanism

**Test:** Temporarily break image generation (e.g., disconnect network during render)

**Expected Results:**
- ✅ Plugin doesn't crash
- ✅ Falls back to text report
- ✅ User is notified of fallback
- ✅ Text report contains all data

**Verification:**
```
Check logs for:
- Error message about image generation failure
- "Falling back to text report"
- Text report is returned to user
```

#### 5. Test Empty Data Handling

**Test:** Run analysis on a group with no messages in the time range

**Expected Results:**
- ✅ Plugin handles gracefully
- ✅ Report indicates no data available
- ✅ No crashes or errors

**Verification:**
```
Report should show:
- "No messages found in the specified period"
- Or similar message
- Statistics show 0 messages
```

### Test Results Template

```
Test 16.3: Report Generation
Date: ___________
Tester: ___________

[ ] Text format works correctly
[ ] Image format includes avatars
[ ] PDF format works (if available)
[ ] Fallback mechanism works
[ ] Empty data handled gracefully

Issues Found:
_________________________________
_________________________________

Report Quality (1-5): ___
```

---

## Test 16.4: Error Scenarios Testing

### Objective
Verify that the plugin handles errors gracefully and provides useful feedback.

### Test Steps

#### 1. Test API Failures

**Test:** Disconnect network or revoke bot permissions

**Command:** `/群分析`

**Expected Results:**
- ✅ Plugin doesn't crash
- ✅ Clear error message to user
- ✅ Detailed error in logs
- ✅ Fallback data used where possible

**Verification:**
```
Check logs for:
- "Failed to fetch messages: [error details]"
- "Using fallback user info"
- Error includes request parameters for debugging

User sees:
- Friendly error message
- Suggestion to check bot permissions
```

#### 2. Test Malformed Messages

**Test:** (This requires special setup - may skip if difficult)

**Expected Results:**
- ✅ Malformed messages are skipped
- ✅ Warning logged for each skipped message
- ✅ Analysis continues with valid messages
- ✅ No crashes

**Verification:**
```
Check logs for:
- "Skipping message msg_xxx: [reason]"
- "Parsed X out of Y messages"
- Analysis completes successfully
```

#### 3. Test LLM Failures

**Test:** Temporarily set invalid LLM API key or model

**Command:** `/群分析`

**Expected Results:**
- ✅ Plugin doesn't crash
- ✅ Clear error message about LLM failure
- ✅ Fallback to basic analysis (if implemented)
- ✅ Detailed error in logs

**Verification:**
```
Check logs for:
- "LLM analysis failed: [error details]"
- "Falling back to basic analysis"

User sees:
- Error message about analysis failure
- Suggestion to check configuration
```

#### 4. Test Configuration Errors

**Test:** Set invalid configuration values (e.g., days=-1, max_messages=0)

**Command:** `/群分析`

**Expected Results:**
- ✅ Configuration validation catches errors
- ✅ Clear error message about invalid config
- ✅ Suggests correct values
- ✅ Plugin doesn't crash

**Verification:**
```
Check logs for:
- "Invalid configuration: [field] = [value]"
- "Expected: [valid range]"

User sees:
- Error message about configuration
- Instructions to fix
```

#### 5. Test Timeout Scenarios

**Test:** Set very short timeout or analyze very large group

**Expected Results:**
- ✅ Timeout is handled gracefully
- ✅ Partial results returned if possible
- ✅ Clear message about timeout
- ✅ No hanging or freezing

**Verification:**
```
Check logs for:
- "Operation timed out after Xs"
- "Returning partial results"

User sees:
- Message about timeout
- Partial results or suggestion to reduce scope
```

### Test Results Template

```
Test 16.4: Error Scenarios
Date: ___________
Tester: ___________

[ ] API failures handled gracefully
[ ] Malformed messages skipped correctly
[ ] LLM failures don't crash plugin
[ ] Configuration errors caught
[ ] Timeouts handled properly

Issues Found:
_________________________________
_________________________________

Error Handling Quality (1-5): ___
```

---

## Overall Test Summary

### Test Completion Checklist

```
[ ] 16.1 Lark Integration - All tests passed
[ ] 16.2 Analysis Accuracy - All tests passed
[ ] 16.3 Report Generation - All tests passed
[ ] 16.4 Error Scenarios - All tests passed
```

### Critical Issues Found

```
Priority | Issue | Test | Status
---------|-------|------|-------
High     |       |      |
Medium   |       |      |
Low      |       |      |
```

### Recommendations

```
1. _________________________________
2. _________________________________
3. _________________________________
```

### Sign-off

```
Tested by: ___________
Date: ___________
Overall Status: [ ] Pass [ ] Pass with Issues [ ] Fail

Notes:
_________________________________
_________________________________
_________________________________
```

---

## Automated Test Execution

While manual testing is comprehensive, you can also run the automated test suite:

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
python run_tests.py

# Run specific test file
python run_tests.py --test tests/test_lark_integration.py

# Run with coverage
python run_tests.py --coverage
```

Note: Automated tests use mocking and may not catch all real-world issues. Manual testing with actual Lark groups is essential for validation.
