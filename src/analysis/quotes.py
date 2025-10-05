"""
金句分析模块

负责使用LLM从解析后的消息中提取令人难忘的金句
本模块识别有影响力、令人难忘的语句，并正确归属发言者
"""

import json
import re
from typing import List, Tuple
from datetime import datetime
from astrbot.api import logger
from ..models import ParsedMessage, Quote, TokenUsage
from ..utils.llm_helper import LLMHelper


class QuotesAnalyzer:
    """
    金句分析器

    使用LLM分析消息以提取金句
    分析器会按质量和长度过滤消息，然后使用LLM识别最有影响力、最令人难忘或最有洞察力的语句
    """

    def __init__(self, context, config_manager):
        """
        初始化金句分析器

        Args:
            context: AstrBot上下文，用于访问LLM提供者
            config_manager: 配置管理器
        """
        self.context = context
        self.config_manager = config_manager
        self.llm_helper = LLMHelper(context, config_manager)

    async def analyze(
        self, messages: List[ParsedMessage], umo: str = None
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
            # 按长度和内容质量过滤消息
            quality_messages = self._filter_quality_messages(messages)

            if not quality_messages:
                logger.info("未找到适合提取金句的高质量消息")
                return [], TokenUsage()

            # 使用实际发送者名称格式化消息
            messages_text = self._format_messages_for_llm(quality_messages)

            # 构建LLM提示词
            max_quotes = self.config_manager.get_max_golden_quotes()
            prompt = self._build_quotes_prompt(messages_text, max_quotes)

            # 调用LLM
            response = await self.llm_helper.call_llm_with_retry(
                prompt, max_tokens=8000, temperature=0.7, umo=umo
            )
            if response is None:
                logger.error("金句提取LLM调用失败: 提供者返回None")
                return [], TokenUsage()

            # 提取token使用量
            token_usage = self.llm_helper.extract_token_usage(response)

            # 解析响应
            result_text = self.llm_helper.extract_response_text(response)
            logger.info(f"=== 金句提取LLM完整响应 ===")
            logger.info(result_text)
            logger.info(f"=== 响应结束 ===")
            logger.debug(f"金句分析原始响应（前500字符）: {result_text[:500]}...")

            # 解析JSON并创建Quote对象
            quotes = self._parse_quotes_response(
                result_text, quality_messages, max_quotes
            )
            logger.info(f"金句解析结果: 成功提取 {len(quotes)} 条金句")

            logger.info(f"金句提取完成: 提取了{len(quotes)}条金句")
            return quotes, token_usage

        except Exception as e:
            logger.error(f"金句提取失败: {e}", exc_info=True)
            return [], TokenUsage()

    def _filter_quality_messages(
        self, messages: List[ParsedMessage]
    ) -> List[ParsedMessage]:
        """
        按长度和内容质量过滤消息

        Args:
            messages: 所有 ParsedMessage 对象列表

        Returns:
            过滤后的高质量消息列表
        """
        quality_messages = []
        filtered_stats = {
            "too_short": 0,      # 太短
            "too_long": 0,       # 太长
            "starts_with_url": 0, # 以URL开头
            "too_many_emojis": 0, # 表情过多
            "passed": 0,         # 通过
        }

        for msg in messages:
            content = msg.content.strip()

            # 跳过空消息
            if not content:
                continue

            # 跳过命令
            if content.startswith("/"):
                continue

            # 跳过很短的消息（少于10个字符）
            if len(content) < 10:
                filtered_stats["too_short"] += 1
                continue

            # 跳过很长的消息（超过200个字符）
            if len(content) > 200:
                filtered_stats["too_long"] += 1
                continue

            # 跳过仅包含URL的消息
            if content.startswith("http://") or content.startswith("https://"):
                filtered_stats["starts_with_url"] += 1
                continue

            # 跳过主要是表情的消息
            emoji_pattern = re.compile(
                "["
                "\U0001f600-\U0001f64f"
                "\U0001f300-\U0001f5ff"
                "\U0001f680-\U0001f6ff"
                "\U0001f1e0-\U0001f1ff"
                "\U00002702-\U000027b0"
                "\U000024c2-\U0001f251"
                "]+",
                flags=re.UNICODE,
            )
            emoji_count = len(emoji_pattern.findall(content))
            if emoji_count > len(content) / 3:  # 超过1/3是表情
                filtered_stats["too_many_emojis"] += 1
                continue

            filtered_stats["passed"] += 1
            quality_messages.append(msg)

        logger.info(
            f"消息过滤统计: 总消息={len(messages)}, 通过={filtered_stats['passed']}, "
            f"太短={filtered_stats['too_short']}, 太长={filtered_stats['too_long']}, "
            f"URL={filtered_stats['starts_with_url']}, 表情过多={filtered_stats['too_many_emojis']}"
        )

        # 输出一些示例消息
        logger.info("通过过滤的消息示例（前3条）:")
        for i, msg in enumerate(quality_messages[:3]):
            logger.info(f"  {i + 1}. [{msg.sender_name}] {msg.content[:80]}...")
        
        # 如果通过的消息太少，给出警告
        if filtered_stats["passed"] < 5:
            logger.warning(f"⚠️ 通过过滤的消息太少（{filtered_stats['passed']}条），可能无法提取有效金句")

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
            # 转换时间戳为可读时间
            time_str = datetime.fromtimestamp(msg.timestamp).strftime("%H:%M")

            # 清理消息内容
            content = self._clean_message_content(msg.content)

            # 格式: [HH:MM] 用户名: 内容
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
        # 将中文引号替换为英文引号
        content = content.replace('"', '"').replace('"', '"')
        content = content.replace(""", "'").replace(""", "'")

        # 移除或替换特殊字符
        content = content.replace("\n", " ").replace("\r", " ")
        content = content.replace("\t", " ")

        # 移除控制字符
        content = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", content)

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
- 注重质量而非数量 - 如果没有足够好的金句，返回较少的也可以，但是一定要有至少一句。

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

    def _parse_quotes_response(
        self, result_text: str, messages: List[ParsedMessage], max_quotes: int
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
        # 创建发送者信息的查找映射
        sender_map = {}
        for msg in messages:
            sender_map[msg.sender_name] = {
                "avatar": msg.sender_avatar,
                "timestamp": msg.timestamp,
            }

        try:
            # 尝试提取JSON
            json_match = re.search(r"\[.*?\]", result_text, re.DOTALL)
            if json_match:
                json_text = json_match.group()
                logger.info(f"找到 JSON 格式，长度: {len(json_text)} 字符")
                logger.debug(f"金句提取 JSON 原文（前500字符）: {json_text[:500]}...")

                # 修复并清理JSON
                json_text = self._fix_json(json_text)
                logger.debug(f"修复后的 JSON（前300字符）: {json_text[:300]}...")

                quotes_data = json.loads(json_text)
                logger.info(f"JSON 解析成功，包含 {len(quotes_data)} 个金句对象")
                quotes = []

                for idx, quote_dict in enumerate(quotes_data[:max_quotes]):
                    logger.debug(f"处理第 {idx + 1} 个金句: {quote_dict}")

                    sender_name = quote_dict.get("sender_name", "Unknown")
                    content = quote_dict.get("content", "")
                    reason = quote_dict.get("reason", "")
                    timestamp = quote_dict.get("timestamp", 0)

                    # 验证必需字段
                    if not content:
                        logger.warning(f"第 {idx + 1} 个金句缺少 content 字段，跳过")
                        continue

                    if not sender_name or sender_name == "Unknown":
                        logger.warning(
                            f"第 {idx + 1} 个金句缺少 sender_name 字段，跳过"
                        )
                        continue

                    # 从查找映射中获取发送者头像
                    sender_info = sender_map.get(sender_name, {})
                    sender_avatar = sender_info.get("avatar", "")

                    # 如果消息中有时间戳则使用，否则使用JSON中的
                    if not timestamp and sender_name in sender_map:
                        timestamp = sender_info.get("timestamp", 0)

                    quote = Quote(
                        content=content,
                        sender_name=sender_name,
                        sender_avatar=sender_avatar,
                        timestamp=timestamp,
                        reason=reason,
                    )
                    quotes.append(quote)
                    logger.debug(f"成功添加金句: {sender_name}: {content[:50]}...")

                if quotes:
                    logger.info(f"成功解析 {len(quotes)} 条金句")
                else:
                    logger.warning(
                        f"JSON 解析成功但没有提取到有效金句。原始数据包含 {len(quotes_data)} 个对象"
                    )
                return quotes
            else:
                logger.warning("响应中未找到 JSON 格式")
                logger.info(f"完整响应内容: {result_text}")
        except json.JSONDecodeError as e:
            logger.error(f"金句提取JSON解析失败: {e}")
            logger.error(
                f"修复后的JSON: {json_text if 'json_text' in locals() else 'N/A'}"
            )
            logger.error(f"原始响应: {result_text}")

            # 降级方案：尝试正则表达式提取
            logger.info("尝试使用正则表达式提取金句...")
            quotes = self._extract_quotes_with_regex(
                result_text, sender_map, max_quotes
            )
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
        # 移除markdown代码块标记
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)

        # 基础清理
        text = text.replace("\n", " ").replace("\r", " ")
        text = re.sub(r"\s+", " ", text)

        # 将中文引号替换为英文引号
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(""", "'").replace(""", "'")

        # 修复截断的JSON
        if not text.endswith("]"):
            last_complete = text.rfind("}")
            if last_complete > 0:
                text = text[: last_complete + 1] + "]"

        # 修复常见JSON格式问题
        # 1. 修复对象之间缺少的逗号
        text = re.sub(r"}\s*{", "}, {", text)

        # 2. 确保字段名有引号
        text = re.sub(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', text)

        # 3. 移除多余的逗号
        text = re.sub(r",\s*}", "}", text)
        text = re.sub(r",\s*]", "]", text)

        return text

    def _extract_quotes_with_regex(
        self, result_text: str, sender_map: dict, max_quotes: int
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

            # 匹配金句对象的正则表达式模式
            quote_pattern = r'\{\s*"content":\s*"([^"]*(?:\\.[^"]*)*)"\s*,\s*"sender_name":\s*"([^"]+)"\s*,\s*"timestamp":\s*(\d+)\s*,\s*"reason":\s*"([^"]*(?:\\.[^"]*)*)"\s*\}'
            matches = re.findall(quote_pattern, result_text, re.DOTALL)

            if not matches:
                # 尝试更宽松的匹配
                quote_pattern = r'"content":\s*"([^"]*(?:\\.[^"]*)*)"\s*[^}]*"sender_name":\s*"([^"]+)"[^}]*"reason":\s*"([^"]*(?:\\.[^"]*)*)"'
                matches = re.findall(quote_pattern, result_text, re.DOTALL)

                for match in matches[:max_quotes]:
                    content = match[0].strip()
                    sender_name = match[1].strip()
                    reason = match[2].strip()

                    # 清理转义字符
                    content = (
                        content.replace('\\"', '"')
                        .replace("\\n", " ")
                        .replace("\\t", " ")
                    )
                    reason = (
                        reason.replace('\\"', '"')
                        .replace("\\n", " ")
                        .replace("\\t", " ")
                    )

                    # 获取发送者信息
                    sender_info = sender_map.get(sender_name, {})
                    sender_avatar = sender_info.get("avatar", "")
                    timestamp = sender_info.get("timestamp", 0)

                    quotes.append(
                        Quote(
                            content=content,
                            sender_name=sender_name,
                            sender_avatar=sender_avatar,
                            timestamp=timestamp,
                            reason=reason,
                        )
                    )
            else:
                for match in matches[:max_quotes]:
                    content = match[0].strip()
                    sender_name = match[1].strip()
                    timestamp = int(match[2])
                    reason = match[3].strip()

                    # 清理转义字符
                    content = (
                        content.replace('\\"', '"')
                        .replace("\\n", " ")
                        .replace("\\t", " ")
                    )
                    reason = (
                        reason.replace('\\"', '"')
                        .replace("\\n", " ")
                        .replace("\\t", " ")
                    )

                    # 获取发送者头像
                    sender_info = sender_map.get(sender_name, {})
                    sender_avatar = sender_info.get("avatar", "")

                    quotes.append(
                        Quote(
                            content=content,
                            sender_name=sender_name,
                            sender_avatar=sender_avatar,
                            timestamp=timestamp,
                            reason=reason,
                        )
                    )

            return quotes
        except Exception as e:
            logger.error(f"正则表达式提取失败: {e}")
            return []
