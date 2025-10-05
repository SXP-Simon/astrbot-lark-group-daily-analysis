"""
话题分析模块

负责使用LLM从解析后的消息中分析讨论话题
本模块提取并总结群聊中讨论的主要话题
"""

import json
import re
from typing import List, Tuple
from astrbot.api import logger
from ..models import ParsedMessage, Topic, TokenUsage
from ..utils.llm_helper import LLMHelper


class TopicsAnalyzer:
    """
    话题分析器

    使用LLM从解析后的消息中分析讨论话题
    分析器会格式化消息（包含真实用户名和时间戳），然后使用LLM提取有意义的话题及详细描述
    """

    def __init__(self, context, config_manager):
        """
        初始化话题分析器

        Args:
            context: AstrBot上下文，用于访问LLM提供者
            config_manager: 配置管理器
        """
        self.context = context
        self.config_manager = config_manager
        self.llm_helper = LLMHelper(context, config_manager)

    async def analyze(
        self, messages: List[ParsedMessage], umo: str = None
    ) -> Tuple[List[Topic], TokenUsage]:
        """
        从解析后的消息中分析话题

        Args:
            messages: ParsedMessage 对象列表，包含真实用户信息
            umo: LLM 选择的唯一模型对象标识符

        Returns:
            元组：(Topic 对象列表, TokenUsage)
        """
        if not messages:
            logger.warning("未提供消息数据进行话题分析")
            return [], TokenUsage()

        if not isinstance(messages, list):
            logger.error(f"消息数据类型错误: 期望list，实际{type(messages)}")
            return [], TokenUsage()

        # 过滤有意义的文本消息
        text_messages = [
            msg
            for msg in messages
            if hasattr(msg, "content")
            and msg.content
            and len(msg.content.strip()) > 2
            and not msg.content.startswith("/")
        ]

        if not text_messages:
            logger.info("过滤后无可分析的文本消息")
            return [], TokenUsage()

        # 格式化消息并构建提示词
        messages_text = self._format_messages_for_llm(text_messages)
        max_topics = self.config_manager.get_max_topics()
        prompt = self._build_topics_prompt(messages_text, max_topics)

        # 调用LLM进行分析
        response = await self.llm_helper.call_llm_with_retry(
            prompt, max_tokens=10000, temperature=0.6, umo=umo
        )
        if response is None:
            logger.error("话题分析LLM调用失败，请检查LLM配置和网络连接")
            return [], TokenUsage()

        # 提取token使用量和响应文本
        token_usage = self.llm_helper.extract_token_usage(response)
        result_text = self.llm_helper.extract_response_text(response)

        # 解析响应并创建话题对象
        topics = self._parse_topics_response(result_text, max_topics)
        if not topics:
            # 返回默认话题作为后备
            logger.info("使用默认话题作为解析失败的后备")
            topics = [
                Topic(
                    title="群组讨论",
                    participants=["群成员"],
                    description="今日群聊涵盖了多个话题，由于分析错误无法提取详细话题信息",
                    message_count=len(text_messages),
                )
            ]

        logger.info(f"话题分析完成: 提取了{len(topics)}个话题")
        return topics, token_usage

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

    def _parse_topics_response(self, result_text: str, max_topics: int) -> List[Topic]:
        """
        解析LLM响应并提取话题

        Args:
            result_text: 原始LLM响应文本
            max_topics: 返回的最大话题数量

        Returns:
            Topic对象列表
        """
        try:
            # 尝试提取JSON
            json_match = re.search(r"\[.*?\]", result_text, re.DOTALL)
            if json_match:
                json_text = json_match.group()
                logger.debug(f"话题分析JSON原始数据: {json_text[:500]}...")

                # 修复并清理JSON
                json_text = self._fix_json(json_text)
                logger.debug(f"修复后的JSON: {json_text[:300]}...")

                topics_data = json.loads(json_text)
                topics = []
                for topic_dict in topics_data[:max_topics]:
                    # 将旧字段名映射到新的Topic模型
                    topic = Topic(
                        title=topic_dict.get("topic", ""),
                        participants=topic_dict.get("contributors", []),
                        description=topic_dict.get("detail", ""),
                        message_count=0,  # 如果需要，稍后计算
                    )
                    topics.append(topic)

                logger.info(f"成功解析 {len(topics)} 个话题")
                return topics
            else:
                logger.warning(
                    f"响应中未找到JSON格式: {result_text[:200]}..."
                )
        except json.JSONDecodeError as e:
            logger.error(f"话题分析JSON解析失败: {e}")
            logger.debug(
                f"修复后的JSON: {json_text if 'json_text' in locals() else 'N/A'}"
            )
            logger.debug(f"Raw response: {result_text}")

            # 降级方案：尝试正则表达式提取
            topics = self._extract_topics_with_regex(result_text, max_topics)
            if topics:
                logger.info(f"正则表达式提取成功: {len(topics)} 个话题")
                return topics
            else:
                # 最终降级方案
                logger.info("正则表达式提取失败，使用默认话题")
                return [
                    Topic(
                        title="群组讨论",
                        participants=["群成员"],
                        description="今日群聊涵盖了多个话题，由于分析错误无法提取详细话题信息",
                        message_count=0,
                    )
                ]

        return []

    def _fix_json(self, text: str) -> str:
        """
        修复常见的JSON格式问题

        Args:
            text: 原始JSON文本

        Returns:
            修复后的JSON文本
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

    def _extract_topics_with_regex(
        self, result_text: str, max_topics: int
    ) -> List[Topic]:
        """
        使用正则表达式提取话题（降级方案）

        Args:
            result_text: 原始LLM响应文本
            max_topics: 要提取的最大话题数量

        Returns:
            Topic对象列表
        """
        try:
            topics = []

            # 匹配话题对象的正则表达式模式
            topic_pattern = r'\{\s*"topic":\s*"([^"]+)"\s*,\s*"contributors":\s*\[([^\]]+)\]\s*,\s*"detail":\s*"([^"]*(?:\\.[^"]*)*)"\s*\}'
            matches = re.findall(topic_pattern, result_text, re.DOTALL)

            if not matches:
                # 尝试更宽松的匹配
                topic_pattern = r'"topic":\s*"([^"]+)"[^}]*"contributors":\s*\[([^\]]+)\][^}]*"detail":\s*"([^"]*(?:\\.[^"]*)*)"'
                matches = re.findall(topic_pattern, result_text, re.DOTALL)

            for match in matches[:max_topics]:
                topic_name = match[0].strip()
                contributors_str = match[1].strip()
                detail = match[2].strip()

                # 清理detail中的转义字符
                detail = (
                    detail.replace('\\"', '"').replace("\\n", " ").replace("\\t", " ")
                )

                # 解析参与者列表
                contributors = []
                for contrib in re.findall(r'"([^"]+)"', contributors_str):
                    contributors.append(contrib.strip())

                if not contributors:
                    contributors = ["群成员"]

                topics.append(
                    Topic(
                        title=topic_name,
                        participants=contributors[:5],  # 最多5个参与者
                        description=detail,
                        message_count=0,
                    )
                )

            return topics
        except Exception as e:
            logger.error(f"Regex extraction failed: {e}")
            return []
