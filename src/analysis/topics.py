"""
话题分析模块

负责使用 LLM 从解析后的消息中分析讨论话题。
本模块提取并总结群聊中讨论的主要话题。
"""

import json
import re
import asyncio
from typing import List, Tuple
from astrbot.api import logger
from ..models import ParsedMessage, Topic, TokenUsage


class TopicsAnalyzer:
    """
    话题分析器
    
    使用 LLM 从解析后的消息中分析讨论话题。
    分析器会格式化消息（包含真实用户名和时间戳），然后使用 LLM 提取有意义的话题及详细描述。
    """

    def __init__(self, context, config_manager):
        """
        初始化话题分析器
        
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
    ) -> Tuple[List[Topic], TokenUsage]:
        """
        从解析后的消息中分析话题
        
        Args:
            messages: ParsedMessage 对象列表，包含真实用户信息
            umo: LLM 选择的唯一模型对象标识符
            
        Returns:
            元组：(Topic 对象列表, TokenUsage)
        """
        try:
            # Validate input
            if not messages:
                logger.warning("No messages provided for topic analysis")
                return [], TokenUsage()
            
            if not isinstance(messages, list):
                logger.error(f"Invalid messages type: expected list, got {type(messages)}")
                return [], TokenUsage()
            
            # Filter messages with meaningful content
            text_messages = []
            try:
                for msg in messages:
                    try:
                        # Skip empty messages, commands, and very short messages
                        if msg.content and len(msg.content.strip()) > 2 and not msg.content.startswith("/"):
                            text_messages.append(msg)
                    except AttributeError as e:
                        logger.warning(f"Invalid message object in list: {e}")
                        continue
            except Exception as e:
                logger.error(f"Error filtering messages for topic analysis: {e}", exc_info=True)
                return [], TokenUsage()

            if not text_messages:
                logger.info("No text messages to analyze for topics after filtering")
                return [], TokenUsage()

            # Format messages with actual usernames and timestamps
            try:
                messages_text = self._format_messages_for_llm(text_messages)
            except Exception as e:
                logger.error(f"Error formatting messages for LLM: {e}", exc_info=True)
                return [], TokenUsage()
            
            # Build LLM prompt
            try:
                max_topics = self.config_manager.get_max_topics()
                prompt = self._build_topics_prompt(messages_text, max_topics)
            except Exception as e:
                logger.error(f"Error building LLM prompt: {e}", exc_info=True)
                return [], TokenUsage()
            
            # Call LLM with retry logic
            try:
                response = await self._call_llm_with_retry(prompt, umo)
                if response is None:
                    logger.error(
                        "Topics analysis LLM call failed: provider returned None. "
                        "Please check your LLM configuration and network connection."
                    )
                    return [], TokenUsage()
            except Exception as e:
                logger.error(f"Error calling LLM for topic analysis: {e}", exc_info=True)
                return [], TokenUsage()

            # Extract token usage
            try:
                token_usage = self._extract_token_usage(response)
            except Exception as e:
                logger.warning(f"Error extracting token usage: {e}")
                token_usage = TokenUsage()
            
            # Parse response
            try:
                result_text = self._extract_response_text(response)
            except Exception as e:
                logger.error(f"Error extracting response text: {e}", exc_info=True)
                return [], token_usage
            
            # Parse JSON and create Topic objects
            try:
                topics = self._parse_topics_response(result_text, max_topics)
            except Exception as e:
                logger.error(f"Error parsing topics response: {e}", exc_info=True)
                # Return fallback topic
                logger.info("Using fallback topic due to parsing error")
                return [Topic(
                    title="Group Discussion",
                    participants=["Group Members"],
                    description="Today's group chat covered various topics. Unable to extract detailed topics due to analysis error.",
                    message_count=len(text_messages)
                )], token_usage
            
            logger.info(f"Topics analysis completed successfully: {len(topics)} topics extracted")
            return topics, token_usage

        except Exception as e:
            logger.error(f"Unexpected error in topics analysis: {e}", exc_info=True)
            return [], TokenUsage()

    def _format_messages_for_llm(self, messages: List[ParsedMessage]) -> str:
        """
        格式化解析后的消息供 LLM 输入，包含真实用户名和时间戳
        
        Args:
            messages: ParsedMessage 对象列表
            
        Returns:
            格式化后的消息字符串
        """
        from datetime import datetime
        
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

    def _build_topics_prompt(self, messages_text: str, max_topics: int) -> str:
        """
        构建话题分析的 LLM 提示词
        
        Args:
            messages_text: 格式化后的消息文本
            max_topics: 要提取的最大话题数量
            
        Returns:
            完整的提示词字符串
        """
        return f"""你是一个帮我进行群聊信息总结的助手，生成总结内容时，你需要严格遵守下面的几个准则：

