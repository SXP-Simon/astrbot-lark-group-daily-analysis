# Requirements Document

## Introduction

This document outlines the requirements for refactoring the `astrbot-lark-group-daily-analysis` plugin to properly support Lark (Feishu) platform. The current implementation is a direct port from the QQ plugin and contains many platform-specific issues that prevent accurate message analysis, user identification, and report generation.

The refactored plugin should:
- Properly parse Lark message formats (text, post, system messages)
- Correctly identify users with their actual nicknames and avatars
- Generate accurate daily analysis reports with proper user attribution
- Simplify the codebase by removing unnecessary abstractions
- Provide clear, maintainable module structure

## Requirements

### Requirement 1: Lark Message Parsing

**User Story:** As a plugin developer, I want to properly parse all Lark message types, so that the analysis includes complete and accurate message content.

#### Acceptance Criteria

1. WHEN the plugin receives Lark SDK message objects THEN it SHALL correctly parse text messages from the `body.content` field
2. WHEN the plugin encounters post-type messages THEN it SHALL extract all text content from the structured post format
3. WHEN the plugin encounters system messages THEN it SHALL parse the template and extract meaningful information (e.g., "User A invited User B")
4. WHEN the plugin processes messages THEN it SHALL handle JSON-encoded content fields without errors
5. IF a message type is unsupported THEN the plugin SHALL log a warning and skip the message gracefully

### Requirement 2: User Identification and Attribution

**User Story:** As a group admin, I want to see actual user nicknames and avatars in the analysis report, so that I can identify who said what.

#### Acceptance Criteria

1. WHEN the plugin processes a message THEN it SHALL extract the sender's `open_id` from `sender_id.open_id`
2. WHEN the plugin needs a user's nickname THEN it SHALL fetch it from Lark API using the `open_id`
3. WHEN the plugin generates user titles THEN it SHALL use actual nicknames instead of truncated IDs
4. WHEN the plugin creates reports THEN it SHALL include user avatar URLs fetched from Lark API
5. IF user information cannot be fetched THEN the plugin SHALL use a fallback display name (e.g., "User_xxx")

### Requirement 3: Message History Retrieval

**User Story:** As a plugin user, I want the plugin to retrieve complete message history from Lark, so that the analysis is based on sufficient data.

#### Acceptance Criteria

1. WHEN fetching message history THEN the plugin SHALL use `lark_oapi.api.im.v1.ListMessageRequest` with correct parameters
2. WHEN paginating through messages THEN the plugin SHALL handle `page_token` correctly to retrieve all pages
3. WHEN converting timestamps THEN the plugin SHALL correctly convert milliseconds to seconds
4. WHEN filtering messages THEN the plugin SHALL exclude bot's own messages based on `bot_open_id`
5. IF the API returns an error THEN the plugin SHALL log the error details and return an empty list

### Requirement 4: LLM Analysis Optimization

**User Story:** As a plugin user, I want the LLM to generate accurate and insightful analysis, so that the daily report is valuable and interesting.

#### Acceptance Criteria

1. WHEN preparing messages for LLM analysis THEN the plugin SHALL format them with actual usernames and timestamps
2. WHEN analyzing topics THEN the LLM prompt SHALL emphasize extracting specific, detailed discussions with context
3. WHEN analyzing user titles THEN the LLM prompt SHALL use actual user activity patterns and message characteristics
4. WHEN extracting golden quotes THEN the LLM prompt SHALL focus on impactful, memorable statements with proper attribution
5. WHEN the LLM returns results THEN the plugin SHALL properly parse JSON responses and handle malformed output gracefully

### Requirement 5: Simplified Module Structure

**User Story:** As a plugin maintainer, I want a clear and simple module structure, so that the codebase is easy to understand and modify.

#### Acceptance Criteria

1. WHEN organizing code THEN the plugin SHALL use a flat module structure with clear naming
2. WHEN handling Lark SDK interactions THEN all SDK calls SHALL be in a dedicated `lark_client` module
3. WHEN processing messages THEN the message parsing logic SHALL be in a `message_parser` module
4. WHEN analyzing data THEN the analysis logic SHALL be in separate modules by function (topics, users, quotes)
5. IF a module exceeds 300 lines THEN it SHALL be split into smaller, focused modules

### Requirement 6: Bot Instance Decoupling

**User Story:** As a plugin developer, I want to remove unnecessary bot instance management, so that the code is simpler and more maintainable.

#### Acceptance Criteria

1. WHEN the plugin initializes THEN it SHALL obtain the Lark SDK client directly from the platform adapter
2. WHEN making API calls THEN the plugin SHALL use the Lark SDK client without intermediate bot manager abstractions
3. WHEN filtering bot messages THEN the plugin SHALL use the bot's `open_id` obtained once during initialization
4. WHEN the plugin terminates THEN it SHALL not need to clean up bot instance references
5. IF the Lark SDK client is unavailable THEN the plugin SHALL log an error and disable analysis features

### Requirement 7: Activity Visualization Enhancement

**User Story:** As a group admin, I want to see accurate activity patterns in the report, so that I understand when the group is most active.

#### Acceptance Criteria

1. WHEN calculating hourly activity THEN the plugin SHALL use the correct timezone from message timestamps
2. WHEN generating activity charts THEN the plugin SHALL show actual message distribution across 24 hours
3. WHEN identifying peak hours THEN the plugin SHALL correctly rank hours by message count
4. WHEN displaying user activity THEN the plugin SHALL show top contributors with accurate message counts
5. IF there are fewer than 10 messages THEN the plugin SHALL display a notice that data is insufficient for visualization

### Requirement 8: Error Handling and Logging

**User Story:** As a plugin administrator, I want clear error messages and logs, so that I can troubleshoot issues quickly.

#### Acceptance Criteria

1. WHEN an API call fails THEN the plugin SHALL log the error code, message, and request parameters
2. WHEN JSON parsing fails THEN the plugin SHALL log the raw response text for debugging
3. WHEN LLM analysis fails THEN the plugin SHALL provide fallback content and log the failure reason
4. WHEN configuration is invalid THEN the plugin SHALL log specific validation errors
5. IF the plugin encounters an unexpected exception THEN it SHALL log the full stack trace

### Requirement 9: Configuration Management

**User Story:** As a plugin user, I want to configure analysis parameters easily, so that I can customize the plugin behavior.

#### Acceptance Criteria

1. WHEN configuring the plugin THEN users SHALL be able to set analysis days (1-7)
2. WHEN configuring the plugin THEN users SHALL be able to set minimum message threshold
3. WHEN configuring the plugin THEN users SHALL be able to enable/disable specific analysis features
4. WHEN configuring the plugin THEN users SHALL be able to set output format (text/image/pdf)
5. IF configuration is changed THEN the plugin SHALL reload settings without requiring a restart

### Requirement 10: Report Generation Accuracy

**User Story:** As a group member, I want the daily report to accurately reflect group activity, so that I can catch up on what I missed.

#### Acceptance Criteria

1. WHEN generating topic summaries THEN the report SHALL include specific discussion points with context
2. WHEN listing user titles THEN the report SHALL use actual nicknames and accurate activity metrics
3. WHEN showing golden quotes THEN the report SHALL attribute quotes to the correct users
4. WHEN displaying statistics THEN the report SHALL show accurate message counts, character counts, and time ranges
5. IF the report generation fails THEN the plugin SHALL provide a text-only fallback report
