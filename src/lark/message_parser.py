"""
Message Parser

This module provides functionality to parse Lark SDK message objects into
a unified ParsedMessage format. It handles various message types including
text, post (rich text), and system messages.
"""

import json
from typing import Optional
from astrbot.api import logger
from ..models import ParsedMessage
from .user_info import UserInfoCache


class MessageParser:
    """
    Parses Lark SDK message objects into unified ParsedMessage format.
    
    This class handles different Lark message types and extracts relevant
    information including sender details, content, and metadata.
    """
    
    def __init__(self, user_info_cache: UserInfoCache):
        """
        Initialize the message parser.
        
        Args:
            user_info_cache: Cache for fetching user information
        """
        self._user_info_cache = user_info_cache
        logger.debug("MessageParser initialized")
    
    async def parse_message(self, msg) -> Optional[ParsedMessage]:
        """
        Parse a single Lark message into ParsedMessage format.
        
        This method extracts the sender's open_id, fetches their user info,
        parses the message content based on type, and returns a unified
        ParsedMessage object.
        
        Args:
            msg: Lark SDK message object
            
        Returns:
            ParsedMessage object or None if message cannot be parsed
        """
        message_id = "unknown"
        try:
            # Extract message ID early for better error logging
            message_id = getattr(msg, 'message_id', 'unknown')
            
            # Validate message object
            if not msg:
                logger.warning("Received None message object, skipping")
                return None
            
            # Extract sender open_id - handle different message structures
            sender_id = None
            
            # Debug: log message structure
            # Note: sender.id should be user's open_id (starts with 'ou_')
            # If it's app_id (starts with 'cli_'), it's a bot message
            logger.debug(f"Message {message_id} structure: sender type={type(getattr(msg, 'sender', None))}, "
                        f"has sender_id={hasattr(msg, 'sender_id')}")
            
            try:
                # Try different possible structures
                if hasattr(msg, 'sender'):
                    sender = msg.sender
                    # Case 1: sender is a string (direct open_id)
                    if isinstance(sender, str):
                        sender_id = sender
                        logger.debug(f"Message {message_id}: sender is string: {sender_id[:8]}...")
                    # Case 2: Sender object with 'id' attribute (lark_oapi.api.im.v1.model.sender.Sender)
                    elif hasattr(sender, 'id') and isinstance(sender.id, str):
                        sender_id = sender.id
                        logger.debug(f"Message {message_id}: sender.id (string): {sender_id[:8]}...")
                    # Case 3: sender.id.open_id structure (nested object)
                    elif hasattr(sender, 'id') and hasattr(sender.id, 'open_id'):
                        sender_id = sender.id.open_id
                        logger.debug(f"Message {message_id}: sender.id.open_id: {sender_id[:8]}...")
                    # Case 4: sender.open_id structure
                    elif hasattr(sender, 'open_id'):
                        sender_id = sender.open_id
                        logger.debug(f"Message {message_id}: sender.open_id: {sender_id[:8]}...")
                    else:
                        logger.warning(f"Message {message_id}: sender has unknown structure: {type(sender)}, available attrs={[a for a in dir(sender) if not a.startswith('_')]}")
                
                # Try sender_id field directly
                if not sender_id and hasattr(msg, 'sender_id'):
                    sender_id_obj = msg.sender_id
                    if isinstance(sender_id_obj, str):
                        sender_id = sender_id_obj
                    elif hasattr(sender_id_obj, 'open_id'):
                        sender_id = sender_id_obj.open_id
                    elif hasattr(sender_id_obj, 'id'):
                        sender_id = sender_id_obj.id
                    logger.debug(f"Message {message_id}: using sender_id field: {sender_id[:8] if sender_id else 'None'}...")
                        
            except AttributeError as e:
                logger.warning(
                    f"Message {message_id} has invalid sender structure: {e}. Skipping message."
                )
                return None
            
            if not sender_id:
                logger.warning(f"Message {message_id} has no sender open_id, skipping")
                return None
            
            # Skip messages where sender.id is app_id instead of open_id
            # App IDs start with 'cli_', while user open_ids start with 'ou_'
            if sender_id.startswith('cli_'):
                logger.debug(f"Message {message_id} has app_id instead of user open_id (app_id: {sender_id[:12]}...), skipping. This is likely a bot message.")
                return None
            
            # Fetch sender info from cache
            try:
                user_info = await self._user_info_cache.get_user_info(sender_id)
            except Exception as e:
                logger.error(
                    f"Failed to fetch user info for sender {sender_id[:8]}... in message {message_id}: {e}. "
                    f"Using fallback user info.",
                    exc_info=True
                )
                # Create fallback user info
                from ..models import UserInfo
                user_info = UserInfo(
                    open_id=sender_id,
                    name=f"User_{sender_id[:8]}",
                    avatar_url="",
                    en_name=""
                )
            
            # Extract message type
            message_type = msg.msg_type if hasattr(msg, 'msg_type') else "unknown"
            
            # Extract timestamp (convert from milliseconds to seconds if needed)
            try:
                timestamp = int(msg.create_time) if hasattr(msg, 'create_time') else 0
                # Lark timestamps are in milliseconds, convert to seconds
                if timestamp > 10**12:  # If timestamp is in milliseconds
                    timestamp = timestamp // 1000
                elif timestamp == 0:
                    logger.warning(f"Message {message_id} has no timestamp, using current time")
                    from datetime import datetime
                    timestamp = int(datetime.now().timestamp())
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Failed to parse timestamp for message {message_id}: {e}. Using current time."
                )
                from datetime import datetime
                timestamp = int(datetime.now().timestamp())
            
            # Get raw content
            try:
                raw_content = msg.body.content if msg.body and hasattr(msg.body, 'content') else ""
            except AttributeError as e:
                logger.warning(f"Message {message_id} has invalid body structure: {e}")
                raw_content = ""
            
            # Parse content based on message type
            content = None
            try:
                if message_type == "text":
                    content = self.parse_text_content(raw_content)
                elif message_type == "post":
                    content = self.parse_post_content(raw_content)
                elif message_type in ["system", "share_chat"]:
                    content = self.parse_system_message(msg)
                else:
                    logger.warning(
                        f"Unsupported message type '{message_type}' for message {message_id}. "
                        f"Supported types: text, post, system, share_chat"
                    )
                    return None
            except Exception as e:
                logger.error(
                    f"Error parsing content for message {message_id} (type: {message_type}): {e}",
                    exc_info=True
                )
                return None
            
            # If content parsing failed, skip this message
            if content is None or content.strip() == "":
                logger.warning(
                    f"Failed to parse content or content is empty for message {message_id} (type: {message_type})"
                )
                return None
            
            # Create ParsedMessage
            try:
                parsed_message = ParsedMessage(
                    message_id=message_id,
                    timestamp=timestamp,
                    sender_id=sender_id,
                    sender_name=user_info.name,
                    sender_avatar=user_info.avatar_url,
                    content=content,
                    message_type=message_type,
                    raw_content=raw_content
                )
            except Exception as e:
                logger.error(
                    f"Failed to create ParsedMessage object for message {message_id}: {e}",
                    exc_info=True
                )
                return None
            
            logger.debug(
                f"Parsed message {message_id[:8]}... from {user_info.name} (avatar: {bool(user_info.avatar_url)}): "
                f"{content[:50]}..." if len(content) > 50 else content
            )
            
            return parsed_message
            
        except Exception as e:
            logger.error(
                f"Unexpected error parsing message {message_id}: {e}",
                exc_info=True
            )
            return None
    
    def parse_text_content(self, content: str) -> Optional[str]:
        """
        Parse text message content.
        
        Text messages in Lark have their content stored as JSON in the format:
        {"text": "actual message text"}
        
        Args:
            content: Raw content string from message body
            
        Returns:
            Extracted text or None if parsing fails
        """
        try:
            if not content:
                logger.debug("Empty content provided to parse_text_content")
                return None
            
            # Content is JSON-encoded
            try:
                content_json = json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse text content as JSON: {e}. "
                    f"Attempting to use raw content as fallback."
                )
                # Try to return raw content as fallback
                return content if content.strip() else None
            
            # Extract text field
            if not isinstance(content_json, dict):
                logger.warning(f"Text content JSON is not a dictionary: {type(content_json)}")
                return str(content_json) if content_json else None
            
            text = content_json.get("text", "")
            
            if not text:
                logger.debug("Text field is empty in content JSON")
                return None
            
            return text
            
        except Exception as e:
            logger.error(f"Unexpected error parsing text content: {e}", exc_info=True)
            # Last resort: return raw content if it's not empty
            return content if content and content.strip() else None

    def parse_post_content(self, content: str) -> Optional[str]:
        """
        Parse post (rich text) message content.
        
        Post messages in Lark have a structured format with title and content blocks:
        {
            "zh_cn": {
                "title": "Post Title",
                "content": [
                    [{"tag": "text", "text": "Line 1"}],
                    [{"tag": "text", "text": "Line 2"}, {"tag": "a", "text": "link"}]
                ]
            }
        }
        
        This method extracts all text elements and concatenates them.
        
        Args:
            content: Raw content string from message body
            
        Returns:
            Concatenated text from post or None if parsing fails
        """
        try:
            if not content:
                logger.debug("Empty content provided to parse_post_content")
                return None
            
            # Content is JSON-encoded
            try:
                content_json = json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse post content as JSON: {e}")
                return None
            
            if not isinstance(content_json, dict):
                logger.warning(f"Post content JSON is not a dictionary: {type(content_json)}")
                return None
            
            # Post messages can have multiple language versions
            # Try to get the first available language version
            post_data = None
            for lang_key in ["zh_cn", "zh_tw", "en_us", "ja_jp"]:
                if lang_key in content_json:
                    post_data = content_json[lang_key]
                    logger.debug(f"Found post data in language: {lang_key}")
                    break
            
            # If no known language key, try to get the first key
            if not post_data and content_json:
                try:
                    first_key = next(iter(content_json))
                    post_data = content_json[first_key]
                    logger.debug(f"Using first available language key: {first_key}")
                except StopIteration:
                    logger.warning("Content JSON is empty")
                    return None
            
            if not post_data:
                logger.warning(f"No post data found in content. Available keys: {list(content_json.keys()) if content_json else 'None'}")
                logger.debug(f"Content JSON structure: {content_json}")
                return None
            
            if not isinstance(post_data, dict):
                logger.warning(f"Post data is not a dictionary: {type(post_data)}")
                return None
            
            # Extract title
            title = post_data.get("title", "")
            
            # Extract content blocks
            content_blocks = post_data.get("content", [])
            
            if not isinstance(content_blocks, list):
                logger.warning(f"Content blocks is not a list: {type(content_blocks)}")
                content_blocks = []
            
            # Collect all text elements
            text_parts = []
            
            if title:
                text_parts.append(str(title))
            
            for block_idx, block in enumerate(content_blocks):
                try:
                    if not isinstance(block, list):
                        logger.debug(f"Block {block_idx} is not a list, skipping")
                        continue
                    
                    # Each block is a list of elements (a line)
                    line_parts = []
                    for element_idx, element in enumerate(block):
                        try:
                            if isinstance(element, dict):
                                # Extract text from various element types
                                if "text" in element:
                                    line_parts.append(str(element["text"]))
                                elif "content" in element:
                                    line_parts.append(str(element["content"]))
                        except Exception as e:
                            logger.debug(
                                f"Error processing element {element_idx} in block {block_idx}: {e}"
                            )
                            continue
                    
                    if line_parts:
                        text_parts.append(" ".join(line_parts))
                        
                except Exception as e:
                    logger.debug(f"Error processing block {block_idx}: {e}")
                    continue
            
            # Join all parts with newlines
            result = "\n".join(text_parts)
            return result if result.strip() else None
            
        except Exception as e:
            logger.error(f"Unexpected error parsing post content: {e}", exc_info=True)
            return None

    def parse_system_message(self, msg) -> Optional[str]:
        """
        Parse system message content.
        
        System messages in Lark use templates with variables, for example:
        - "{from_user} invited {to_chatters}"
        - "{from_user} removed {to_chatters}"
        - "{from_user} changed group name to {new_name}"
        
        This method extracts the template and replaces variables with actual values
        to generate a human-readable message.
        
        Args:
            msg: Lark SDK message object
            
        Returns:
            Human-readable system message text or None if parsing fails
        """
        try:
            # System messages may have different structures
            # Try to get the content from body
            if not msg.body or not hasattr(msg.body, 'content'):
                logger.warning(f"System message {msg.message_id} has no body content")
                return None
            
            raw_content = msg.body.content
            
            # Try to parse as JSON
            try:
                content_json = json.loads(raw_content)
                
                # Look for template field
                template = content_json.get("template", "")
                
                if not template:
                    # Some system messages might have a "text" field
                    text = content_json.get("text", "")
                    if text:
                        return text
                    
                    # If no template or text, return a generic message
                    logger.warning(f"System message {msg.message_id} has no template or text")
                    return "[System Message]"
                
                # Extract variables from the message
                # Variables are typically in the format {variable_name}
                # We'll try to replace them with actual values if available
                
                # Common variables in system messages
                variables = content_json.get("variables", {})
                
                # Replace variables in template
                result = template
                for var_name, var_value in variables.items():
                    placeholder = f"{{{var_name}}}"
                    result = result.replace(placeholder, str(var_value))
                
                # If there are still unreplaced variables, try to extract user names
                # from the message context
                if "{from_user}" in result or "{to_chatters}" in result:
                    # Try to get sender name
                    if msg.sender and msg.sender.id:
                        sender_id = msg.sender.id.open_id
                        # We can't await here, so we'll use a placeholder
                        result = result.replace("{from_user}", f"User_{sender_id[:8]}")
                    
                    # For to_chatters, we'll use a generic placeholder
                    result = result.replace("{to_chatters}", "some users")
                
                return result
                
            except json.JSONDecodeError:
                # If not JSON, return the raw content
                logger.warning(f"System message {msg.message_id} content is not JSON")
                return raw_content if raw_content else "[System Message]"
            
        except Exception as e:
            logger.error(f"Error parsing system message {getattr(msg, 'message_id', 'unknown')}: {e}")
            return None
