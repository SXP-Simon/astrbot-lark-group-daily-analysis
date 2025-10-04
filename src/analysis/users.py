"""
Users analyzer module
Analyzes user activity patterns and assigns titles using LLM.
"""

import json
import re
from datetime import datetime
from typing import List, Tuple, Dict
from collections import defaultdict
from astrbot.api import logger
from ..models import ParsedMessage, UserTitle, UserMetrics, TokenUsage


class UsersAnalyzer:
    """Analyzes user activity and assigns titles"""

    def __init__(self, context, config_manager):
        """
        Initialize with AstrBot context and config.
        
        Args:
            context: AstrBot context for accessing LLM provider
            config_manager: Configuration manager instance
        """
        self.context = context
        self.config_manager = config_manager

    async def analyze(
        self,
        messages: List[ParsedMessage],
        umo: str = None
    ) -> Tuple[List[UserTitle], TokenUsage]:
        """
        Analyze user activity and assign titles.
        
        Args:
            messages: List of parsed messages
            umo: Unique Model Object identifier for LLM selection
            
        Returns:
            Tuple of (list of UserTitle objects, TokenUsage)
        """
        try:
            # Validate input
            if not messages:
                logger.warning("No messages provided for user analysis")
                return [], TokenUsage()
            
            if not isinstance(messages, list):
                logger.error(f"Invalid messages type: expected list, got {type(messages)}")
                return [], TokenUsage()

            # Calculate metrics for each user
            try:
                user_metrics = self._calculate_user_metrics(messages)
            except Exception as e:
                logger.error(f"Error calculating user metrics: {e}", exc_info=True)
                return [], TokenUsage()
            
            if not user_metrics:
                logger.info("No user metrics calculated")
                return [], TokenUsage()

            # Filter users with low activity (less than 5 messages)
            try:
                active_users = {
                    user_id: metrics 
                    for user_id, metrics in user_metrics.items() 
                    if metrics.message_count >= 5
                }
            except Exception as e:
                logger.error(f"Error filtering active users: {e}", exc_info=True)
                return [], TokenUsage()

            if not active_users:
                logger.info("No active users found (minimum 5 messages required)")
                return [], TokenUsage()

            # Sort by message count and take top N users
            try:
                max_user_titles = self.config_manager.get_max_user_titles()
                sorted_users = sorted(
                    active_users.items(),
                    key=lambda x: x[1].message_count,
                    reverse=True
                )[:max_user_titles]
            except Exception as e:
                logger.error(f"Error sorting users: {e}", exc_info=True)
                return [], TokenUsage()

            # Call LLM to assign titles
            try:
                user_titles, token_usage = await self._assign_titles_with_llm(
                    sorted_users,
                    messages,
                    umo
                )
                logger.info(f"User analysis completed successfully: {len(user_titles)} titles assigned")
                return user_titles, token_usage
            except Exception as e:
                logger.error(f"Error assigning titles with LLM: {e}", exc_info=True)
                return [], TokenUsage()

        except Exception as e:
            logger.error(f"Unexpected error in user analysis: {e}", exc_info=True)
            return [], TokenUsage()

    def _calculate_user_metrics(
        self,
        messages: List[ParsedMessage]
    ) -> Dict[str, UserMetrics]:
        """
        Calculate metrics for each user from parsed messages.
        
        Args:
            messages: List of parsed messages
            
        Returns:
            Dictionary mapping user open_id to UserMetrics
        """
        user_data = defaultdict(lambda: {
            'message_count': 0,
            'char_count': 0,
            'emoji_count': 0,
            'reply_count': 0,
            'hourly_distribution': defaultdict(int),
            'sender_name': '',
            'sender_avatar': ''
        })

        for msg in messages:
            try:
                user_id = msg.sender_id
                data = user_data[user_id]
                
                # Update basic counts
                data['message_count'] += 1
                
                try:
                    data['char_count'] += len(msg.content)
                except (TypeError, AttributeError) as e:
                    logger.debug(f"Error counting characters for message: {e}")
                
                # Store user info (will be the same for all messages from this user)
                try:
                    data['sender_name'] = msg.sender_name
                    data['sender_avatar'] = msg.sender_avatar
                except AttributeError as e:
                    logger.debug(f"Error accessing sender info: {e}")
                
                # Count emojis in content
                try:
                    emoji_count = self._count_emojis(msg.content)
                    data['emoji_count'] += emoji_count
                except Exception as e:
                    logger.debug(f"Error counting emojis: {e}")
                
                # Track hourly distribution
                try:
                    hour = datetime.fromtimestamp(msg.timestamp).hour
                    data['hourly_distribution'][hour] += 1
                except (ValueError, OSError) as e:
                    logger.debug(f"Error parsing timestamp: {e}")
                
                # Count replies (messages that might be replies - this is a simple heuristic)
                try:
                    if '@' in msg.content or msg.message_type == 'reply':
                        data['reply_count'] += 1
                except (TypeError, AttributeError) as e:
                    logger.debug(f"Error checking reply status: {e}")
                    
            except AttributeError as e:
                logger.warning(f"Invalid message object in metrics calculation: {e}")
                continue
            except Exception as e:
                logger.error(f"Error processing message in metrics calculation: {e}")
                continue

        # Convert to UserMetrics objects
        user_metrics = {}
        for user_id, data in user_data.items():
            try:
                avg_length = (
                    data['char_count'] / data['message_count'] 
                    if data['message_count'] > 0 
                    else 0.0
                )
                
                user_metrics[user_id] = UserMetrics(
                    message_count=data['message_count'],
                    char_count=data['char_count'],
                    avg_message_length=round(avg_length, 1),
                    emoji_count=data['emoji_count'],
                    reply_count=data['reply_count'],
                    hourly_distribution=dict(data['hourly_distribution'])
                )
                
                # Store name and avatar for later use
                user_metrics[user_id].sender_name = data['sender_name']
                user_metrics[user_id].sender_avatar = data['sender_avatar']
            except Exception as e:
                logger.error(f"Error creating UserMetrics for user {user_id}: {e}")
                continue

        return user_metrics

    def _count_emojis(self, text: str) -> int:
        """
        Count emoji characters in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Number of emojis found
        """
        # Simple emoji detection using Unicode ranges
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        return len(emoji_pattern.findall(text))

    async def _assign_titles_with_llm(
        self,
        sorted_users: List[Tuple[str, UserMetrics]],
        messages: List[ParsedMessage],
        umo: str = None
    ) -> Tuple[List[UserTitle], TokenUsage]:
        """
        Use LLM to assign titles to users based on their metrics.
        
        Args:
            sorted_users: List of (user_id, UserMetrics) tuples
            messages: Original messages for context
            umo: Unique Model Object identifier
            
        Returns:
            Tuple of (list of UserTitle objects, TokenUsage)
        """
        # Prepare user summaries with actual names
        user_summaries = []
        user_info_map = {}  # Map user_id to (name, avatar)
        
        for user_id, metrics in sorted_users:
            # Calculate activity ratios
            night_messages = sum(
                metrics.hourly_distribution.get(h, 0) 
                for h in range(0, 6)
            )
            night_ratio = (
                night_messages / metrics.message_count 
                if metrics.message_count > 0 
                else 0
            )
            emoji_ratio = (
                metrics.emoji_count / metrics.message_count 
                if metrics.message_count > 0 
                else 0
            )
            reply_ratio = (
                metrics.reply_count / metrics.message_count 
                if metrics.message_count > 0 
                else 0
            )
            
            # Store user info for later
            user_info_map[user_id] = (
                metrics.sender_name,
                metrics.sender_avatar
            )
            
            # Debug: log user info mapping
            logger.debug(f"Added to user_info_map: {user_id[:12]}... -> name={metrics.sender_name}, has_avatar={bool(metrics.sender_avatar)}")
            
            user_summaries.append({
                "name": metrics.sender_name,
                "user_id": user_id,
                "message_count": metrics.message_count,
                "avg_chars": metrics.avg_message_length,
                "emoji_ratio": round(emoji_ratio, 2),
                "night_ratio": round(night_ratio, 2),
                "reply_ratio": round(reply_ratio, 2)
            })

        # Build LLM prompt with user_id included
        users_text = "\n".join([
            f"- {user['name']} (ID: {user['user_id']}): "
            f"发言{user['message_count']}条, 平均{user['avg_chars']}字, "
            f"表情比例{user['emoji_ratio']}, 夜间发言比例{user['night_ratio']}, "
            f"回复比例{user['reply_ratio']}"
            for user in user_summaries
        ])

        prompt = f"""
请为以下群友分配合适的称号和MBTI类型。每个人只能有一个称号，每个称号只能给一个人。

可选称号：
- 龙王: 发言频繁但内容轻松的人
- 技术专家: 经常讨论技术话题的人
- 夜猫子: 经常在深夜发言的人
- 表情包军火库: 经常发表情的人
- 沉默终结者: 经常开启话题的人
- 评论家: 平均发言长度很长的人
- 阳角: 在群里很有影响力的人
- 互动达人: 经常回复别人的人
- ... (你可以自行进行拓展添加)

用户数据：
{users_text}

重要说明：
- 请使用用户的实际昵称（如上面显示的名字）
- **必须使用上面提供的完整 user_id（以 ou_ 开头的ID），不要使用用户名作为 user_id**
- 为每个用户提供具体的称号获得理由
- 称号应该反映用户的实际活动特征

请以JSON格式返回，格式如下：
[
  {{
    "name": "用户实际昵称",
    "user_id": "完整的用户ID（必须是上面括号中的ID，例如：ou_b492d551235de6197c39d22b58231180）",
    "title": "称号",
    "mbti": "MBTI类型",
    "reason": "获得此称号的具体原因（需要提到用户的实际活动数据）"
  }}
]

注意：
1. 返回的内容必须是纯JSON，不要包含markdown代码块标记或其他格式
2. user_id 必须是完整的 ID（以 ou_ 开头），不能是用户名
"""

        # Call LLM
        response = await self._call_llm_with_retry(
            prompt,
            max_tokens=1500,
            temperature=0.5,
            umo=umo
        )

        if response is None:
            logger.error("User title analysis LLM call failed")
            return [], TokenUsage()

        # Extract token usage
        token_usage = self._extract_token_usage(response)

        # Parse response
        result_text = self._extract_response_text(response)
        logger.debug(f"User title analysis raw response: {result_text[:500]}...")

        # Try to parse JSON
        try:
            json_match = re.search(r'\[.*?\]', result_text, re.DOTALL)
            if json_match:
                json_text = json_match.group()
                logger.debug(f"User title analysis JSON: {json_text[:300]}...")
                
                titles_data = json.loads(json_text)
                user_titles = []
                
                for title_data in titles_data:
                    user_id = title_data.get('user_id', '')
                    name, avatar = user_info_map.get(user_id, (title_data.get('name', ''), ''))
                    
                    # Debug: log user info mapping
                    logger.debug(f"User {user_id[:12]}... -> name={name}, has_avatar={bool(avatar)}")
                    if user_id not in user_info_map:
                        logger.warning(f"User {user_id[:12]}... not found in user_info_map. Available users: {list(user_info_map.keys())[:3]}")
                    
                    # Get metrics for this user
                    metrics = None
                    for uid, m in sorted_users:
                        if uid == user_id:
                            metrics = m
                            break
                    
                    if metrics is None:
                        metrics = UserMetrics(
                            message_count=0,
                            char_count=0,
                            avg_message_length=0.0,
                            emoji_count=0,
                            reply_count=0,
                            hourly_distribution={}
                        )
                    
                    user_titles.append(UserTitle(
                        open_id=user_id,
                        name=name,
                        avatar_url=avatar,
                        title=title_data.get('title', ''),
                        mbti=title_data.get('mbti', ''),
                        reason=title_data.get('reason', ''),
                        metrics=metrics
                    ))
                
                logger.info(f"User title analysis successful, parsed {len(user_titles)} titles")
                return user_titles, token_usage
                
        except json.JSONDecodeError as e:
            logger.error(f"User title analysis JSON parsing failed: {e}")
            logger.debug(f"Original response: {result_text}")

        return [], token_usage

    async def _call_llm_with_retry(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        umo: str = None
    ):
        """
        Call LLM provider with retry logic.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            umo: Unique Model Object identifier
            
        Returns:
            LLM response or None on failure
        """
        import asyncio
        
        timeout = self.config_manager.get_llm_timeout()
        retries = self.config_manager.get_llm_retries()
        backoff = self.config_manager.get_llm_backoff()

        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                provider = self.context.get_using_provider(umo=umo)
                if not provider:
                    logger.error("Provider is None, cannot call LLM")
                    return None
                
                coro = provider.text_chat(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return await asyncio.wait_for(coro, timeout=timeout)
                
            except asyncio.TimeoutError as e:
                last_exc = e
                logger.warning(f"LLM request timeout: attempt {attempt}, timeout={timeout}s")
            except Exception as e:
                last_exc = e
                logger.warning(f"LLM request failed: attempt {attempt}, error: {e}")
            
            # Wait before retry
            if attempt < retries:
                await asyncio.sleep(backoff * attempt)

        logger.error(f"LLM request failed after all retries: {last_exc}")
        return None

    def _extract_token_usage(self, response) -> TokenUsage:
        """Extract token usage from LLM response"""
        token_usage = TokenUsage()
        
        if hasattr(response, 'raw_completion') and response.raw_completion:
            usage = getattr(response.raw_completion, 'usage', None)
            if usage:
                token_usage.prompt_tokens = getattr(usage, 'prompt_tokens', 0) or 0
                token_usage.completion_tokens = getattr(usage, 'completion_tokens', 0) or 0
                token_usage.total_tokens = getattr(usage, 'total_tokens', 0) or 0
        
        return token_usage

    def _extract_response_text(self, response) -> str:
        """Extract text from LLM response"""
        if hasattr(response, 'completion_text'):
            return response.completion_text
        return str(response)
