"""
分析准确性测试

测试需求: 4.2, 4.3, 4.4, 10.1, 10.2, 10.3, 10.4
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.analysis.topics import TopicsAnalyzer
from src.analysis.users import UsersAnalyzer
from src.analysis.quotes import QuotesAnalyzer
from src.analysis.statistics import StatisticsCalculator
from src.models import ParsedMessage, Topic, UserTitle, Quote, Statistics


class TestTopicsAnalyzer:
    """测试话题分析准确性"""
    
    @pytest.mark.asyncio
    async def test_topics_use_actual_names(self, sample_parsed_messages):
        """验证话题使用实际用户名"""
        mock_context = Mock()
        mock_config = Mock()
        mock_config.get_llm_model.return_value = "gpt-4"
        
        analyzer = TopicsAnalyzer(mock_context, mock_config)
        
        # Mock LLM response with actual names
        mock_llm_response = {
            "topics": [
                {
                    "title": "Greetings and Catch-up",
                    "participants": ["Alice", "Bob"],
                    "description": "Alice greeted everyone and Bob asked how she was doing. Alice responded positively.",
                    "message_count": 3
                }
            ]
        }
        
        with patch.object(analyzer, '_call_llm', return_value=json.dumps(mock_llm_response)):
            topics, token_usage = await analyzer.analyze(sample_parsed_messages, "gpt-4")
            
            assert len(topics) > 0
            assert "Alice" in topics[0].participants
            assert "Bob" in topics[0].participants
            assert "Alice" in topics[0].description or "Bob" in topics[0].description
    
    @pytest.mark.asyncio
    async def test_topics_are_detailed(self, sample_parsed_messages):
        """验证话题包含具体、详细的信息"""
        mock_context = Mock()
        mock_config = Mock()
        mock_config.get_llm_model.return_value = "gpt-4"
        
        analyzer = TopicsAnalyzer(mock_context, mock_config)
        
        mock_llm_response = {
            "topics": [
                {
                    "title": "Project Discussion",
                    "participants": ["Alice", "Bob"],
                    "description": "Alice proposed a new feature for the project. Bob agreed and suggested implementation details. They discussed timeline and decided to start next week.",
                    "message_count": 5
                }
            ]
        }
        
        with patch.object(analyzer, '_call_llm', return_value=json.dumps(mock_llm_response)):
            topics, token_usage = await analyzer.analyze(sample_parsed_messages, "gpt-4")
            
            assert len(topics) > 0
            # Description should be detailed (more than just a title)
            assert len(topics[0].description) > 50
            # Should mention specific actions or outcomes
            assert any(word in topics[0].description.lower() for word in ["proposed", "agreed", "discussed", "decided"])
    
    @pytest.mark.asyncio
    async def test_topics_handle_malformed_json(self, sample_parsed_messages):
        """验证话题分析器优雅地处理格式错误的JSON"""
        mock_context = Mock()
        mock_config = Mock()
        mock_config.get_llm_model.return_value = "gpt-4"
        
        analyzer = TopicsAnalyzer(mock_context, mock_config)
        
        # Malformed JSON response
        with patch.object(analyzer, '_call_llm', return_value="This is not JSON"):
            topics, token_usage = await analyzer.analyze(sample_parsed_messages, "gpt-4")
            
            # Should return empty list or fallback, not crash
            assert isinstance(topics, list)


class TestUsersAnalyzer:
    """测试用户分析准确性"""
    
    @pytest.mark.asyncio
    async def test_users_use_actual_names(self, sample_parsed_messages):
        """验证用户称号使用实际昵称"""
        mock_context = Mock()
        mock_config = Mock()
        mock_config.get_llm_model.return_value = "gpt-4"
        
        analyzer = UsersAnalyzer(mock_context, mock_config)
        
        mock_llm_response = {
            "user_titles": [
                {
                    "open_id": "ou_user_1",
                    "name": "Alice",
                    "avatar_url": "https://example.com/alice.jpg",
                    "title": "Conversation Starter",
                    "mbti": "ENFP",
                    "reason": "Alice initiated the conversation and kept it flowing"
                },
                {
                    "open_id": "ou_user_2",
                    "name": "Bob",
                    "avatar_url": "https://example.com/bob.jpg",
                    "title": "Friendly Responder",
                    "mbti": "ISFJ",
                    "reason": "Bob responded warmly to Alice's greeting"
                }
            ]
        }
        
        with patch.object(analyzer, '_call_llm', return_value=json.dumps(mock_llm_response)):
            user_titles, token_usage = await analyzer.analyze(sample_parsed_messages, "gpt-4")
            
            assert len(user_titles) > 0
            # Should use actual names, not IDs
            assert any(user.name == "Alice" for user in user_titles)
            assert any(user.name == "Bob" for user in user_titles)
            # Should not have truncated IDs
            assert not any("ou_user" in user.name for user in user_titles)
    
    @pytest.mark.asyncio
    async def test_users_metrics_accurate(self, sample_parsed_messages):
        """验证用户指标计算准确"""
        mock_context = Mock()
        mock_config = Mock()
        mock_config.get_llm_model.return_value = "gpt-4"
        
        analyzer = UsersAnalyzer(mock_context, mock_config)
        
        # Calculate metrics manually
        metrics = analyzer._calculate_user_metrics(sample_parsed_messages)
        
        # Alice sent 2 messages
        assert metrics["ou_user_1"]["message_count"] == 2
        # Bob sent 1 message
        assert metrics["ou_user_2"]["message_count"] == 1
        
        # Check character counts
        assert metrics["ou_user_1"]["char_count"] > 0
        assert metrics["ou_user_2"]["char_count"] > 0
        
        # Check average message length
        assert metrics["ou_user_1"]["avg_message_length"] > 0
    
    @pytest.mark.asyncio
    async def test_users_include_avatars(self, sample_parsed_messages):
        """验证用户称号包含头像URL"""
        mock_context = Mock()
        mock_config = Mock()
        mock_config.get_llm_model.return_value = "gpt-4"
        
        analyzer = UsersAnalyzer(mock_context, mock_config)
        
        mock_llm_response = {
            "user_titles": [
                {
                    "open_id": "ou_user_1",
                    "name": "Alice",
                    "avatar_url": "https://example.com/alice.jpg",
                    "title": "Active Participant",
                    "mbti": "ENFP",
                    "reason": "Very engaged in conversation"
                }
            ]
        }
        
        with patch.object(analyzer, '_call_llm', return_value=json.dumps(mock_llm_response)):
            user_titles, token_usage = await analyzer.analyze(sample_parsed_messages, "gpt-4")
            
            assert len(user_titles) > 0
            assert user_titles[0].avatar_url.startswith("https://")


class TestQuotesAnalyzer:
    """测试金句分析准确性"""
    
    @pytest.mark.asyncio
    async def test_quotes_properly_attributed(self, sample_parsed_messages):
        """验证金句正确归属到对应用户"""
        mock_context = Mock()
        mock_config = Mock()
        mock_config.get_llm_model.return_value = "gpt-4"
        
        analyzer = QuotesAnalyzer(mock_context, mock_config)
        
        mock_llm_response = {
            "quotes": [
                {
                    "content": "Hello everyone!",
                    "sender_name": "Alice",
                    "sender_avatar": "https://example.com/alice.jpg",
                    "timestamp": int(datetime.now().timestamp()),
                    "reason": "Warm greeting that started the conversation"
                }
            ]
        }
        
        with patch.object(analyzer, '_call_llm', return_value=json.dumps(mock_llm_response)):
            quotes, token_usage = await analyzer.analyze(sample_parsed_messages, "gpt-4")
            
            assert len(quotes) > 0
            assert quotes[0].sender_name == "Alice"
            assert quotes[0].content == "Hello everyone!"
    
    @pytest.mark.asyncio
    async def test_quotes_include_avatars(self, sample_parsed_messages):
        """验证金句包含发送者头像"""
        mock_context = Mock()
        mock_config = Mock()
        mock_config.get_llm_model.return_value = "gpt-4"
        
        analyzer = QuotesAnalyzer(mock_context, mock_config)
        
        mock_llm_response = {
            "quotes": [
                {
                    "content": "I'm doing great, thanks!",
                    "sender_name": "Alice",
                    "sender_avatar": "https://example.com/alice.jpg",
                    "timestamp": int(datetime.now().timestamp()),
                    "reason": "Positive and uplifting response"
                }
            ]
        }
        
        with patch.object(analyzer, '_call_llm', return_value=json.dumps(mock_llm_response)):
            quotes, token_usage = await analyzer.analyze(sample_parsed_messages, "gpt-4")
            
            assert len(quotes) > 0
            assert quotes[0].sender_avatar.startswith("https://")
    
    @pytest.mark.asyncio
    async def test_quotes_have_reasons(self, sample_parsed_messages):
        """验证金句包含选择原因"""
        mock_context = Mock()
        mock_config = Mock()
        mock_config.get_llm_model.return_value = "gpt-4"
        
        analyzer = QuotesAnalyzer(mock_context, mock_config)
        
        mock_llm_response = {
            "quotes": [
                {
                    "content": "Hello everyone!",
                    "sender_name": "Alice",
                    "sender_avatar": "https://example.com/alice.jpg",
                    "timestamp": int(datetime.now().timestamp()),
                    "reason": "Enthusiastic greeting that set a positive tone"
                }
            ]
        }
        
        with patch.object(analyzer, '_call_llm', return_value=json.dumps(mock_llm_response)):
            quotes, token_usage = await analyzer.analyze(sample_parsed_messages, "gpt-4")
            
            assert len(quotes) > 0
            assert len(quotes[0].reason) > 10  # Should have meaningful reason


class TestStatisticsCalculator:
    """测试统计数据计算准确性"""
    
    def test_statistics_message_count(self, sample_parsed_messages):
        """验证准确的消息计数"""
        calculator = StatisticsCalculator()
        stats = calculator.calculate(sample_parsed_messages)
        
        assert stats.message_count == len(sample_parsed_messages)
    
    def test_statistics_char_count(self, sample_parsed_messages):
        """验证准确的字符计数"""
        calculator = StatisticsCalculator()
        stats = calculator.calculate(sample_parsed_messages)
        
        expected_chars = sum(len(msg.content) for msg in sample_parsed_messages)
        assert stats.char_count == expected_chars
    
    def test_statistics_participant_count(self, sample_parsed_messages):
        """验证准确的参与者计数"""
        calculator = StatisticsCalculator()
        stats = calculator.calculate(sample_parsed_messages)
        
        unique_senders = len(set(msg.sender_id for msg in sample_parsed_messages))
        assert stats.participant_count == unique_senders
    
    def test_statistics_hourly_distribution(self, sample_parsed_messages):
        """验证小时分布计算正确"""
        calculator = StatisticsCalculator()
        stats = calculator.calculate(sample_parsed_messages)
        
        assert isinstance(stats.hourly_distribution, dict)
        # Should have entries for hours when messages were sent
        assert len(stats.hourly_distribution) > 0
        # All values should be positive
        assert all(count > 0 for count in stats.hourly_distribution.values())
    
    def test_statistics_peak_hours(self, sample_parsed_messages):
        """验证高峰时段识别正确"""
        calculator = StatisticsCalculator()
        stats = calculator.calculate(sample_parsed_messages)
        
        assert isinstance(stats.peak_hours, list)
        # Should have at least one peak hour
        assert len(stats.peak_hours) > 0
        # Peak hours should be valid (0-23)
        assert all(0 <= hour <= 23 for hour in stats.peak_hours)
    
    def test_statistics_empty_messages(self):
        """验证统计数据处理空消息列表"""
        calculator = StatisticsCalculator()
        stats = calculator.calculate([])
        
        assert stats.message_count == 0
        assert stats.char_count == 0
        assert stats.participant_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
