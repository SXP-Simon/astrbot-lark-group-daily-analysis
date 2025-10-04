"""
Core data models for the Lark group daily analysis plugin.

This module defines all the data structures used throughout the plugin,
including message parsing, user information, analysis results, and statistics.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime


@dataclass
class ParsedMessage:
    """
    Unified message format after parsing Lark SDK message objects.
    
    Attributes:
        message_id: Unique message identifier
        timestamp: Unix timestamp in seconds
        sender_id: Sender's open_id
        sender_name: Actual nickname of the sender
        sender_avatar: Avatar URL of the sender
        content: Parsed text content
        message_type: Type of message (text, post, system, etc.)
        raw_content: Original content for debugging
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
    User information fetched from Lark API.
    
    Attributes:
        open_id: User's unique open_id
        name: Display name
        avatar_url: Avatar image URL
        en_name: English name (optional)
    """
    open_id: str
    name: str
    avatar_url: str
    en_name: str = ""


@dataclass
class Topic:
    """
    Discussion topic extracted from messages.
    
    Attributes:
        title: Topic title
        participants: List of participant names
        description: Detailed description of the topic
        message_count: Number of messages in this topic
    """
    title: str
    participants: List[str]
    description: str
    message_count: int


@dataclass
class UserMetrics:
    """
    User activity metrics.
    
    Attributes:
        message_count: Total number of messages
        char_count: Total character count
        avg_message_length: Average message length
        emoji_count: Total emoji count
        reply_count: Number of replies
        hourly_distribution: Message distribution by hour (0-23)
        sender_name: User's display name (for internal use)
        sender_avatar: User's avatar URL (for internal use)
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
    User activity title assigned by LLM analysis.
    
    Attributes:
        open_id: User's open_id
        name: User's display name
        avatar_url: User's avatar URL
        title: Assigned title
        mbti: MBTI personality type
        reason: Reason for the title assignment
        metrics: User activity metrics
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
    Golden quote extracted from messages.
    
    Attributes:
        content: Quote content
        sender_name: Name of the person who said it
        sender_avatar: Avatar URL of the sender
        timestamp: When the quote was said (Unix timestamp)
        reason: Why this quote was selected
    """
    content: str
    sender_name: str
    sender_avatar: str
    timestamp: int
    reason: str


@dataclass
class EmojiStats:
    """
    Emoji usage statistics.
    
    Attributes:
        total_count: Total number of emojis used
        unique_count: Number of unique emojis
        top_emojis: Dictionary of emoji to count
        emoji_per_user: Emoji count per user
    """
    total_count: int = 0
    unique_count: int = 0
    top_emojis: Dict[str, int] = field(default_factory=dict)
    emoji_per_user: Dict[str, int] = field(default_factory=dict)


@dataclass
class Statistics:
    """
    Group statistics.
    
    Attributes:
        message_count: Total message count
        char_count: Total character count
        participant_count: Number of unique participants
        hourly_distribution: Message distribution by hour (0-23)
        peak_hours: Top 3 peak activity hours
        emoji_stats: Emoji usage statistics
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
    LLM token usage tracking.
    
    Attributes:
        prompt_tokens: Number of tokens in the prompt
        completion_tokens: Number of tokens in the completion
        total_tokens: Total tokens used
    """
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    def add(self, other: 'TokenUsage') -> 'TokenUsage':
        """Add another TokenUsage to this one."""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens
        )


@dataclass
class AnalysisResult:
    """
    Complete analysis result.
    
    Attributes:
        topics: List of discussion topics
        user_titles: List of user titles
        quotes: List of golden quotes
        statistics: Group statistics
        token_usage: Total token usage
        analysis_period: Tuple of (start_time, end_time)
    """
    topics: List[Topic]
    user_titles: List[UserTitle]
    quotes: List[Quote]
    statistics: Statistics
    token_usage: TokenUsage
    analysis_period: Tuple[datetime, datetime]
