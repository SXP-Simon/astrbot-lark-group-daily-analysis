# Implementation Plan

This implementation plan breaks down the refactoring into discrete, manageable tasks. Each task builds incrementally on previous work, ensuring the plugin remains functional throughout the refactoring process.

- [x] 1. Set up new module structure and data models



  - Create new directory structure under `src/`
  - Define core data models in `src/models.py`
  - Create `__init__.py` files for all modules
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 1.1 Create new directory structure


  - Create `src/lark/` directory for Lark platform integration
  - Create `src/analysis/` directory for analysis logic
  - Create `src/reports/` directory for report generation
  - Remove old `src/core/bot_manager.py` (will be replaced)
  - _Requirements: 5.1, 5.2, 6.4_

- [x] 1.2 Define core data models


  - Create `src/models.py` with `ParsedMessage` dataclass
  - Add `UserInfo`, `Topic`, `UserTitle`, `Quote` models
  - Add `UserMetrics`, `Statistics`, `AnalysisResult` models
  - Add `TokenUsage` and `EmojiStats` models
  - _Requirements: 1.1, 2.1, 2.4_

- [x] 2. Implement Lark client manager





  - Create `src/lark/client.py` with `LarkClientManager` class
  - Implement method to get Lark SDK client from platform adapter
  - Implement method to get bot's open_id
  - Add error handling for missing Lark adapter
  - _Requirements: 6.1, 6.2, 8.4_

- [x] 2.1 Implement LarkClientManager class


  - Write `__init__` method to extract Lark adapter from context
  - Write `get_client()` method to return `lark.Client` instance
  - Write `get_bot_open_id()` method to return bot's open_id
  - Add validation to ensure Lark adapter exists
  - _Requirements: 6.1, 6.2, 8.1_



- [x] 2.2 Add error handling and logging









  - Raise clear exception if Lark adapter not found
  - Log client initialization success/failure
  - Add debug logging for bot open_id
  - _Requirements: 8.1, 8.4_

- [ ] 3. Implement user info cache




  - Create `src/lark/user_info.py` with `UserInfoCache` class
  - Implement single user fetch with caching
  - Implement batch user fetch
  - Add cache expiration logic (TTL)
  - _Requirements: 2.2, 2.5_

- [x] 3.1 Implement UserInfoCache class


  - Write `__init__` method with client manager
  - Write `get_user_info()` method with cache lookup
  - Write `_fetch_user_from_api()` method using Lark SDK
  - Implement in-memory cache with dict
  - _Requirements: 2.2, 2.5_

- [x] 3.2 Implement batch fetching


  - Write `batch_fetch_users()` method
  - Use Lark SDK batch API if available
  - Fall back to sequential fetching if needed
  - Update cache with batch results
  - _Requirements: 2.2_

- [x] 3.3 Add cache management


  - Implement TTL-based cache expiration (1 hour default)
  - Write `clear_cache()` method
  - Add cache hit/miss logging
  - _Requirements: 2.5_

- [ ] 4. Implement message fetcher



  - Create `src/lark/message_fetcher.py` with `MessageFetcher` class
  - Implement message history retrieval with pagination
  - Filter out bot's own messages
  - Handle timestamp conversion (milliseconds to seconds)
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 4.1 Implement MessageFetcher class


  - Write `__init__` method with client manager
  - Write `fetch_messages()` method using `ListMessageRequest`
  - Implement pagination loop with `page_token`
  - Convert timestamps from milliseconds to seconds
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 4.2 Add message filtering


  - Filter out messages from bot's own open_id
  - Apply date range filtering
  - Limit total messages to configured maximum
  - _Requirements: 3.4, 3.5_

- [x] 4.3 Add error handling


  - Handle API errors with detailed logging
  - Return empty list on failure
  - Log request parameters for debugging
  - _Requirements: 3.5, 8.1_

