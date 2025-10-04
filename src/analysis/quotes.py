"""
金句分析模块

负责使用 LLM 从解析后的消息中提取令人难忘的金句。
本模块识别有影响力、令人难忘的语句，并正确归属发言者。
"""

import json
import re
import asyncio
from typing import List, Tuple
from datetime import datetime
from astrbot.api import logger
from ..models import ParsedMessage, Quote, TokenUsage


class QuotesAnalyzer:
    """
    金句分析器
    
    使用 LLM 分析消息以提取金句。
    分析器会按质量和长度过滤消息，然后使用 LLM 识别最有影响力、最令人难忘或最有洞察力的语句。
    """

    def __init__(self, context, config_manager):
        """
        初始化金句分析器
        
        Args:
            context: AstrBot 上下文，用于访问 LLM 提供者
            config_manager: 配置管理器
        """
        self.context = context
        self.config_manager = config_manager

    async def analyze(
        self,
        messages: List[ParsedMessage],
        umo: str = None
    ) -> Tuple[List[Quote], TokenUsage]:
        """
        分析消息以提取金句
        
        Args:
            messages: ParsedMessage 对象列表，包含真实用户信息
            umo: LLM 选择的唯一模型对象标识符
            
        Returns:
            元组：(Quote 对象列表, TokenUsage)
        """
        try:
            # Filter messages by length and content quality
            quality_messages = self._filter_quality_messages(messages)
            
            if not quality_messages:
                logger.info("No quality messages found for quote extraction")
                return [], TokenUsage()

            # Format messages with actual sender names
            messages_text = self._format_messages_for_llm(quality_messages)
            
            # Build LLM prompt
            max_quotes = self.config_manager.get_max_golden_quotes()
            prompt = self._build_quotes_prompt(messages_text, max_quotes)
            
            # Call LLM
            response = await self._call_llm_with_retry(prompt, umo)
            if response is None:
                logger.error("Quote extraction LLM call failed: provider returned None")
                return [], TokenUsage()

            # Extract token usage
            token_usage = self._extract_token_usage(response)
            
            # Parse response
            result_text = self._extract_response_text(response)
            logger.debug(f"金句分析原始响应（前500字符）: {result_text[:500]}...")
            
            # Parse JSON and create Quote objects
            quotes = self._parse_quotes_response(result_text, quality_messages, max_quotes)
            logger.info(f"金句解析结果: 成功提取 {len(quotes)} 条金句")
            
            logger.info(f"Quote extraction completed: {len(quotes)} quotes extracted")
            return quotes, token_usage

        except Exception as e:
            logger.error(f"Quote extraction failed: {e}", exc_info=True)
            return [], TokenUsage()

    def _filter_quality_messages(self, messages: List[ParsedMessage]) -> List[ParsedMessage]:
        """
        按长度和内容质量过滤消息
        
        Args:
            messages: 所有 ParsedMessage 对象列表
            
        Returns:
            过滤后的高质量消息列表
        """
        quality_messages = []
        filtered_stats = {
            'too_short': 0,
            'too_long': 0,
            'starts_with_url': 0,
            'too_many_emojis': 0,
            'passed': 0
        }
        
        for msg in messages:
            content = msg.content.strip()
            
            # Skip empty messages
            if not content:
                continue
            
            # Skip commands
            if content.startswith('/'):
                continue
            
            # Skip very short messages (less than 10 characters)
            if len(content) < 10:
                filtered_stats['too_short'] += 1
                continue
            
            # Skip very long messages (more than 200 characters)
            if len(content) > 200:
                filtered_stats['too_long'] += 1
                continue
            
            # Skip messages that are just URLs
            if content.startswith('http://') or content.startswith('https://'):
                filtered_stats['starts_with_url'] += 1
                continue
            
            # Skip messages that are mostly emojis
            emoji_pattern = re.compile(
                "["
                "\U0001F600-\U0001F64F"
                "\U0001F300-\U0001F5FF"
                "\U0001F680-\U0001F6FF"
                "\U0001F1E0-\U0001F1FF"
                "\U00002702-\U000027B0"
                "\U000024C2-\U0001F251"
                "]+",
                flags=re.UNICODE
            )
            emoji_count = len(emoji_pattern.findall(content))
            if emoji_count > len(content) / 3:  # More than 1/3 emojis
                filtered_stats['too_many_emojis'] += 1
                continue
            
            filtered_stats['passed'] += 1
            quality_messages.append(msg)
        
        logger.info(f"消息过滤统计: 总消息={len(messages)}, 通过={filtered_stats['passed']}, "
                   f"太短={filtered_stats['too_short']}, 太长={filtered_stats['too_long']}, "
                   f"URL={filtered_stats['starts_with_url']}, 表情过多={filtered_stats['too_many_emojis']}")
        
        # 如果通过的消息太少，输出一些示例
        if filtered_stats['passed'] < 10:
            logger.info(f"通过过滤的消息示例（前3条）:")
            for i, msg in enumerate(quality_messages[:3]):
                logger.info(f"  {i+1}. [{msg.sender_name}] {msg.content[:80]}...")
        
        return quality_messages

    def _format_messages_for_llm(self, messages: List[ParsedMessage]) -> str:
        """
        格式化解析后的消息供 LLM 输入，包含真实用户名和时间戳
        
        Args:
            messages: ParsedMessage 对象列表
            
        Returns:
            格式化后的消息字符串
        """
        formatted_messages = []
        
        for msg in messages:
            # Convert timestamp to readable time
            time_str = datetime.fromtimestamp(msg.timestamp).strftime("%H:%M")
            
            # Clean message content
            content = self._clean_message_content(msg.content)
            
            # Format: [HH:MM] Username: content
            formatted_messages.append(f"[{time_str}] {msg.sender_name}: {content}")
        
        return "\n".join(formatted_messages)

    def _clean_message_content(self, content: str) -> str:
        """
        清理消息内容以避免 JSON 解析问题
        
        Args:
            content: 原始消息内容
            
        Returns:
            清理后的内容
        """
        # Replace Chinese quotes with English quotes
        content = content.replace('"', '"').replace('"', '"')
        content = content.replace(''', "'").replace(''', "'")
        
        # Remove or replace special characters
        content = content.replace('\n', ' ').replace('\r', ' ')
        content = content.replace('\t', ' ')
        
        # Remove control characters
        content = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', content)
        
        return content.strip()

    def _build_quotes_prompt(self, messages_text: str, max_quotes: int) -> str:
        """
        构建金句提取的 LLM 提示词
        
        Args:
            messages_text: 格式化后的消息文本
            max_quotes: 要提取的最大金句数量
            
        Returns:
            完整的提示词字符串
        """
        return f"""你是一个帮助从群聊对话中提取令人难忘金句的助手。

请从以下群聊记录中挑选出最多 {max_quotes} 句最具冲击力、最令人惊叹的"金句"。

选择标准：
一个好的金句应该：
1. **有冲击力**：让人思考、发笑或有所感触
2. **令人难忘**：从普通对话中脱颖而出
3. **有洞察力**：包含智慧、幽默或独特视角
4. **独立完整**：不需要太多上下文就能理解
5. **真实自然**：代表真实的人类表达

好的金句示例：

✅ 好："我发现调试就像是在侦探电影里当侦探，但你同时也是凶手。" - Alice
   理由：幽默、有共鸣，对编程有深刻见解

✅ 好："种树最好的时间是20年前，其次是现在，第三好的时间是在你研究完哪种树长得最快之后。" - Bob
   理由：对名言的巧妙改编，展现个性

✅ 好："我不是总测试我的代码，但当我测试时，我在生产环境测试。" - Chen
   理由：自嘲式幽默，引起开发者共鸣

❌ 不好："哈哈"
   理由：太短，没有实质内容

❌ 不好："我同意你说的"
   理由：不令人难忘，没有独特视角

❌ 不好："我们3点见"
   理由：纯功能性，没有情感或智力冲击

群聊记录：
{messages_text}

重要说明：
- 选择真正有趣或令人难忘的金句
- 包含说这句话的真实用户名
- 为每个金句提供具体的选择理由
- 注重质量而非数量 - 如果没有足够好的金句，返回较少的也可以

请严格按照以下 JSON 格式返回：
[
  {{
    "content": "金句原文",
    "sender_name": "发言人的真实用户名",
    "timestamp": 1234567890,
    "reason": "选择这句话的具体理由（例如：'对调试的幽默看法，引起开发者共鸣'）"
  }},
  {{
    "content": "另一个金句",
    "sender_name": "另一个用户名",
    "timestamp": 1234567891,
    "reason": "另一个具体理由"
  }}
]

注意：只返回有效的 JSON，不要包含 markdown 代码块或其他格式"""

    async def _call_llm_with_retry(self, prompt: str, umo: str = None):
        """
        调用 LLM 提供者，带重试逻辑
        
        Args:
            prompt: 发送给 LLM 的提示词
            umo: 唯一模型对象标识符
            
        Returns:
            LLM 响应，失败时返回 None
        """
        timeout = self.config_manager.get_llm_timeout()
        retries = self.config_manager.get_llm_retries()
        backoff = self.config_manager.get_llm_backoff()

        # Get custom provider parameters
        custom_api_key = self.config_manager.get_custom_api_key()
        custom_api_base = self.config_manager.get_custom_api_base_url()
        custom_model = self.config_manager.get_custom_model_name()

        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                if custom_api_key and custom_api_base and custom_model:
                    logger.info(f"Using custom LLM provider: {custom_api_base} model={custom_model}")
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        headers = {
                            "Authorization": f"Bearer {custom_api_key}",
                            "Content-Type": "application/json"
                        }
                        payload = {
                            "model": custom_model,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": 8000,
                            "temperature": 0.7
                        }
                        aio_timeout = aiohttp.ClientTimeout(total=timeout)
                        async with session.post(custom_api_base, json=payload, headers=headers, timeout=aio_timeout) as resp:
                            if resp.status != 200:
                                error_text = await resp.text()
                                logger.error(f"Custom LLM provider request failed: HTTP {resp.status}, content: {error_text}")
                            try:
                                response_json = await resp.json()
                            except Exception as json_err:
                                error_text = await resp.text()
                                logger.error(f"Custom LLM provider response JSON parsing failed: {json_err}, content: {error_text}")
                                return None
                            
                            # Compatible with OpenAI format
                            content = None
                            try:
                                choices = response_json.get("choices")
                                if choices and isinstance(choices, list) and len(choices) > 0:
                                    message = choices[0].get("message")
                                    if message and isinstance(message, dict):
                                        content = message.get("content")
                                if content is None:
                                    logger.error(f"Custom LLM response format error: {response_json}")
                                    return None
                            except Exception as key_err:
                                logger.error(f"Custom LLM response structure parsing failed: {key_err}, response: {response_json}")
                                return None
                            
                            # Create compatible response object
                            class CustomResponse:
                                completion_text = content
                                raw_completion = response_json
                            return CustomResponse()
                else:
                    # Use AstrBot provider
                    provider = self.context.get_using_provider(umo=umo)
                    if not provider:
                        logger.error("Provider is None, cannot call text_chat")
                        return None
                    
                    logger.info(f"Using LLM provider: {provider}")
                    coro = provider.text_chat(prompt=prompt, max_tokens=8000, temperature=0.7)
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

        logger.error(f"All LLM retry attempts failed: {last_exc}")
        return None

    def _extract_token_usage(self, response) -> TokenUsage:
        """
        从 LLM 响应中提取 token 使用情况
        
        Args:
            response: LLM 响应对象
            
        Returns:
            TokenUsage 对象
        """
        token_usage = TokenUsage()
        try:
            if getattr(response, 'raw_completion', None) is not None:
                usage = getattr(response.raw_completion, 'usage', None)
                if usage:
                    token_usage.prompt_tokens = getattr(usage, 'prompt_tokens', 0) or 0
                    token_usage.completion_tokens = getattr(usage, 'completion_tokens', 0) or 0
                    token_usage.total_tokens = getattr(usage, 'total_tokens', 0) or 0
        except Exception as e:
            logger.debug(f"Failed to extract token usage: {e}")
        
        return token_usage

    def _extract_response_text(self, response) -> str:
        """
        从 LLM 响应中提取文本
        
        Args:
            response: LLM 响应对象
            
        Returns:
            响应文本
        """
        if hasattr(response, 'completion_text'):
            return response.completion_text
        else:
            return str(response)

    def _parse_quotes_response(
        self,
        result_text: str,
        messages: List[ParsedMessage],
        max_quotes: int
    ) -> List[Quote]:
        """
        解析 LLM 响应并提取金句
        
        Args:
            result_text: 原始 LLM 响应文本
            messages: 原始消息列表，用于查找发送者信息
            max_quotes: 返回的最大金句数量
            
        Returns:
            Quote 对象列表
        """
        # Create a lookup map for sender info
        sender_map = {}
        for msg in messages:
            sender_map[msg.sender_name] = {
                'avatar': msg.sender_avatar,
                'timestamp': msg.timestamp
            }
        
        try:
            # Try to extract JSON
            json_match = re.search(r'\[.*?\]', result_text, re.DOTALL)
            if json_match:
                json_text = json_match.group()
                logger.info(f"找到 JSON 格式，长度: {len(json_text)} 字符")
                logger.debug(f"金句提取 JSON 原文（前500字符）: {json_text[:500]}...")

                # Fix and clean JSON
                json_text = self._fix_json(json_text)
                logger.debug(f"修复后的 JSON（前300字符）: {json_text[:300]}...")

                quotes_data = json.loads(json_text)
                logger.info(f"JSON 解析成功，包含 {len(quotes_data)} 个金句对象")
                quotes = []
                
                for idx, quote_dict in enumerate(quotes_data[:max_quotes]):
                    logger.debug(f"处理第 {idx+1} 个金句: {quote_dict}")
                    
                    sender_name = quote_dict.get("sender_name", "Unknown")
                    content = quote_dict.get("content", "")
                    reason = quote_dict.get("reason", "")
                    timestamp = quote_dict.get("timestamp", 0)
                    
                    # 验证必需字段
                    if not content:
                        logger.warning(f"第 {idx+1} 个金句缺少 content 字段，跳过")
                        continue
                    
                    if not sender_name or sender_name == "Unknown":
                        logger.warning(f"第 {idx+1} 个金句缺少 sender_name 字段，跳过")
                        continue
                    
                    # Get sender avatar from lookup map
                    sender_info = sender_map.get(sender_name, {})
                    sender_avatar = sender_info.get('avatar', '')
                    
                    # Use timestamp from message if available, otherwise use from JSON
                    if not timestamp and sender_name in sender_map:
                        timestamp = sender_info.get('timestamp', 0)
                    
                    quote = Quote(
                        content=content,
                        sender_name=sender_name,
                        sender_avatar=sender_avatar,
                        timestamp=timestamp,
                        reason=reason
                    )
                    quotes.append(quote)
                    logger.debug(f"成功添加金句: {sender_name}: {content[:50]}...")
                
                if quotes:
                    logger.info(f"成功解析 {len(quotes)} 条金句")
                else:
                    logger.warning(f"JSON 解析成功但没有提取到有效金句。原始数据包含 {len(quotes_data)} 个对象")
                return quotes
            else:
                logger.warning(f"响应中未找到 JSON 格式")
                logger.info(f"完整响应内容: {result_text}")
        except json.JSONDecodeError as e:
            logger.error(f"金句提取 JSON 解析失败: {e}")
            logger.error(f"修复后的 JSON: {json_text if 'json_text' in locals() else 'N/A'}")
            logger.error(f"原始响应: {result_text}")

            # Fallback: try regex extraction
            logger.info("尝试使用正则表达式提取金句...")
            quotes = self._extract_quotes_with_regex(result_text, sender_map, max_quotes)
            if quotes:
                logger.info(f"正则表达式提取成功: {len(quotes)} 条金句")
                return quotes
            else:
                logger.warning("正则表达式提取也失败了")

        logger.warning("所有金句提取方法都失败，返回空列表")
        return []

    def _fix_json(self, text: str) -> str:
        """
        修复常见的 JSON 格式问题
        
        Args:
            text: 原始 JSON 文本
            
        Returns:
            修复后的 JSON 文本
        """
        # Remove markdown code block markers
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)

        # Basic cleaning
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = re.sub(r'\s+', ' ', text)

        # Replace Chinese quotes with English quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")

        # Fix truncated JSON
        if not text.endswith(']'):
            last_complete = text.rfind('}')
            if last_complete > 0:
                text = text[:last_complete + 1] + ']'

        # Fix common JSON format issues
        # 1. Fix missing commas between objects
        text = re.sub(r'}\s*{', '}, {', text)

        # 2. Ensure field names have quotes
        text = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)

        # 3. Remove extra commas
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)

        return text

    def _extract_quotes_with_regex(
        self,
        result_text: str,
        sender_map: dict,
        max_quotes: int
    ) -> List[Quote]:
        """
        使用正则表达式提取金句（降级方案）
        
        Args:
            result_text: 原始 LLM 响应文本
            sender_map: 发送者名称到其信息的映射
            max_quotes: 要提取的最大金句数量
            
        Returns:
            Quote 对象列表
        """
        try:
            quotes = []

            # Regex pattern to match quote objects
            quote_pattern = r'\{\s*"content":\s*"([^"]*(?:\\.[^"]*)*)"\s*,\s*"sender_name":\s*"([^"]+)"\s*,\s*"timestamp":\s*(\d+)\s*,\s*"reason":\s*"([^"]*(?:\\.[^"]*)*)"\s*\}'
            matches = re.findall(quote_pattern, result_text, re.DOTALL)

            if not matches:
                # Try more lenient matching
                quote_pattern = r'"content":\s*"([^"]*(?:\\.[^"]*)*)"\s*[^}]*"sender_name":\s*"([^"]+)"[^}]*"reason":\s*"([^"]*(?:\\.[^"]*)*)"'
                matches = re.findall(quote_pattern, result_text, re.DOTALL)
                
                for match in matches[:max_quotes]:
                    content = match[0].strip()
                    sender_name = match[1].strip()
                    reason = match[2].strip()
                    
                    # Clean escaped characters
                    content = content.replace('\\"', '"').replace('\\n', ' ').replace('\\t', ' ')
                    reason = reason.replace('\\"', '"').replace('\\n', ' ').replace('\\t', ' ')
                    
                    # Get sender info
                    sender_info = sender_map.get(sender_name, {})
                    sender_avatar = sender_info.get('avatar', '')
                    timestamp = sender_info.get('timestamp', 0)
                    
                    quotes.append(Quote(
                        content=content,
                        sender_name=sender_name,
                        sender_avatar=sender_avatar,
                        timestamp=timestamp,
                        reason=reason
                    ))
            else:
                for match in matches[:max_quotes]:
                    content = match[0].strip()
                    sender_name = match[1].strip()
                    timestamp = int(match[2])
                    reason = match[3].strip()
                    
                    # Clean escaped characters
                    content = content.replace('\\"', '"').replace('\\n', ' ').replace('\\t', ' ')
                    reason = reason.replace('\\"', '"').replace('\\n', ' ').replace('\\t', ' ')
                    
                    # Get sender avatar
                    sender_info = sender_map.get(sender_name, {})
                    sender_avatar = sender_info.get('avatar', '')
                    
                    quotes.append(Quote(
                        content=content,
                        sender_name=sender_name,
                        sender_avatar=sender_avatar,
                        timestamp=timestamp,
                        reason=reason
                    ))

            return quotes
        except Exception as e:
            logger.error(f"Regex extraction failed: {e}")
            return []
