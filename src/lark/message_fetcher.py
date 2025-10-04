"""
Message Fetcher

This module handles retrieving message history from the Lark API.
It manages pagination, timestamp conversion, and basic filtering.
"""

from typing import List
from datetime import datetime, timedelta
from lark_oapi.api.im.v1 import ListMessageRequest
from astrbot.api import logger

from .client import LarkClientManager


class MessageFetcher:
    """
    Fetches message history from Lark API.
    
    This class handles:
    - Message history retrieval with pagination
    - Timestamp conversion (milliseconds to seconds)
    - Filtering bot's own messages
    - Date range filtering
    """
    
    def __init__(self, client_manager: LarkClientManager):
        """
        Initialize the message fetcher.
        
        Args:
            client_manager: LarkClientManager instance for API access
        """
        self._client_manager = client_manager
    
    async def fetch_messages(
        self,
        chat_id: str,
        days: int,
        max_messages: int = 1000,
        container_id_type: str = "chat"
    ) -> List:
        """
        Fetch messages from Lark API with pagination.
        
        This method retrieves message history for the specified chat within
        the given time range. It handles pagination automatically.
        
        Args:
            chat_id: The chat/group ID (e.g., oc_xxx)
            days: Number of days to look back
            max_messages: Maximum number of messages to fetch
            container_id_type: Type of container ("chat" or "user")
            
        Returns:
            List of Lark message objects (raw SDK format), or empty list on failure
        """
        try:
            # Validate input parameters
            if not chat_id:
                logger.error("Cannot fetch messages: chat_id is empty")
                return []
            
            if days <= 0:
                logger.error(f"Cannot fetch messages: invalid days value ({days})")
                return []
            
            if max_messages <= 0:
                logger.error(f"Cannot fetch messages: invalid max_messages value ({max_messages})")
                return []
            
            # Calculate time range
            try:
                end_time = datetime.now()
                start_time = end_time - timedelta(days=days)
                
                # Convert to Unix timestamps (seconds)
                start_timestamp = 0
                end_timestamp = int(end_time.timestamp())
            except Exception as e:
                logger.error(f"Failed to calculate time range: {e}", exc_info=True)
                return []
            
            logger.info(
                f"Fetching messages: chat_id={chat_id}, "
                f"days={days}, max={max_messages}, "
                f"time_range={start_time.isoformat()} to {end_time.isoformat()}"
            )
            logger.debug(
                f"Request parameters: container_id={chat_id}, "
                f"container_id_type={container_id_type}, "
                f"start_timestamp={start_timestamp}, "
                f"end_timestamp={end_timestamp}"
            )
            
            # Fetch messages with pagination
            try:
                messages = await self._fetch_with_pagination(
                    chat_id=chat_id,
                    start_timestamp=start_timestamp,
                    end_timestamp=end_timestamp,
                    max_messages=max_messages,
                    container_id_type=container_id_type
                )
                
                logger.info(f"Successfully fetched {len(messages)} messages")
                return messages
            except Exception as e:
                logger.error(
                    f"Error during message pagination for chat_id={chat_id}: {e}",
                    exc_info=True
                )
                return []
            
        except Exception as e:
            logger.error(
                f"Unexpected error fetching messages for chat_id={chat_id}, days={days}: {e}",
                exc_info=True
            )
            return []
    
    async def _fetch_with_pagination(
        self,
        chat_id: str,
        start_timestamp: int,
        end_timestamp: int,
        max_messages: int,
        container_id_type: str,
        page_size: int = 50
    ) -> List:
        """
        Fetch messages with pagination support.
        
        Args:
            chat_id: The chat/group ID
            start_timestamp: Start time in seconds
            end_timestamp: End time in seconds
            max_messages: Maximum messages to fetch
            container_id_type: Type of container
            page_size: Number of messages per page
            
        Returns:
            List of message objects
        """
        client = self._client_manager.get_client()
        all_messages = []
        page_token = None
        page_count = 0
        
        logger.debug(
            f"Starting pagination: start={start_timestamp}, "
            f"end={end_timestamp}, page_size={page_size}"
        )
        
        while len(all_messages) < max_messages:
            page_count += 1
            
            # Build request with pagination token
            req_builder = ListMessageRequest.builder() \
                .container_id(chat_id) \
                .container_id_type(container_id_type) \
                .start_time(int(start_timestamp * 1000)) \
                .end_time(int(end_timestamp * 1000)) \
                .page_size(page_size)
            
            if page_token:
                req_builder = req_builder.page_token(page_token)
            
            request = req_builder.build()
            
            # Make API call
            logger.debug(f"Fetching page {page_count} (token: {page_token[:20] if page_token else 'None'})")
            
            try:
                response = await client.im.v1.message.alist(request)
            except AttributeError as e:
                error_msg = (
                    f"Lark SDK client structure error on page {page_count}. "
                    f"The client may not be properly initialized: {e}"
                )
                logger.error(error_msg, exc_info=True)
                raise RuntimeError(error_msg) from e
            except Exception as e:
                error_msg = (
                    f"API call failed on page {page_count} for chat_id={chat_id}. "
                    f"This may be due to network issues or API rate limiting: {e}"
                )
                logger.error(error_msg, exc_info=True)
                raise RuntimeError(error_msg) from e
            
            # Check for API errors
            if not response.success():
                error_msg = (
                    f"Lark API returned error on page {page_count}: "
                    f"code={response.code}, msg={response.msg}, "
                    f"chat_id={chat_id}, container_id_type={container_id_type}. "
                    f"Please check if the bot has permission to access this chat."
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            # Extract messages from response
            try:
                batch = response.data.items or []
                logger.debug(f"Page {page_count}: received {len(batch)} messages")
            except AttributeError as e:
                logger.error(
                    f"Failed to extract messages from response on page {page_count}: {e}",
                    exc_info=True
                )
                break
            
            if not batch:
                logger.debug("No more messages in this page")
                break
            
            # Filter and add messages
            try:
                filtered_batch = self._filter_messages(batch)
                all_messages.extend(filtered_batch)
            except Exception as e:
                logger.error(
                    f"Error filtering messages on page {page_count}: {e}. Skipping this batch.",
                    exc_info=True
                )
                # Continue to next page instead of failing completely
                continue
            
            logger.debug(
                f"Page {page_count}: {len(filtered_batch)} messages after filtering "
                f"(total: {len(all_messages)})"
            )
            
            # Check if we have more pages
            if not response.data.has_more:
                logger.debug("No more pages available")
                break
            
            page_token = response.data.page_token
            
            # Stop if we've reached the limit
            if len(all_messages) >= max_messages:
                logger.debug(f"Reached max_messages limit: {max_messages}")
                break
        
        # Trim to max_messages if we exceeded
        if len(all_messages) > max_messages:
            all_messages = all_messages[:max_messages]
            logger.debug(f"Trimmed to {max_messages} messages")
        
        logger.info(f"Pagination complete: {page_count} pages, {len(all_messages)} messages")
        return all_messages
    
    def _filter_messages(self, messages: List) -> List:
        """
        Filter messages to exclude bot's own messages.
        
        Args:
            messages: List of raw message objects
            
        Returns:
            Filtered list of messages
        """
        filtered = []
        
        for msg in messages:
            try:
                # Convert timestamp from milliseconds to seconds
                if hasattr(msg, 'create_time'):
                    try:
                        # Store original timestamp in milliseconds
                        original_timestamp = int(msg.create_time)
                        # Convert to seconds for easier handling
                        msg.create_time = original_timestamp // 1000
                        logger.debug(
                            f"Converted timestamp: {original_timestamp}ms -> {msg.create_time}s "
                            f"(message_id: {getattr(msg, 'message_id', 'unknown')})"
                        )
                    except (ValueError, TypeError) as e:
                        logger.warning(
                            f"Failed to convert timestamp for message {getattr(msg, 'message_id', 'unknown')}: {e}. "
                            f"Using current time as fallback."
                        )
                        msg.create_time = int(datetime.now().timestamp())
                
                filtered.append(msg)
                
            except Exception as e:
                logger.error(
                    f"Error processing message {getattr(msg, 'message_id', 'unknown')} during filtering: {e}. "
                    f"Skipping this message.",
                    exc_info=True
                )
                continue
        
        return filtered