- [x] 5. Implement message parser





  - Create `src/lark/message_parser.py` with `MessageParser` class
  - Implement text message parsing
  - Implement post (rich text) message parsing
  - Implement system message parsing
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 5.1 Implement MessageParser class


  - Write `__init__` method with user info cache
  - Write `parse_message()` async method
  - Extract sender open_id from `sender_id.open_id`
  - Fetch sender info using user info cache
  - _Requirements: 1.1, 2.1, 2.2_

- [x] 5.2 Implement text message parsing


  - Write `parse_text_content()` method
  - Extract text from `body.content` JSON field
  - Handle JSON parsing errors gracefully
  - _Requirements: 1.1, 1.5_

- [x] 5.3 Implement post message parsing


  - Write `parse_post_content()` method
  - Parse structured post format (title + content blocks)
  - Extract all text elements from post structure
  - Concatenate text with proper formatting
  - _Requirements: 1.2, 1.5_

- [x] 5.4 Implement system message parsing


  - Write `parse_system_message()` method
  - Parse template field (e.g., "{from_user} invited {to_chatters}")
  - Extract user names from template variables
  - Generate human-readable system message text
  - _Requirements: 1.3, 1.5_

- [x] 5.5 Add error handling


  - Return None for unparseable messages
  - Log warnings for unsupported message types
  - Include raw content in ParsedMessage for debugging
  - _Requirements: 1.5, 8.2_

- [x] 6. Refactor topics analyzer





  - Update `src/analysis/topics.py` to use ParsedMessage
  - Improve LLM prompt with actual usernames
  - Enhance prompt to request specific, detailed summaries
  - Update JSON parsing to handle new format
  - _Requirements: 4.1, 4.2, 4.5, 10.1_


- [x] 6.1 Update TopicsAnalyzer to use ParsedMessage

  - Modify `analyze()` method signature to accept `List[ParsedMessage]`
  - Format messages with actual sender names and timestamps
  - Remove old message format handling code
  - _Requirements: 4.1, 4.2_

- [x] 6.2 Improve LLM prompt


  - Update prompt to emphasize specific, detailed discussions
  - Add examples of good vs. bad summaries
  - Request context and conclusions in topic descriptions
  - Specify that summaries should mention who did what
  - _Requirements: 4.2, 10.1_

- [x] 6.3 Enhance JSON parsing


  - Update expected JSON structure if needed
  - Improve error handling for malformed JSON
  - Add regex fallback extraction
  - _Requirements: 4.5, 8.2_

- [ ] 7. Refactor users analyzer




  - Update `src/analysis/users.py` to use ParsedMessage
  - Calculate metrics using actual user info
  - Improve LLM prompt with real usernames
  - Return UserTitle objects with avatar URLs
  - _Requirements: 2.3, 2.4, 4.3, 10.2_

- [x] 7.1 Update UsersAnalyzer to use ParsedMessage


  - Modify `analyze()` method signature
  - Calculate metrics from ParsedMessage fields
  - Use sender_name instead of truncated IDs
  - _Requirements: 2.3, 4.3_

- [x] 7.2 Enhance user metrics calculation


  - Calculate hourly distribution from timestamps
  - Calculate average message length from content
  - Count emoji usage from content
  - Track reply patterns if available
  - _Requirements: 2.3, 10.2_

- [x] 7.3 Improve LLM prompt


  - Format user data with actual names
  - Include avatar URLs in output
  - Request specific reasons for title assignments
  - _Requirements: 2.4, 4.3, 10.2_

- [x] 8. Refactor quotes analyzer





  - Update `src/analysis/quotes.py` to use ParsedMessage
  - Improve LLM prompt for better quote selection
  - Include sender names and avatars in Quote objects
  - Enhance selection criteria in prompt
  - _Requirements: 2.4, 4.4, 10.3_

- [x] 8.1 Update QuotesAnalyzer to use ParsedMessage


  - Modify `analyze()` method signature
  - Format messages with actual sender names
  - Filter messages by length and content quality
  - _Requirements: 4.4, 10.3_

