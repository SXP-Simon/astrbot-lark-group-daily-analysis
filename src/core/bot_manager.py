"""
Bot实例管理模块
统一管理bot实例的获取、设置和使用
"""

from typing import Dict, Any

class BotManager:
    """飞书Bot实例管理器 - 统一管理所有bot相关操作"""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self._bot_instance = None
        self._bot_open_id = None
        self._context = None
        self._is_initialized = False
    
    def set_context(self, context):
        """设置AstrBot上下文"""
        self._context = context
    
    def set_bot_instance(self, bot_instance):
        """设置飞书bot实例"""
        if bot_instance:
            self._bot_instance = bot_instance
            # 自动提取Open ID
            if not self._bot_open_id:
                bot_open_id = self._extract_bot_open_id(bot_instance)
                if bot_open_id:
                    self._bot_open_id = str(bot_open_id)


    def set_bot_open_id(self, bot_open_id: str):
        """设置飞书bot Open ID"""
        if bot_open_id:
            self._bot_open_id = str(bot_open_id)

    
    def get_bot_instance(self):
        """获取当前bot实例"""
        return self._bot_instance
    
    def has_bot_instance(self) -> bool:
        """检查是否有可用的bot实例"""
        return self._bot_instance is not None
    
    def has_bot_open_id(self) -> bool:
        """检查是否有配置的飞书bot Open ID"""
        return self._bot_open_id is not None
    
    def is_ready_for_auto_analysis(self) -> bool:
        """检查是否准备好进行自动分析"""
        return self.has_bot_instance() and self.has_bot_open_id()
    
    async def auto_discover_bot_instance(self):
        """自动发现可用的bot实例"""
        if not self._context or not hasattr(self._context, 'platform_manager'):
            return None

        platforms = getattr(self._context.platform_manager, 'platform_insts', [])
        for platform in platforms:
            # 获取bot实例
            bot_client = None
            if hasattr(platform, 'get_client'):
                bot_client = platform.get_client()
            elif hasattr(platform, 'bot'):
                bot_client = platform.bot

            if bot_client:
                self.set_bot_instance(bot_client)
                return bot_client
        return None
    
    async def initialize_from_config(self):
        """从配置初始化飞书bot管理器"""
        # 设置配置的飞书bot Open ID
        bot_open_id = self.config_manager.get_bot_open_id()
        if bot_open_id:
            self.set_bot_open_id(bot_open_id)

        # 自动发现bot实例
        await self.auto_discover_bot_instance()
        self._is_initialized = True

        # 返回是否成功初始化（至少有bot实例）
        return self.has_bot_instance()
    
    def get_status_info(self) -> Dict[str, Any]:
        """获取飞书bot管理器状态信息"""
        return {
            "has_bot_instance": self.has_bot_instance(),
            "has_bot_open_id": self.has_bot_open_id(),
            "bot_open_id": self._bot_open_id,
            "ready_for_auto_analysis": self.is_ready_for_auto_analysis()
        }
    
    def update_from_event(self, event):
        """从飞书事件更新bot实例（用于手动命令）"""
        if hasattr(event, 'bot') and event.bot:
            self.set_bot_instance(event.bot)
            # 每次都尝试从bot实例提取Open ID
            bot_open_id = self._extract_bot_open_id(event.bot)
            if bot_open_id:
                self.set_bot_open_id(bot_open_id)
            else:
                # 如果bot实例没有Open ID，尝试使用配置的Open ID
                config_open_id = self.config_manager.get_bot_open_id()
                if config_open_id:
                    self.set_bot_open_id(config_open_id)
            return True
        return False

    def _extract_bot_open_id(self, bot_instance):
        """从飞书bot实例中提取Open ID"""
        # 尝试多种方式获取飞书bot Open ID
        if hasattr(bot_instance, 'self_id') and bot_instance.self_id:
            return str(bot_instance.self_id)
        elif hasattr(bot_instance, 'open_id') and bot_instance.open_id:
            return str(bot_instance.open_id)
        elif hasattr(bot_instance, 'bot_name') and bot_instance.bot_name:
            return str(bot_instance.bot_name)
        return None
    
    def validate_for_message_fetching(self, group_id: str) -> bool:
        """验证是否可以进行消息获取"""
        return self.has_bot_instance() and bool(group_id)
    
    def should_filter_bot_message(self, sender_id: str) -> bool:
        """判断是否应该过滤飞书bot自己的消息"""
        if not self._bot_open_id:
            return False
        return str(sender_id) == self._bot_open_id
