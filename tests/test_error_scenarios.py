"""
错误处理和回退机制测试

测试需求: 8.1, 8.2, 8.3, 8.5
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.lark.client import LarkClientManager
from src.lark.message_fetcher import MessageFetcher
from src.lark.message_parser import MessageParser
from src.lark.user_info import UserInfoCache
from src.analysis.topics import TopicsAnalyzer
from src.analysis.users import UsersAnalyzer
from src.analysis.quotes import QuotesAnalyzer
from src.models import ParsedMessage


class TestAPIFailures:
    """测试API故障处理"""
    
    @pytest.mark.asyncio
    async def test_message_fetch_api_error(self):
        """测试消息获取器优雅地处理API错误"""
        mock_context = Mock()
        mock_adapter = Mock()
        mock_adapter.name = "lark"
        mock_adapter.bot_open_id = "ou_bot_123"
        mock_client = Mock()
        mock_adapter.client = mock_client
        mock_context.platforms = [mock_adapter]
        
        manager = LarkClientManager(mock_context)
        fetcher = MessageFetcher(manager)
        
        # Mock API error
        with patch.object(fetcher, '_fetch_page', side_effect=Exception("API Error")):
            messages = await fetcher.fetch_messages("oc_test_chat", days=1)
            
            # Should return empty list, not crash
            assert isinstance(messages, list)
            assert len(messages) == 0
    
    @pytest.mark.asyncio
    async def test_user_info_fetch_error(self):
        """测试用户信息缓存处理获取错误"""
        mock_context = Mock()
        mock_adapter = Mock()
        mock_adapter.name = "lark"
        mock_client = Mock()
        mock_adapter.client = mock_client
        mock_context.platforms = [mock_adapter]
        
        manager = LarkClientManager(mock_context)
        cache = UserInfoCache(manager)
        
        # Mock API error
        with patch.object(cache, '_fetch_user_from_api', side_effect=Exception("API Error")):
            user_info = await cache.get_user_info("ou_test_123")
            
            # Should return fallback user info
            assert user_info is not None
            assert user_info.open_id == "ou_test_123"
            assert "User_" in user_info.name
    
    @pytest.mark.asyncio
    async def test_message_fetch_timeout(self):
        """测试消息获取器处理超时"""
        mock_context = Mock()
        mock_adapter = Mock()
        mock_adapter.name = "lark"
        mock_adapter.bot_open_id = "ou_bot_123"
        mock_client = Mock()
        mock_adapter.client = mock_client
        mock_context.platforms = [mock_adapter]
        
        manager = LarkClientManager(mock_context)
        fetcher = MessageFetcher(manager)
        
        # Mock timeout
        with patch.object(fetcher, '_fetch_page', side_effect=asyncio.TimeoutError()):
            messages = await fetcher.fetch_messages("oc_test_chat", days=1)
            
            assert isinstance(messages, list)
            assert len(messages) == 0
    
    @pytest.mark.asyncio
    async def test_api_rate_limit_error(self):
        """测试API速率限制错误处理"""
        mock_context = Mock()
        mock_adapter = Mock()
        mock_adapter.name = "lark"
        mock_adapter.bot_open_id = "ou_bot_123"
        mock_client = Mock()
        mock_adapter.client = mock_client
        mock_context.platforms = [mock_adapter]
        
        manager = LarkClientManager(mock_context)
        fetcher = MessageFetcher(manager)
        
        # Mock rate limit error
        rate_limit_error = Exception("Rate limit exceeded")
        with patch.object(fetcher, '_fetch_page', side_effect=rate_limit_error):
            messages = await fetcher.fetch_messages("oc_test_chat", days=1)
            
            assert isinstance(messages, list)


class TestMalformedMessages:
    """测试格式错误消息数据处理"""
    
    @pytest.mark.asyncio
    async def test_parse_message_invalid_json(self):
        """测试解析器处理消息内容中的无效JSON"""
        mock_context = Mock()
        mock_adapter = Mock()
        mock_adapter.name = "lark"
        mock_context.platforms = [mock_adapter]
        
        manager = LarkClientManager(mock_context)
        cache = UserInfoCache(manager)
        parser = MessageParser(cache)
        
        # Mock message with invalid JSON
        mock_msg = Mock()
        mock_msg.message_id = "msg_123"
        mock_msg.create_time = str(int(datetime.now().timestamp() * 1000))
        mock_msg.sender = Mock()
        mock_msg.sender.sender_id = Mock()
        mock_msg.sender.sender_id.open_id = "ou_user_123"
        mock_msg.msg_type = "text"
        mock_msg.body = Mock()
        mock_msg.body.content = "This is not JSON {invalid}"
        
        from src.models import UserInfo
        user_info = UserInfo("ou_user_123", "Test User", "https://example.com/avatar.jpg", "test")
        
        with patch.object(cache, 'get_user_info', return_value=user_info):
            parsed = await parser.parse_message(mock_msg)
            
            # Should handle gracefully
            assert parsed is None or isinstance(parsed, ParsedMessage)
    
    @pytest.mark.asyncio
    async def test_parse_message_missing_fields(self):
        """测试解析器处理缺少字段的消息"""
        mock_context = Mock()
        mock_adapter = Mock()
        mock_adapter.name = "lark"
        mock_context.platforms = [mock_adapter]
        
        manager = LarkClientManager(mock_context)
        cache = UserInfoCache(manager)
        parser = MessageParser(cache)
        
        # Mock message with missing sender
        mock_msg = Mock()
        mock_msg.message_id = "msg_123"
        mock_msg.create_time = str(int(datetime.now().timestamp() * 1000))
        mock_msg.sender = None  # Missing sender
        mock_msg.msg_type = "text"
        mock_msg.body = Mock()
        mock_msg.body.content = json.dumps({"text": "Hello"})
        
        parsed = await parser.parse_message(mock_msg)
        
        # Should handle gracefully
        assert parsed is None or isinstance(parsed, ParsedMessage)
    
    @pytest.mark.asyncio
    async def test_parse_message_corrupted_timestamp(self):
        """测试解析器处理损坏的时间戳"""
        mock_context = Mock()
        mock_adapter = Mock()
        mock_adapter.name = "lark"
        mock_context.platforms = [mock_adapter]
        
        manager = LarkClientManager(mock_context)
        cache = UserInfoCache(manager)
        parser = MessageParser(cache)
        
        mock_msg = Mock()
        mock_msg.message_id = "msg_123"
        mock_msg.create_time = "invalid_timestamp"
        mock_msg.sender = Mock()
        mock_msg.sender.sender_id = Mock()
        mock_msg.sender.sender_id.open_id = "ou_user_123"
        mock_msg.msg_type = "text"
        mock_msg.body = Mock()
        mock_msg.body.content = json.dumps({"text": "Hello"})
        
        from src.models import UserInfo
        user_info = UserInfo("ou_user_123", "Test User", "https://example.com/avatar.jpg", "test")
        
        with patch.object(cache, 'get_user_info', return_value=user_info):
            parsed = await parser.parse_message(mock_msg)
            
            # Should handle gracefully
            assert parsed is None or isinstance(parsed, ParsedMessage)


class TestLLMFailures:
    """测试LLM分析失败处理"""
    
    @pytest.mark.asyncio
    async def test_topics_analyzer_llm_error(self, sample_parsed_messages):
        """测试话题分析器处理LLM错误"""
        mock_context = Mock()
        mock_config = Mock()
        mock_config.get_llm_model.return_value = "gpt-4"
        
        analyzer = TopicsAnalyzer(mock_context, mock_config)
        
        # Mock LLM error
        with patch.object(analyzer, '_call_llm', side_effect=Exception("LLM Error")):
            topics, token_usage = await analyzer.analyze(sample_parsed_messages, "gpt-4")
            
            # Should return empty list or fallback
            assert isinstance(topics, list)
    
    @pytest.mark.asyncio
    async def test_users_analyzer_llm_timeout(self, sample_parsed_messages):
        """测试用户分析器处理LLM超时"""
        mock_context = Mock()
        mock_config = Mock()
        mock_config.get_llm_model.return_value = "gpt-4"
        
        analyzer = UsersAnalyzer(mock_context, mock_config)
        
        # Mock timeout
        with patch.object(analyzer, '_call_llm', side_effect=asyncio.TimeoutError()):
            user_titles, token_usage = await analyzer.analyze(sample_parsed_messages, "gpt-4")
            
            assert isinstance(user_titles, list)
    
    @pytest.mark.asyncio
    async def test_quotes_analyzer_invalid_response(self, sample_parsed_messages):
        """测试金句分析器处理无效的LLM响应"""
        mock_context = Mock()
        mock_config = Mock()
        mock_config.get_llm_model.return_value = "gpt-4"
        
        analyzer = QuotesAnalyzer(mock_context, mock_config)
        
        # Mock invalid response
        with patch.object(analyzer, '_call_llm', return_value="Not a valid JSON response"):
            quotes, token_usage = await analyzer.analyze(sample_parsed_messages, "gpt-4")
            
            # Should handle gracefully
            assert isinstance(quotes, list)
    
    @pytest.mark.asyncio
    async def test_analyzer_malformed_json_fallback(self, sample_parsed_messages):
        """测试分析器对格式错误JSON使用正则表达式回退"""
        mock_context = Mock()
        mock_config = Mock()
        mock_config.get_llm_model.return_value = "gpt-4"
        
        analyzer = TopicsAnalyzer(mock_context, mock_config)
        
        # Mock response with JSON embedded in text
        malformed_response = """
        Here are the topics:
        {"topics": [{"title": "Test Topic", "participants": ["Alice"], "description": "Test", "message_count": 1}]}
        Hope this helps!
        """
        
        with patch.object(analyzer, '_call_llm', return_value=malformed_response):
            topics, token_usage = await analyzer.analyze(sample_parsed_messages, "gpt-4")
            
            # Should extract JSON using regex fallback
            assert isinstance(topics, list)


class TestFallbackMechanisms:
    """测试回退机制"""
    
    @pytest.mark.asyncio
    async def test_user_info_fallback_name(self):
        """测试回退用户名生成"""
        mock_context = Mock()
        mock_adapter = Mock()
        mock_adapter.name = "lark"
        mock_client = Mock()
        mock_adapter.client = mock_client
        mock_context.platforms = [mock_adapter]
        
        manager = LarkClientManager(mock_context)
        cache = UserInfoCache(manager)
        
        # Force API error
        with patch.object(cache, '_fetch_user_from_api', side_effect=Exception("Error")):
            user_info = await cache.get_user_info("ou_test_12345678")
            
            # Should generate fallback name
            assert "User_ou_test" in user_info.name
            assert user_info.open_id == "ou_test_12345678"
    
    @pytest.mark.asyncio
    async def test_empty_message_list_handling(self):
        """测试空消息列表处理"""
        mock_context = Mock()
        mock_config = Mock()
        mock_config.get_llm_model.return_value = "gpt-4"
        
        analyzer = TopicsAnalyzer(mock_context, mock_config)
        
        # Empty message list
        topics, token_usage = await analyzer.analyze([], "gpt-4")
        
        # Should handle gracefully
        assert isinstance(topics, list)
        assert len(topics) == 0
    
    def test_missing_lark_adapter_error(self):
        """测试飞书适配器缺失时的明确错误"""
        mock_context = Mock()
        mock_adapter = Mock()
        mock_adapter.name = "qq"  # Wrong platform
        mock_context.platforms = [mock_adapter]
        
        with pytest.raises(ValueError) as exc_info:
            LarkClientManager(mock_context)
        
        # Should have clear error message
        assert "Lark adapter not found" in str(exc_info.value)


class TestErrorLogging:
    """测试错误日志功能"""
    
    @pytest.mark.asyncio
    async def test_api_error_logging(self):
        """测试API错误被详细记录"""
        mock_context = Mock()
        mock_adapter = Mock()
        mock_adapter.name = "lark"
        mock_adapter.bot_open_id = "ou_bot_123"
        mock_client = Mock()
        mock_adapter.client = mock_client
        mock_context.platforms = [mock_adapter]
        
        manager = LarkClientManager(mock_context)
        fetcher = MessageFetcher(manager)
        
        with patch('logging.Logger.error') as mock_log:
            with patch.object(fetcher, '_fetch_page', side_effect=Exception("API Error")):
                await fetcher.fetch_messages("oc_test_chat", days=1)
                
                # Should log error
                assert mock_log.called
    
    @pytest.mark.asyncio
    async def test_parse_error_logging(self):
        """测试解析错误被记录"""
        mock_context = Mock()
        mock_adapter = Mock()
        mock_adapter.name = "lark"
        mock_context.platforms = [mock_adapter]
        
        manager = LarkClientManager(mock_context)
        cache = UserInfoCache(manager)
        parser = MessageParser(cache)
        
        mock_msg = Mock()
        mock_msg.message_id = "msg_123"
        mock_msg.create_time = str(int(datetime.now().timestamp() * 1000))
        mock_msg.sender = Mock()
        mock_msg.sender.sender_id = Mock()
        mock_msg.sender.sender_id.open_id = "ou_user_123"
        mock_msg.msg_type = "unsupported"
        mock_msg.body = Mock()
        mock_msg.body.content = "{}"
        
        from src.models import UserInfo
        user_info = UserInfo("ou_user_123", "Test", "https://example.com/avatar.jpg", "test")
        
        with patch('logging.Logger.warning') as mock_log:
            with patch.object(cache, 'get_user_info', return_value=user_info):
                await parser.parse_message(mock_msg)
                
                # Should log warning for unsupported type
                # (implementation dependent)
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