请分析接下来提供的群聊记录，提取出最多 {max_topics} 个主要话题。

对于每个话题，请提供：
1. 话题名称（突出主题内容，尽量简明扼要）
2. 主要参与者（最多5人）
3. 话题详细描述（包含关键信息和结论）

重要准则：
- 对于比较有价值的点，稍微用一两句话详细讲讲，比如不要生成"Nolan 和 SOV 讨论了 galgame 中关于性符号的衍生情况"这种宽泛的内容，而是生成更加具体的讨论内容，让其他人只看这个消息就能知道讨论中有价值的、有营养的信息。
- 对于其中的部分信息，你需要特意提到主题施加的主体是谁，是哪个群友做了什么事情，而不要直接生成和群友没有关系的语句。
- 对于每一条总结，尽量讲清楚前因后果，以及话题的结论，是什么，为什么，怎么做，如果用户没有讲到细节，则可以不用这么做。

好的总结示例 vs 不好的总结示例：

❌ 不好："用户讨论了技术"
✅ 好："Alice 分享了她从 MySQL 迁移到 PostgreSQL 的经验，说明主要挑战是处理 JSON 数据类型。Bob 建议使用 jsonb 类型并提供了具体的迁移脚本。群组得出结论，PostgreSQL 的 JSON 支持对他们的用例更加稳健。"

❌ 不好："大家聊了游戏"
✅ 好："Chen 和 Li 辩论了《黑暗之魂》和《艾尔登法环》哪个的 Boss 设计更好。Chen 认为《黑暗之魂》的 Boss 因为更紧凑的竞技场设计而更令人难忘，而 Li 更喜欢《艾尔登法环》的多样性和可选遭遇。讨论显示 6 位参与者中有 4 位更喜欢具有挑战性但公平的 Boss 机制。"

群聊记录：
{messages_text}

重要：必须返回标准 JSON 格式，严格遵守以下规则：
1. 只使用英文双引号 " 不要使用中文引号 " "
2. 字符串内容中的引号必须转义为 \"
3. 多个对象之间用逗号分隔
4. 数组元素之间用逗号分隔
5. 不要在 JSON 外添加任何文字说明
6. 描述内容避免使用特殊符号，用普通文字表达

请严格按照以下 JSON 格式返回，确保可以被标准 JSON 解析器解析：
[
  {{
    "topic": "话题名称",
    "contributors": ["用户1", "用户2"],
    "detail": "话题描述内容，包含具体细节、上下文和结论"
  }},
  {{
    "topic": "另一个话题",
    "contributors": ["用户3", "用户4"],
    "detail": "另一个话题的描述，说明谁做了什么以及为什么"
  }}
]