- [x] 8.2 Improve LLM prompt

  - Emphasize impactful, memorable statements
  - Request specific reasons for quote selection
  - Include sender attribution in output
  - Add examples of good quotes
  - _Requirements: 4.4, 10.3_

- [x] 8.3 Add avatar URLs to Quote objects

  - Include sender_avatar in Quote dataclass
  - Fetch avatar from ParsedMessage
  - _Requirements: 2.4, 10.3_

- [ ] 9. Update statistics calculator








  - Update `src/analysis/statistics.py` to use ParsedMessage
  - Calculate accurate hourly distribution
  - Identify peak hours correctly
  - Calculate emoji statistics
  - _Requirements: 7.1, 7.2, 7.3, 10.4_


- [x] 9.1 Update StatisticsCalculator

  - Modify `calculate()` method to accept `List[ParsedMessage]`
  - Calculate message count, char count, participant count
  - Build hourly distribution from timestamps
  - Identify top 3 peak hours
  - _Requirements: 7.1, 7.2, 7.3, 10.4_


- [x] 9.2 Add emoji statistics

  - Count emoji occurrences in message content
  - Track emoji types if possible
  - Calculate emoji usage per user
  - _Requirements: 10.4_

- [ ] 10. Update report generator





  - Update `src/reports/generator.py` to use new models
  - Include user avatars in image/PDF reports
  - Update templates with actual usernames
  - Enhance visualization with accurate data
  - _Requirements: 2.4, 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 10.1 Update ReportGenerator


  - Modify methods to accept AnalysisResult
  - Update text report template with new fields
  - Update HTML template for image reports
  - Include user avatars in templates
  - _Requirements: 2.4, 10.1, 10.2, 10.3_

- [x] 10.2 Enhance visualizations


  - Update activity charts with accurate timestamps
  - Show user avatars in user ranking
  - Improve chart styling and readability
  - _Requirements: 7.4, 10.4_

- [x] 10.3 Add fallback handling


  - Provide text-only fallback if image generation fails
  - Handle missing avatars gracefully
  - Show placeholder for missing data
  - _Requirements: 10.5_
-

- [ ] 11. Update main plugin entry point



  - Refactor `main.py` to use new architecture
  - Remove bot_manager initialization
  - Initialize new Lark client manager
  - Update command handlers to use new components
  - _Requirements: 6.1, 6.3, 6.4_

- [x] 11.1 Refactor plugin initialization


  - Remove bot_manager and related code
  - Initialize LarkClientManager
  - Initialize UserInfoCache
  - Initialize MessageFetcher and MessageParser
  - _Requirements: 6.1, 6.4_

- [x] 11.2 Update command handlers


  - Update `/群分析` command to use new flow
  - Update `/历史消息示例` command
  - Remove bot instance management code
  - _Requirements: 6.2, 6.3_

- [x] 11.3 Update configuration handling


  - Ensure ConfigManager works with new structure
  - Update config validation
  - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [ ] 12. Update configuration management





  - Review and update `src/config.py`
  - Add new configuration options if needed
  - Ensure backward compatibility
  - Add configuration validation
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 12.1 Review ConfigManager


  - Ensure all config getters are present
  - Add any missing configuration options
  - Update default values if needed
  - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 12.2 Add configuration validation


  - Validate analysis_days range (1-7)
  - Validate max_messages > 0
  - Validate output format options
  - Log validation errors clearly
  - _Requirements: 8.4, 9.4_

- [ ] 13. Add comprehensive error handling




  - Add try-catch blocks in all async methods
  - Log errors with full context
  - Provide user-friendly error messages
  - Add fallback mechanisms
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 13.1 Add error handling to Lark modules


  - Handle API errors in client manager
  - Handle fetch errors in message fetcher
  - Handle parse errors in message parser
  - Handle cache errors in user info cache
  - _Requirements: 8.1, 8.2_


