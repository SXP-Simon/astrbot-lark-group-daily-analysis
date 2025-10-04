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
    """统计计算器 - 从ParsedMessage计算各种统计指标"""

    def calculate(self, messages: List[ParsedMessage]) -> Statistics:
        """
        从ParsedMessage列表计算统计数据
        
        Args:
            messages: 已解析的消息列表
            
        Returns:
            Statistics对象包含所有统计指标
        """
        from astrbot.api import logger
        
        try:
            # Validate input
            if not messages:
                logger.info("No messages provided for statistics calculation")
                return Statistics(
                    message_count=0,
                    char_count=0,
                    participant_count=0,
                    hourly_distribution={},
                    peak_hours=[],
                    emoji_stats=EmojiStats()
                )
            
            if not isinstance(messages, list):
                logger.error(f"Invalid messages type: expected list, got {type(messages)}")
                return Statistics(
                    message_count=0,
                    char_count=0,
                    participant_count=0,
                    hourly_distribution={},
                    peak_hours=[],
                    emoji_stats=EmojiStats()
                )
            
            # 基础统计
            try:
                message_count = len(messages)
                char_count = 0
                for msg in messages:
                    try:
                        char_count += len(msg.content)
                    except (TypeError, AttributeError) as e:
                        logger.debug(f"Error counting characters for message: {e}")
                        continue
            except Exception as e:
                logger.error(f"Error calculating basic statistics: {e}", exc_info=True)
                message_count = 0
                char_count = 0
            
            # 统计唯一参与者
            try:
                unique_participants = set()
                for msg in messages:
                    try:
                        unique_participants.add(msg.sender_id)
                    except AttributeError as e:
                        logger.debug(f"Error accessing sender_id: {e}")
                        continue
                participant_count = len(unique_participants)
            except Exception as e:
                logger.error(f"Error calculating participant count: {e}", exc_info=True)
                participant_count = 0
            
            # 构建小时分布
            try:
                hourly_distribution = self._calculate_hourly_distribution(messages)
            except Exception as e:
                logger.error(f"Error calculating hourly distribution: {e}", exc_info=True)
                hourly_distribution = {}
            
            # 识别峰值小时（前3名）
            try:
                peak_hours = self._identify_peak_hours(hourly_distribution)
            except Exception as e:
                logger.error(f"Error identifying peak hours: {e}", exc_info=True)
                peak_hours = []
            
            # 计算emoji统计
            try:
                emoji_stats = self._calculate_emoji_stats(messages)
            except Exception as e:
                logger.error(f"Error calculating emoji statistics: {e}", exc_info=True)
                emoji_stats = EmojiStats()
            
            logger.info(
                f"Statistics calculated: {message_count} messages, "
                f"{participant_count} participants, {char_count} characters"
            )
            
            return Statistics(
                message_count=message_count,
                char_count=char_count,
                participant_count=participant_count,
                hourly_distribution=hourly_distribution,
                peak_hours=peak_hours,
                emoji_stats=emoji_stats
            )
            
        except Exception as e:
            logger.error(f"Unexpected error in statistics calculation: {e}", exc_info=True)
            return Statistics(
                message_count=0,
                char_count=0,
                participant_count=0,
                hourly_distribution={},
                peak_hours=[],
                emoji_stats=EmojiStats()
            )
    
    def _calculate_hourly_distribution(self, messages: List[ParsedMessage]) -> Dict[int, int]:
        """
        计算24小时消息分布
        
        Args:
            messages: 消息列表
            
        Returns:
            字典，键为小时(0-23)，值为消息数量
        """
        from astrbot.api import logger
        
        hourly_dist = defaultdict(int)
        
        for msg in messages:
            try:
                # 从Unix时间戳转换为datetime
                msg_time = datetime.fromtimestamp(msg.timestamp)
                hour = msg_time.hour
                hourly_dist[hour] += 1
            except (ValueError, OSError, AttributeError) as e:
                logger.debug(f"Error parsing timestamp for hourly distribution: {e}")
                continue
            except Exception as e:
                logger.warning(f"Unexpected error in hourly distribution calculation: {e}")
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
            hourly_distribution.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 返回前3个小时
        peak_hours = [hour for hour, count in sorted_hours[:3]]
        return peak_hours
    
    def _calculate_emoji_stats(self, messages: List[ParsedMessage]) -> EmojiStats:
        """
        计算emoji使用统计
        
        Args:
            messages: 消息列表
            
        Returns:
            EmojiStats对象包含emoji统计信息
        """
        all_emojis = []
        emoji_per_user = defaultdict(int)
        
        # Unicode emoji范围的正则表达式
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # 表情符号
            "\U0001F300-\U0001F5FF"  # 符号和象形文字
            "\U0001F680-\U0001F6FF"  # 交通和地图符号
            "\U0001F1E0-\U0001F1FF"  # 旗帜
            "\U00002702-\U000027B0"  # 装饰符号
            "\U000024C2-\U0001F251"  # 封闭字符
            "\U0001F900-\U0001F9FF"  # 补充符号和象形文字
            "\U0001FA00-\U0001FA6F"  # 扩展-A
            "\U0001FA70-\U0001FAFF"  # 符号和象形文字扩展-A
            "\U00002600-\U000026FF"  # 杂项符号
            "\U00002700-\U000027BF"  # 装饰符号
            "]+",
            flags=re.UNICODE
        )
        
        for msg in messages:
            # 从消息内容中提取emoji
            emojis = emoji_pattern.findall(msg.content)
            
            if emojis:
                all_emojis.extend(emojis)
                emoji_per_user[msg.sender_id] += len(emojis)
        
        # 统计emoji
        total_count = len(all_emojis)
        emoji_counter = Counter(all_emojis)
        unique_count = len(emoji_counter)
        
        # 获取前10个最常用的emoji
        top_emojis = emoji_counter.most_common(10)
        
        return EmojiStats(
            total_count=total_count,
            unique_count=unique_count,
            top_emojis=top_emojis,
            emoji_per_user=dict(emoji_per_user)
        )

