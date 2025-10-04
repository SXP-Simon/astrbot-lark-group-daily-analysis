"""
飞书客户端管理器

本模块提供对飞书SDK客户端的统一访问接口
从AstrBot上下文中提取飞书适配器，并提供访问SDK客户端和机器人信息的方法
"""

from astrbot.api.star import Context
from astrbot.api import logger


class LarkClientManager:
    """
    飞书客户端管理器

    提供对飞书SDK客户端的统一访问接口。从AstrBot平台管理器中提取飞书适配器，
    并处理不同的属性名称（lark_api、client或直接实例）

    Attributes:
        _context: AstrBot上下文对象
        _client: 飞书SDK客户端实例
        _lark_adapter: 飞书平台适配器实例
        _initialized: 是否已初始化
    """

    def __init__(self, context: Context):
        """
        初始化飞书客户端管理器

        Args:
            context: 包含平台管理器的AstrBot上下文对象
        """
        self._context = context
        self._client = None
        self._lark_adapter = None
        self._initialized = False

        # 延迟初始化 - 平台可能尚未加载
        # 将在首次使用时初始化

    def _initialize_client(self):
        """
        从平台管理器中提取飞书SDK客户端
        """
        try:
            # 在平台管理器中查找飞书适配器
            platforms = self._context.platform_manager.get_insts()
            logger.debug(f"找到 {len(platforms)} 个平台实例")

            # 通过类名查找飞书适配器
            for platform in platforms:
                if type(platform).__name__ == "LarkPlatformAdapter":
                    self._lark_adapter = platform
                    logger.info("找到飞书适配器")
                    break

            if not self._lark_adapter:
                logger.warning("未找到飞书适配器，插件将被禁用")
                logger.info("提示：请确保在AstrBot配置中启用了飞书平台适配器")
                self._client = None
                return

            # 使用各种可能的属性名提取客户端
            if hasattr(self._lark_adapter, "lark_api"):
                self._client = self._lark_adapter.lark_api
            elif hasattr(self._lark_adapter, "client"):
                self._client = self._lark_adapter.client
            elif hasattr(self._lark_adapter, "im") and hasattr(
                self._lark_adapter, "v1"
            ):
                self._client = self._lark_adapter
            else:
                raise RuntimeError("无法从适配器中提取飞书SDK客户端")

            if not self._client:
                raise RuntimeError("飞书SDK客户端为空")

            logger.info("飞书客户端管理器初始化成功")
            self._initialized = True

        except Exception as e:
            logger.error(f"初始化飞书客户端管理器失败: {e}")
            self._client = None
            self._initialized = True
            logger.warning("飞书客户端管理器初始化失败，插件功能将被禁用")

    def is_available(self) -> bool:
        """
        检查飞书客户端是否可用

        Returns:
            bool: 如果客户端可用返回True，否则返回False
        """
        if not self._initialized:
            self._initialize_client()
        return self._client is not None

    def get_client(self):
        """
        获取飞书SDK客户端实例

        Returns:
            飞书SDK客户端实例

        Raises:
            RuntimeError: 如果客户端不可用
        """
        if not self._initialized:
            self._initialize_client()

        if not self._client:
            error_msg = "飞书SDK客户端不可用，请确保飞书平台适配器配置正确"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        return self._client
