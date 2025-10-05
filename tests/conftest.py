"""
Pytest 配置和测试固件
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def mock_lark_context():
    """创建带有飞书适配器的模拟 AstrBot 上下文"""
    from unittest.mock import Mock
    
    mock_context = Mock()
    mock_adapter = Mock()
    mock_adapter.name = "lark"
    mock_adapter.bot_open_id = "ou_bot_test_123"
    mock_client = Mock()
    mock_adapter.client = mock_client
    mock_context.platforms = [mock_adapter]
    
    return mock_context


@pytest.fixture
def sample_user_info():
    """创建测试用的示例用户信息"""
    from src.models import UserInfo
    
    return UserInfo(
        open_id="ou_test_user_123",
        name="Test User",
        avatar_url="https://example.com/avatar.jpg",
        en_name="testuser"
    )


@pytest.fixture
def sample_parsed_messages():
    """创建测试用的示例解析消息"""
    from src.models import ParsedMessage
    from datetime import datetime
    
    return [
        ParsedMessage(
            message_id="msg_1",
            timestamp=int(datetime.now().timestamp()),
            sender_id="ou_user_1",
            sender_name="Alice",
            sender_avatar="https://example.com/alice.jpg",
            content="Hello everyone!",
            message_type="text",
            raw_content='{"text": "Hello everyone!"}'
        ),
        ParsedMessage(
            message_id="msg_2",
            timestamp=int(datetime.now().timestamp()) + 60,
            sender_id="ou_user_2",
            sender_name="Bob",
            sender_avatar="https://example.com/bob.jpg",
            content="Hi Alice! How are you?",
            message_type="text",
            raw_content='{"text": "Hi Alice! How are you?"}'
        ),
        ParsedMessage(
            message_id="msg_3",
            timestamp=int(datetime.now().timestamp()) + 120,
            sender_id="ou_user_1",
            sender_name="Alice",
            sender_avatar="https://example.com/alice.jpg",
            content="I'm doing great, thanks!",
            message_type="text",
            raw_content='{"text": "I\'m doing great, thanks!"}'
        ),
    ]
