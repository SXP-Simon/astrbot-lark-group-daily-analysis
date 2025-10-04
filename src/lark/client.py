"""
飞书客户端管理器

本模块提供对飞书 SDK 客户端的统一访问接口。
从 AstrBot 上下文中提取飞书适配器，并提供访问 SDK 客户端和机器人信息的方法。
"""

from typing import Optional
from astrbot.api.star import Context
from astrbot.api import logger


class LarkClientManager:
    """
    飞书客户端管理器
    
    提供对飞书 SDK 客户端的统一访问接口。从 AstrBot 平台管理器中提取飞书适配器，
    并处理不同的属性名称（lark_api、client 或直接实例）。
    
    Attributes:
        _context: AstrBot 上下文对象
        _client: 飞书 SDK 客户端实例
        _lark_adapter: 飞书平台适配器实例
        _initialized: 是否已初始化
    """
    
    def __init__(self, context: Context):
        """
        初始化飞书客户端管理器
        
        Args:
            context: 包含平台管理器的 AstrBot 上下文对象
        """
        self._context = context
        self._client = None
        self._lark_adapter = None
        self._initialized = False
        
        # Don't initialize immediately - platforms may not be loaded yet
        # Will initialize on first use (lazy initialization)
    
    def _initialize_client(self):
        """
        从平台管理器中提取飞书 SDK 客户端
        
        遍历所有平台实例以查找飞书适配器，然后使用各种可能的属性名称提取 SDK 客户端。
        如果找不到飞书适配器，将设置客户端为 None 并禁用插件功能。
        
        Raises:
            RuntimeError: 如果无法提取飞书 SDK 客户端
        """
        try:
            # Find Lark adapter in platform manager
            platforms = self._context.platform_manager.get_insts()
            logger.debug(f"Found {len(platforms)} platform instances")
            
            # Try to find Lark adapter by checking class name instead of isinstance
            # This avoids import issues with the lark module name conflict
            for platform in platforms:
                platform_class_name = type(platform).__name__
                platform_module = type(platform).__module__
                logger.debug(f"Checking platform: {platform_class_name} from {platform_module}")
                
                # Check if this is a Lark adapter by class name
                if platform_class_name == "LarkPlatformAdapter":
                    self._lark_adapter = platform
                    logger.info(f"Found Lark adapter: {platform_class_name}")
                    break
            
            if not self._lark_adapter:
                available_platforms = [(type(p).__name__, type(p).__module__) for p in platforms]
                logger.warning("Lark adapter not found in platform manager. Plugin will be disabled.")
                logger.info(f"Available platforms: {available_platforms}")
                logger.info("提示：请确保在 AstrBot 配置中启用了 Lark 平台适配器")
                # Don't raise error, just set client to None
                self._client = None
                return
            
            # Extract client using various possible attribute names
            if hasattr(self._lark_adapter, "lark_api"):
                self._client = self._lark_adapter.lark_api
                logger.debug("Lark client extracted from 'lark_api' attribute")
            elif hasattr(self._lark_adapter, "client"):
                self._client = self._lark_adapter.client
                logger.debug("Lark client extracted from 'client' attribute")
            elif hasattr(self._lark_adapter, "im") and hasattr(self._lark_adapter, "v1"):
                # Direct SDK instance
                self._client = self._lark_adapter
                logger.debug("Using Lark adapter as direct SDK instance")
            else:
                raise RuntimeError("Could not extract Lark SDK client from adapter")
            
            if not self._client:
                raise RuntimeError("Lark SDK client is None")
            
            logger.info("Lark client manager initialized successfully")
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize Lark client manager: {e}")
            # Don't raise error, just log it and set client to None
            self._client = None
            self._initialized = True  # Mark as initialized to avoid retrying
            logger.warning("Lark client manager initialization failed. Plugin features will be disabled.")
    
    def is_available(self) -> bool:
        """
        检查飞书客户端是否可用
        
        Returns:
            bool: 如果客户端可用返回 True，否则返回 False
        """
        # Try to initialize if not already done
        if not self._initialized:
            self._initialize_client()
        return self._client is not None
    
    def get_client(self):
        """
        获取飞书 SDK 客户端实例
        
        Returns:
            飞书 SDK 客户端（lark.Client 或兼容实例）
            
        Raises:
            RuntimeError: 如果客户端不可用
        """
        try:
            # Try to initialize if not already done
            if not self._initialized:
                self._initialize_client()
            
            if not self._client:
                error_msg = "Lark SDK client is not available. Please ensure the Lark platform adapter is properly configured."
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            return self._client
        except Exception as e:
            logger.error(f"Error accessing Lark client: {e}", exc_info=True)
            raise
    