- [x] 13.2 Add error handling to analysis modules

  - Handle LLM errors with retry logic
  - Handle JSON parsing errors with fallback
  - Handle calculation errors gracefully
  - _Requirements: 8.2, 8.3_

- [x] 13.3 Add error handling to report generation


  - Handle template rendering errors
  - Handle image generation errors with text fallback
  - Handle PDF generation errors
  - _Requirements: 8.3, 10.5_

- [x] 14. Add comprehensive logging




  - Add debug logging for API calls
  - Add info logging for progress
  - Add warning logging for fallbacks
  - Add error logging with stack traces
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 14.1 Add logging to Lark modules


  - Log client initialization
  - Log message fetch progress
  - Log parse warnings for unsupported types
  - Log user info cache hits/misses
  - _Requirements: 8.1, 8.2_

- [x] 14.2 Add logging to analysis modules


  - Log LLM request/response
  - Log analysis progress
  - Log token usage
  - _Requirements: 8.1, 8.3_

- [x] 14.3 Add logging to report generation


  - Log report generation start/end
  - Log format selection
  - Log any fallback usage
  - _Requirements: 8.3_

- [ ] 15. Remove old code and cleanup




  - Delete `src/core/bot_manager.py`
  - Delete `src/core/feishu_history_sdk.py` (replaced by message_fetcher)
  - Remove unused imports
  - Update `src/utils/helpers.py` if needed
  - _Requirements: 5.4, 6.4_

- [x] 15.1 Delete obsolete files


  - Remove `src/core/bot_manager.py`
  - Remove `src/core/feishu_history_sdk.py`
  - Remove any other unused files
  - _Requirements: 5.4, 6.4_

- [x] 15.2 Clean up imports


  - Remove imports of deleted modules
  - Update import paths for moved modules
  - Remove unused imports
  - _Requirements: 5.4_

- [x] 15.3 Update helper modules


  - Review `src/utils/helpers.py`
  - Remove or update MessageAnalyzer if needed
  - Ensure all utilities are still needed
  - _Requirements: 5.4_

- [x] 16. Testing and validation





  - Test message fetching with real Lark group
  - Test message parsing with various message types
  - Test user info fetching and caching
  - Test complete analysis flow
  - Test all report formats
  - _Requirements: All_

- [x] 16.1 Test Lark integration


  - Test with real Lark group
  - Verify message fetching works
  - Verify user names are correct
  - Verify avatars are fetched
  - _Requirements: 1.1, 2.2, 3.1_

- [x] 16.2 Test analysis accuracy

  - Verify topics are relevant and detailed
  - Verify user titles use actual names
  - Verify quotes are properly attributed
  - Verify statistics are accurate
  - _Requirements: 4.2, 4.3, 4.4, 10.1, 10.2, 10.3, 10.4_

- [x] 16.3 Test report generation

  - Test text format output
  - Test image format with avatars
  - Test PDF format if available
  - Verify all data is displayed correctly
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 16.4 Test error scenarios

  - Test with API failures
  - Test with malformed messages
  - Test with LLM failures
  - Verify fallback mechanisms work
  - _Requirements: 8.1, 8.2, 8.3, 8.5_

- [ ] 17. Documentation updates



  - 使用中文
  - comment in Chinese
  - Update README with new architecture
  - Document new configuration options
  - Add troubleshooting guide
  - Update code comments
  - _Requirements: All_

- [x] 17.1 Update README


  - Document new module structure
  - Explain Lark integration
  - Add usage examples
  - _Requirements: 5.1_



- [ ] 17.2 Add inline documentation
  - Add docstrings to all classes and methods
  - Add type hints
  - Add comments for complex logic
  - _Requirements: All_



- [ ] 17.3 Create troubleshooting guide
  - Document common errors
  - Provide solutions
  - Add FAQ section
  - _Requirements: 8.1, 8.4_
