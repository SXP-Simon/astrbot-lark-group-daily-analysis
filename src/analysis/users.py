"""
用户分析模块
分析用户活动模式并使用LLM分配称号
"""

import json
import re
from datetime import datetime
from typing import List, Tuple, Dict
from collections import defaultdict
from astrbot.api import logger
from ..models import ParsedMessage, UserTitle, UserMetrics, TokenUsage
from ..utils.llm_helper import LLMHelper


class UsersAnalyzer:
    """分析用户活动并分配称号"""

    def __init__(self, context, config_manager):
        """
        初始化用户分析器

        Args:
            context: AstrBot上下文，用于访问LLM提供者
            config_manager: 配置管理器实例
        """
        self.context = context
        self.config_manager = config_manager
        self.llm_helper = LLMHelper(context, config_manager)

    async def analyze(
        self, messages: List[ParsedMessage], umo: str = None
    ) -> Tuple[List[UserTitle], TokenUsage]:
        """
        分析用户活动并分配称号

        Args:
            messages: 解析后的消息列表
            umo: LLM选择的唯一模型对象标识符

        Returns:
            元组：(UserTitle对象列表, TokenUsage)
        """
        try:
            # 验证输入
            if not messages:
                logger.warning("用户分析未提供消息数据")
                return [], TokenUsage()

            if not isinstance(messages, list):
                logger.error(f"消息类型无效：期望列表，得到 {type(messages)}")
                return [], TokenUsage()

            # 计算每个用户的指标
            user_metrics = self._calculate_user_metrics(messages)
            if not user_metrics:
                logger.info("未计算出用户指标")
                return [], TokenUsage()

            # 过滤低活跃用户（少于5条消息）
            active_users = {
                user_id: metrics
                for user_id, metrics in user_metrics.items()
                if metrics.message_count >= 5
            }

            if not active_users:
                logger.info("未找到活跃用户（至少需要5条消息）")
                return [], TokenUsage()

            # 按消息数量排序并取前N个用户
            max_user_titles = self.config_manager.get_max_user_titles()
            sorted_users = sorted(
                active_users.items(), key=lambda x: x[1].message_count, reverse=True
            )[:max_user_titles]

            # 调用LLM分配称号
            user_titles, token_usage = await self._assign_titles_with_llm(
                sorted_users, messages, umo
            )
            logger.info(f"用户分析完成：分配了 {len(user_titles)} 个称号")
            return user_titles, token_usage

        except Exception as e:
            logger.error(f"用户分析发生意外错误: {e}", exc_info=True)
            return [], TokenUsage()

    def _calculate_user_metrics(
        self, messages: List[ParsedMessage]
    ) -> Dict[str, UserMetrics]:
        """
        从解析的消息中计算每个用户的指标

        Args:
            messages: 解析后的消息列表

        Returns:
            用户open_id到UserMetrics的映射字典
        """
        user_data = defaultdict(
            lambda: {
                "message_count": 0,
                "char_count": 0,
                "emoji_count": 0,
                "reply_count": 0,
                "hourly_distribution": defaultdict(int),
                "sender_name": "",
                "sender_avatar": "",
            }
        )

        for msg in messages:
            try:
                user_id = msg.sender_id
                data = user_data[user_id]

                # 更新基础计数
                data["message_count"] += 1
                data["char_count"] += len(msg.content)

                # 存储用户信息（同一用户的所有消息都相同）
                data["sender_name"] = msg.sender_name
                data["sender_avatar"] = msg.sender_avatar

                # 统计表情数量
                emoji_count = self._count_emojis(msg.content)
                data["emoji_count"] += emoji_count

                # 跟踪小时分布
                hour = datetime.fromtimestamp(msg.timestamp).hour
                data["hourly_distribution"][hour] += 1

                # 统计回复数量（简单启发式方法）
                if "@" in msg.content or msg.message_type == "reply":
                    data["reply_count"] += 1

            except AttributeError as e:
                logger.warning(f"指标计算中的消息对象无效: {e}")
                continue
            except Exception as e:
                logger.error(f"处理指标计算中的消息时出错: {e}")
                continue

        # 转换为UserMetrics对象
        user_metrics = {}
        for user_id, data in user_data.items():
            avg_length = (
                data["char_count"] / data["message_count"]
                if data["message_count"] > 0
                else 0.0
            )

            user_metrics[user_id] = UserMetrics(
                message_count=data["message_count"],
                char_count=data["char_count"],
                avg_message_length=round(avg_length, 1),
                emoji_count=data["emoji_count"],
                reply_count=data["reply_count"],
                hourly_distribution=dict(data["hourly_distribution"]),
            )

            # 存储姓名和头像供后续使用
            user_metrics[user_id].sender_name = data["sender_name"]
            user_metrics[user_id].sender_avatar = data["sender_avatar"]

        return user_metrics

    def _count_emojis(self, text: str) -> int:
        """
        统计文本中的表情符号数量

        Args:
            text: 要分析的文本

        Returns:
            找到的表情符号数量
        """
        # 使用Unicode范围进行简单的表情符号检测
        emoji_pattern = re.compile(
            "["
            "\U0001f600-\U0001f64f"  # 表情符号
            "\U0001f300-\U0001f5ff"  # 符号和象形文字
            "\U0001f680-\U0001f6ff"  # 交通和地图符号
            "\U0001f1e0-\U0001f1ff"  # 旗帜
            "\U00002702-\U000027b0"
            "\U000024c2-\U0001f251"
            "]+",
            flags=re.UNICODE,
        )
        return len(emoji_pattern.findall(text))

    async def _assign_titles_with_llm(
        self,
        sorted_users: List[Tuple[str, UserMetrics]],
        messages: List[ParsedMessage],
        umo: str = None,
    ) -> Tuple[List[UserTitle], TokenUsage]:
        """
        使用LLM为用户分配称号

        Args:
            sorted_users: (用户ID, UserMetrics)元组列表
            messages: 原始消息列表，用于上下文
            umo: 唯一模型对象标识符

        Returns:
            元组：(UserTitle对象列表, TokenUsage)
        """
        # 准备包含实际用户名的用户摘要
        user_summaries = []
        user_info_map = {}  # 将user_id映射到(name, avatar)

        for user_id, metrics in sorted_users:
            # 计算活动比例
            night_messages = sum(
                metrics.hourly_distribution.get(h, 0) for h in range(0, 6)
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

            # 存储用户信息供后续使用
            user_info_map[user_id] = (metrics.sender_name, metrics.sender_avatar)

            # 调试：记录用户信息映射
            logger.debug(
                f"添加到user_info_map: {user_id[:12]}... -> name={metrics.sender_name}, has_avatar={bool(metrics.sender_avatar)}"
            )

            user_summaries.append(
                {
                    "name": metrics.sender_name,
                    "user_id": user_id,
                    "message_count": metrics.message_count,
                    "avg_chars": metrics.avg_message_length,
                    "emoji_ratio": round(emoji_ratio, 2),
                    "night_ratio": round(night_ratio, 2),
                    "reply_ratio": round(reply_ratio, 2),
                }
            )

        # 构建包含user_id的LLM提示词
        users_text = "\n".join(
            [
                f"- {user['name']} (ID: {user['user_id']}): "
                f"发言{user['message_count']}条, 平均{user['avg_chars']}字, "
                f"表情比例{user['emoji_ratio']}, 夜间发言比例{user['night_ratio']}, "
                f"回复比例{user['reply_ratio']}"
                for user in user_summaries
            ]
        )

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

        # 调用LLM
        response = await self.llm_helper.call_llm_with_retry(
            prompt, max_tokens=1500, temperature=0.5, umo=umo
        )

        if response is None:
            logger.error("用户称号分析LLM调用失败")
            return [], TokenUsage()

        # 提取token使用量
        token_usage = self.llm_helper.extract_token_usage(response)

        # 解析响应
        result_text = self.llm_helper.extract_response_text(response)
        logger.debug(f"用户称号分析原始响应: {result_text[:500]}...")

        # 尝试解析JSON
        try:
            json_match = re.search(r"\[.*?\]", result_text, re.DOTALL)
            if json_match:
                json_text = json_match.group()
                logger.debug(f"用户称号分析JSON: {json_text[:300]}...")

                titles_data = json.loads(json_text)
                user_titles = []

                for title_data in titles_data:
                    user_id = title_data.get("user_id", "")
                    name, avatar = user_info_map.get(
                        user_id, (title_data.get("name", ""), "")
                    )

                    # 调试：记录用户信息映射
                    logger.debug(
                        f"用户 {user_id[:12]}... -> 名称={name}, 有头像={bool(avatar)}"
                    )
                    if user_id not in user_info_map:
                        logger.warning(
                            f"用户 {user_id[:12]}... 未在 user_info_map 中找到。可用用户: {list(user_info_map.keys())[:3]}"
                        )

                    # 获取此用户的指标
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
                            hourly_distribution={},
                        )

                    user_titles.append(
                        UserTitle(
                            open_id=user_id,
                            name=name,
                            avatar_url=avatar,
                            title=title_data.get("title", ""),
                            mbti=title_data.get("mbti", ""),
                            reason=title_data.get("reason", ""),
                            metrics=metrics,
                        )
                    )

                logger.info(
                    f"用户称号分析成功，解析了 {len(user_titles)} 个称号"
                )
                return user_titles, token_usage

        except json.JSONDecodeError as e:
            logger.error(f"用户称号分析JSON解析失败: {e}")
            logger.debug(f"原始响应: {result_text}")

        return [], token_usage