注意：返回的内容必须是纯 JSON，不要包含 markdown 代码块标记或其他格式"""

    async def _call_llm_with_retry(self, prompt: str, umo: str = None):
        """
        调用 LLM 提供者，带重试逻辑
        
        Args:
            prompt: 发送给 LLM 的提示词
            umo: 唯一模型对象标识符
            
        Returns:
            LLM 响应，失败时返回 None
        """
        try:
            timeout = self.config_manager.get_llm_timeout()
            retries = self.config_manager.get_llm_retries()
            backoff = self.config_manager.get_llm_backoff()
        except Exception as e:
            logger.error(f"Error getting LLM configuration: {e}. Using defaults.", exc_info=True)
            timeout = 30
            retries = 3
            backoff = 2

        # Get custom provider parameters
        try:
            custom_api_key = self.config_manager.get_custom_api_key()
            custom_api_base = self.config_manager.get_custom_api_base_url()
            custom_model = self.config_manager.get_custom_model_name()
        except Exception as e:
            logger.warning(f"Error getting custom provider config: {e}. Using default provider.")
            custom_api_key = None
            custom_api_base = None
            custom_model = None

        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                if custom_api_key and custom_api_base and custom_model:
                    logger.info(f"Using custom LLM provider (attempt {attempt}/{retries}): {custom_api_base} model={custom_model}")
                    try:
                        import aiohttp
                    except ImportError as e:
                        logger.error(f"aiohttp not available for custom provider: {e}")
                        return None
                    
                    try:
                        async with aiohttp.ClientSession() as session:
                            headers = {
                                "Authorization": f"Bearer {custom_api_key}",
                                "Content-Type": "application/json"
                            }
                            payload = {
                                "model": custom_model,
                                "messages": [{"role": "user", "content": prompt}],
                                "max_tokens": 10000,
                                "temperature": 0.6
                            }
                            aio_timeout = aiohttp.ClientTimeout(total=timeout)
                            async with session.post(custom_api_base, json=payload, headers=headers, timeout=aio_timeout) as resp:
                                if resp.status != 200:
                                    error_text = await resp.text()
                                    error_msg = f"Custom LLM provider request failed: HTTP {resp.status}, content: {error_text[:200]}"
                                    logger.error(error_msg)
                                    raise Exception(error_msg)
                                
                                try:
                                    response_json = await resp.json()
                                except Exception as json_err:
                                    error_text = await resp.text()
                                    logger.error(
                                        f"Custom LLM provider response JSON parsing failed: {json_err}, "
                                        f"content: {error_text[:200]}"
                                    )
                                    raise
                                
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
                                        raise Exception("Invalid response format from custom LLM provider")
                                except Exception as key_err:
                                    logger.error(
                                        f"Custom LLM response structure parsing failed: {key_err}, "
                                        f"response: {str(response_json)[:200]}"
                                    )
                                    raise
                                
                                # Create compatible response object
                                class CustomResponse:
                                    completion_text = content
                                    raw_completion = response_json
                                
                                logger.info(f"Custom LLM request successful on attempt {attempt}")
                                return CustomResponse()
                    except aiohttp.ClientError as e:
                        logger.error(f"Network error with custom LLM provider: {e}")
                        raise
                else:
                    # Use AstrBot provider
                    try:
                        provider = self.context.get_using_provider(umo=umo)
                        if not provider:
                            error_msg = "LLM provider is None. Please configure an LLM provider in AstrBot settings."
                            logger.error(error_msg)
                            return None
                        
                        logger.info(f"Using LLM provider (attempt {attempt}/{retries}): {provider}")
                        coro = provider.text_chat(prompt=prompt, max_tokens=10000, temperature=0.6)
                        result = await asyncio.wait_for(coro, timeout=timeout)
                        logger.info(f"LLM request successful on attempt {attempt}")
                        return result
                    except AttributeError as e:
                        logger.error(f"LLM provider method error: {e}. The provider may not support text_chat.", exc_info=True)
                        return None
                    
            except asyncio.TimeoutError as e:
                last_exc = e
                logger.warning(
                    f"LLM request timeout on attempt {attempt}/{retries} (timeout={timeout}s). "
                    f"Consider increasing the timeout in configuration."
                )
            except Exception as e:
                last_exc = e
                logger.warning(f"LLM request failed on attempt {attempt}/{retries}: {e}", exc_info=(attempt == retries))
            
            # Wait before retry
            if attempt < retries:
                wait_time = backoff * attempt
                logger.info(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)

        logger.error(
            f"All {retries} LLM retry attempts failed. Last error: {last_exc}. "
            f"Please check your LLM configuration and network connection."
        )
        return None

    def _extract_token_usage(self, response) -> TokenUsage:
        """
        Extract token usage from LLM response.
        
        Args:
            response: LLM response object
            
        Returns:
            TokenUsage object
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
        Extract text from LLM response.
        
        Args:
            response: LLM response object
            
        Returns:
            Response text
        """
        if hasattr(response, 'completion_text'):
            return response.completion_text
        else:
            return str(response)

    def _parse_topics_response(self, result_text: str, max_topics: int) -> List[Topic]:
        """
        Parse LLM response and extract topics.
        
        Args:
            result_text: Raw LLM response text
            max_topics: Maximum number of topics to return
            
        Returns:
            List of Topic objects
        """
        try:
            # Try to extract JSON
            json_match = re.search(r'\[.*?\]', result_text, re.DOTALL)
            if json_match:
                json_text = json_match.group()
                logger.debug(f"Topics analysis JSON raw: {json_text[:500]}...")

                # Fix and clean JSON
                json_text = self._fix_json(json_text)
                logger.debug(f"Fixed JSON: {json_text[:300]}...")

                topics_data = json.loads(json_text)
                topics = []
                for topic_dict in topics_data[:max_topics]:
                    # Map old field names to new Topic model
                    topic = Topic(
                        title=topic_dict.get("topic", ""),
                        participants=topic_dict.get("contributors", []),
                        description=topic_dict.get("detail", ""),
                        message_count=0  # Will be calculated later if needed
                    )
                    topics.append(topic)
                
                logger.info(f"Successfully parsed {len(topics)} topics")
                return topics
            else:
                logger.warning(f"No JSON format found in response: {result_text[:200]}...")
        except json.JSONDecodeError as e:
            logger.error(f"Topics analysis JSON parsing failed: {e}")
            logger.debug(f"Fixed JSON: {json_text if 'json_text' in locals() else 'N/A'}")
            logger.debug(f"Raw response: {result_text}")

            # Fallback: try regex extraction
            topics = self._extract_topics_with_regex(result_text, max_topics)
            if topics:
                logger.info(f"Regex extraction successful: {len(topics)} topics")
                return topics
            else:
                # Final fallback
                logger.info("Regex extraction failed, using default topic")
                return [Topic(
                    title="Group Discussion",
                    participants=["Group Members"],
                    description="Today's group chat covered various topics with rich content",
                    message_count=0
                )]

        return []

    def _fix_json(self, text: str) -> str:
        """
        Fix common JSON format issues.
        
        Args:
            text: Raw JSON text
            
        Returns:
            Fixed JSON text
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

    def _extract_topics_with_regex(self, result_text: str, max_topics: int) -> List[Topic]:
        """
        Extract topics using regex as fallback.
        
        Args:
            result_text: Raw LLM response text
            max_topics: Maximum number of topics to extract
            
        Returns:
            List of Topic objects
        """
        try:
            topics = []

            # Regex pattern to match topic objects
            topic_pattern = r'\{\s*"topic":\s*"([^"]+)"\s*,\s*"contributors":\s*\[([^\]]+)\]\s*,\s*"detail":\s*"([^"]*(?:\\.[^"]*)*)"\s*\}'
            matches = re.findall(topic_pattern, result_text, re.DOTALL)

            if not matches:
                # Try more lenient matching
                topic_pattern = r'"topic":\s*"([^"]+)"[^}]*"contributors":\s*\[([^\]]+)\][^}]*"detail":\s*"([^"]*(?:\\.[^"]*)*)"'
                matches = re.findall(topic_pattern, result_text, re.DOTALL)

            for match in matches[:max_topics]:
                topic_name = match[0].strip()
                contributors_str = match[1].strip()
                detail = match[2].strip()

                # Clean escaped characters in detail
                detail = detail.replace('\\"', '"').replace('\\n', ' ').replace('\\t', ' ')

                # Parse contributors list
                contributors = []
                for contrib in re.findall(r'"([^"]+)"', contributors_str):
                    contributors.append(contrib.strip())

                if not contributors:
                    contributors = ["Group Members"]

                topics.append(Topic(
                    title=topic_name,
                    participants=contributors[:5],  # Max 5 participants
                    description=detail,
                    message_count=0
                ))

            return topics
        except Exception as e:
            logger.error(f"Regex extraction failed: {e}")
            return []
