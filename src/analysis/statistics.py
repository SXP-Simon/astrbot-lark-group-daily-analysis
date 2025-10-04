"""
统计分析模块
负责计算群组消息的统计数据
"""

from datetime import datetime
from typing import List, Dict
from collections import defaultdict, Counter
import re

from ..models import ParsedMessage, Statistics, EmojiStats


class StatisticsCalculator:
    """统计计算器 - 从解析后的消息计算各种统计指标"""

    def calculate(self, messages: List[ParsedMessage]) -> Statistics:
        """
        从解析后的消息列表计算统计数据

        Args:
            messages: 已解析的消息列表

        Returns:
            包含所有统计指标的Statistics对象
        """
        from astrbot.api import logger

        if not messages:
            logger.info("未提供消息数据，返回空统计")
            return self._empty_statistics()

        if not isinstance(messages, list):
            logger.error(f"消息数据类型错误: 期望list，实际{type(messages)}")
            return self._empty_statistics()

        # 基础统计
        message_count = len(messages)
        char_count = sum(
            len(msg.content)
            for msg in messages
            if hasattr(msg, "content") and msg.content
        )

        # 统计唯一参与者
        unique_participants = {
            msg.sender_id for msg in messages if hasattr(msg, "sender_id")
        }
        participant_count = len(unique_participants)

        # 计算小时分布和峰值时段
        hourly_distribution = self._calculate_hourly_distribution(messages)
        peak_hours = self._identify_peak_hours(hourly_distribution)

        # 计算表情统计
        emoji_stats = self._calculate_emoji_stats(messages)

        logger.info(
            f"统计计算完成: {message_count}条消息, {participant_count}位参与者, {char_count}个字符"
        )

        return Statistics(
            message_count=message_count,
            char_count=char_count,
            participant_count=participant_count,
            hourly_distribution=hourly_distribution,
            peak_hours=peak_hours,
            emoji_stats=emoji_stats,
        )

    def _empty_statistics(self) -> Statistics:
        """返回空的统计数据"""
        return Statistics(
            message_count=0,
            char_count=0,
            participant_count=0,
            hourly_distribution={},
            peak_hours=[],
            emoji_stats=EmojiStats(),
        )

    def _calculate_hourly_distribution(
        self, messages: List[ParsedMessage]
    ) -> Dict[int, int]:
        """
        计算24小时消息分布

        Args:
            messages: 消息列表

        Returns:
            字典，键为小时(0-23)，值为消息数量
        """
        hourly_dist = defaultdict(int)

        for msg in messages:
            try:
                msg_time = datetime.fromtimestamp(msg.timestamp)
                hourly_dist[msg_time.hour] += 1
            except (ValueError, OSError, AttributeError):
                continue

        return dict(hourly_dist)

    def _identify_peak_hours(self, hourly_distribution: Dict[int, int]) -> List[int]:
        """
        识别前3个最活跃的小时

        Args:
            hourly_distribution: 小时分布字典

        Returns:
            前3个最活跃小时的列表，按活跃度降序排列
        """
        if not hourly_distribution:
            return []

        # 按消息数量排序
        sorted_hours = sorted(
            hourly_distribution.items(), key=lambda x: x[1], reverse=True
        )

        # 返回前3个小时
        peak_hours = [hour for hour, count in sorted_hours[:3]]
        return peak_hours

    def _calculate_emoji_stats(self, messages: List[ParsedMessage]) -> EmojiStats:
        """
        计算表情符号使用统计

        Args:
            messages: 消息列表

        Returns:
            包含表情统计信息的EmojiStats对象
        """
        all_emojis = []
        emoji_per_user = defaultdict(int)

        # 表情符号正则表达式
        emoji_pattern = re.compile(
            "["
            "\U0001f600-\U0001f64f"  # 表情符号
            "\U0001f300-\U0001f5ff"  # 符号和象形文字
            "\U0001f680-\U0001f6ff"  # 交通和地图符号
            "\U0001f1e0-\U0001f1ff"  # 旗帜
            "\U00002702-\U000027b0"  # 装饰符号
            "\U000024c2-\U0001f251"  # 封闭字符
            "\U0001f900-\U0001f9ff"  # 补充符号和象形文字
            "\U0001fa00-\U0001fa6f"  # 扩展-A
            "\U0001fa70-\U0001faff"  # 符号和象形文字扩展-A
            "\U00002600-\U000026ff"  # 杂项符号
            "\U00002700-\U000027bf"  # 装饰符号
            "]+",
            flags=re.UNICODE,
        )

        for msg in messages:
            emojis = emoji_pattern.findall(msg.content)
            if emojis:
                all_emojis.extend(emojis)
                emoji_per_user[msg.sender_id] += len(emojis)

        emoji_counter = Counter(all_emojis)

        return EmojiStats(
            total_count=len(all_emojis),
            unique_count=len(emoji_counter),
            top_emojis=emoji_counter.most_common(10),
            emoji_per_user=dict(emoji_per_user),
        )
