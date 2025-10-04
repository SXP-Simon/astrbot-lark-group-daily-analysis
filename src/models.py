"""
飞书群聊日报分析插件的核心数据模型

本模块定义了插件中使用的所有数据结构，
包括消息解析、用户信息、分析结果和统计数据。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from datetime import datetime


@dataclass
class ParsedMessage:
    """
    解析飞书 SDK 消息对象后的统一消息格式

    Attributes:
        message_id: 唯一消息标识符
        timestamp: Unix 时间戳（秒）
        sender_id: 发送者的 open_id
        sender_name: 发送者的真实昵称
        sender_avatar: 发送者的头像 URL
        content: 解析后的文本内容
        message_type: 消息类型（text、post、system 等）
        raw_content: 原始内容（用于调试）
    """

    message_id: str
    timestamp: int
    sender_id: str
    sender_name: str
    sender_avatar: str
    content: str
    message_type: str
    raw_content: str


@dataclass
class UserInfo:
    """
    从飞书 API 获取的用户信息

    Attributes:
        open_id: 用户的唯一 open_id
        name: 显示名称
        avatar_url: 头像图片 URL
        en_name: 英文名称（可选）
    """

    open_id: str
    name: str
    avatar_url: str
    en_name: str = ""


@dataclass
class Topic:
    """
    从消息中提取的讨论话题

    Attributes:
        title: 话题标题
        participants: 参与者名称列表
        description: 话题的详细描述
        message_count: 此话题中的消息数量
    """

    title: str
    participants: List[str]
    description: str
    message_count: int


@dataclass
class UserMetrics:
    """
    用户活动指标

    Attributes:
        message_count: 消息总数
        char_count: 字符总数
        avg_message_length: 平均消息长度
        emoji_count: 表情总数
        reply_count: 回复数量
        hourly_distribution: 按小时分布的消息数（0-23）
        sender_name: 用户显示名称（内部使用）
        sender_avatar: 用户头像 URL（内部使用）
    """

    message_count: int
    char_count: int
    avg_message_length: float
    emoji_count: int
    reply_count: int
    hourly_distribution: Dict[int, int] = field(default_factory=dict)
    sender_name: str = ""
    sender_avatar: str = ""


@dataclass
class UserTitle:
    """
    LLM 分析分配的用户活动称号

    Attributes:
        open_id: 用户的 open_id
        name: 用户显示名称
        avatar_url: 用户头像 URL
        title: 分配的称号
        mbti: MBTI 人格类型
        reason: 分配此称号的原因
        metrics: 用户活动指标
    """

    open_id: str
    name: str
    avatar_url: str
    title: str
    mbti: str
    reason: str
    metrics: UserMetrics


@dataclass
class Quote:
    """
    从消息中提取的金句

    Attributes:
        content: 金句内容
        sender_name: 发言人姓名
        sender_avatar: 发送者头像 URL
        timestamp: 发言时间（Unix 时间戳）
        reason: 选择此金句的原因
    """

    content: str
    sender_name: str
    sender_avatar: str
    timestamp: int
    reason: str


@dataclass
class EmojiStats:
    """
    表情使用统计

    Attributes:
        total_count: 使用的表情总数
        unique_count: 唯一表情数量
        top_emojis: 表情到数量的字典
        emoji_per_user: 每个用户的表情数量
    """

    total_count: int = 0
    unique_count: int = 0
    top_emojis: Dict[str, int] = field(default_factory=dict)
    emoji_per_user: Dict[str, int] = field(default_factory=dict)


@dataclass
class Statistics:
    """
    群组统计数据

    Attributes:
        message_count: 消息总数
        char_count: 字符总数
        participant_count: 唯一参与者数量
        hourly_distribution: 按小时分布的消息数（0-23）
        peak_hours: 前 3 个活跃高峰时段
        emoji_stats: 表情使用统计
    """

    message_count: int
    char_count: int
    participant_count: int
    hourly_distribution: Dict[int, int]
    peak_hours: List[int]
    emoji_stats: EmojiStats = field(default_factory=EmojiStats)


@dataclass
class TokenUsage:
    """
    LLM token 使用量跟踪

    Attributes:
        prompt_tokens: 提示词中的 token 数量
        completion_tokens: 完成内容中的 token 数量
        total_tokens: 使用的总 token 数量
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: "TokenUsage") -> "TokenUsage":
        """将另一个 TokenUsage 添加到当前对象"""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass
class AnalysisResult:
    """
    完整的分析结果

    Attributes:
        topics: 讨论话题列表
        user_titles: 用户称号列表
        quotes: 金句列表
        statistics: 群组统计数据
        token_usage: 总 token 使用量
        analysis_period: 分析时间段（开始时间，结束时间）
    """

    topics: List[Topic]
    user_titles: List[UserTitle]
    quotes: List[Quote]
    statistics: Statistics
    token_usage: TokenUsage
    analysis_period: Tuple[datetime, datetime]
