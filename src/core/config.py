"""
配置管理模块
负责处理插件配置和PDF依赖检查
"""

import sys
from typing import Optional, List
from astrbot.api import logger, AstrBotConfig


class ConfigManager:
    """配置管理器"""

    def __init__(self, config: AstrBotConfig):
        self.config = config
        self._pyppeteer_available = False
        self._pyppeteer_version = None
        self._check_pyppeteer_availability()

    def get_enabled_groups(self) -> List[str]:
        """获取启用的群组列表"""
        return self.config.get("enabled_groups", [])

    def get_max_messages(self) -> int:
        """获取最大消息数量"""
        max_msgs = self.config.get("max_messages", 1000)
        if not isinstance(max_msgs, int) or max_msgs <= 0:
            logger.warning(f"max_messages配置无效: {max_msgs}，使用默认值: 1000")
            return 1000
        return max_msgs

    def get_analysis_days(self) -> int:
        """获取分析天数"""
        days = self.config.get("analysis_days", 1)
        if not isinstance(days, int) or days < 1 or days > 7:
            logger.warning(f"analysis_days配置无效: {days}，使用默认值: 1")
            return 1
        return days

    def get_auto_analysis_time(self) -> str:
        """获取自动分析时间"""
        return self.config.get("auto_analysis_time", "09:00")

    def get_enable_auto_analysis(self) -> bool:
        """获取是否启用自动分析"""
        return self.config.get("enable_auto_analysis", False)

    def get_user_name_mapping(self) -> dict:
        """
        获取用户名称映射配置

        Returns:
            字典，key 为 open_id，value 为用户自定义名称
            例如: {"ou_xxx": "张三", "ou_yyy": "李四"}
        """
        mapping = self.config.get("user_name_mapping", {})
        if not isinstance(mapping, dict):
            logger.warning(
                f"用户名映射格式无效: {type(mapping)}，使用空字典"
            )
            return {}
        return mapping

    def get_output_format(self) -> str:
        """获取输出格式"""
        format_type = self.config.get("output_format", "image")
        valid_formats = ["image", "text", "pdf"]
        if format_type not in valid_formats:
            logger.warning(f"output_format配置无效: {format_type}，使用默认值: image")
            return "image"
        return format_type

    def get_min_messages_threshold(self) -> int:
        """获取最小消息阈值"""
        threshold = self.config.get("min_messages_threshold", 50)
        # 验证是否为正整数
        if not isinstance(threshold, int) or threshold <= 0:
            logger.warning(
                f"最小消息阈值配置无效: {threshold}，使用默认值: 50"
            )
            return 50
        return threshold

    def get_topic_analysis_enabled(self) -> bool:
        """获取是否启用话题分析"""
        return self.config.get("topic_analysis_enabled", True)

    def get_user_title_analysis_enabled(self) -> bool:
        """获取是否启用用户称号分析"""
        return self.config.get("user_title_analysis_enabled", True)

    def get_golden_quotes_analysis_enabled(self) -> bool:
        """获取是否启用金句分析"""
        return self.config.get("golden_quotes_analysis_enabled", True)

    def get_max_topics(self) -> int:
        """获取最大话题数量"""
        max_topics = self.config.get("max_topics", 5)
        # 验证是否为正整数
        if not isinstance(max_topics, int) or max_topics <= 0:
            logger.warning(f"最大话题数无效: {max_topics}，使用默认值: 5")
            return 5
        return max_topics

    def get_max_user_titles(self) -> int:
        """获取最大用户称号数量"""
        max_titles = self.config.get("max_user_titles", 8)
        # 验证是否为正整数
        if not isinstance(max_titles, int) or max_titles <= 0:
            logger.warning(
                f"最大用户称号数无效: {max_titles}，使用默认值: 8"
            )
            return 8
        return max_titles

    def get_max_golden_quotes(self) -> int:
        """获取最大金句数量"""
        max_quotes = self.config.get("max_golden_quotes", 5)
        # 验证是否为正整数
        if not isinstance(max_quotes, int) or max_quotes <= 0:
            logger.warning(
                f"最大金句数无效: {max_quotes}，使用默认值: 5"
            )
            return 5
        return max_quotes

    def get_max_query_rounds(self) -> int:
        """获取最大查询轮数"""
        max_rounds = self.config.get("max_query_rounds", 35)
        # 验证是否为正整数
        if not isinstance(max_rounds, int) or max_rounds <= 0:
            logger.warning(
                f"最大查询轮数无效: {max_rounds}，使用默认值: 35"
            )
            return 35
        return max_rounds

    def get_llm_timeout(self) -> int:
        """获取LLM请求超时时间（秒）"""
        timeout = self.config.get("llm_timeout", 30)
        # 验证是否为正整数
        if not isinstance(timeout, int) or timeout <= 0:
            logger.warning(f"LLM超时时间无效: {timeout}，使用默认值: 30")
            return 30
        return timeout

    def get_llm_retries(self) -> int:
        """获取LLM请求重试次数"""
        retries = self.config.get("llm_retries", 2)
        # 验证是否为非负整数
        if not isinstance(retries, int) or retries < 0:
            logger.warning(f"LLM重试次数无效: {retries}，使用默认值: 2")
            return 2
        return retries

    def get_llm_backoff(self) -> int:
        """获取LLM请求重试退避基值（秒），实际退避会乘以尝试次数"""
        backoff = self.config.get("llm_backoff", 2)
        # 验证是否为正整数
        if not isinstance(backoff, int) or backoff <= 0:
            logger.warning(f"LLM退避时间无效: {backoff}，使用默认值: 2")
            return 2
        return backoff

    def get_custom_api_key(self) -> str:
        """获取自定义 LLM 服务的 API Key"""
        return self.config.get("custom_api_key", "")

    def get_custom_api_base_url(self) -> str:
        """获取自定义 LLM 服务的 Base URL"""
        return self.config.get("custom_api_base_url", "")

    def get_custom_model_name(self) -> str:
        """获取自定义 LLM 服务的模型名称"""
        return self.config.get("custom_model_name", "")

    def get_pdf_output_dir(self) -> str:
        """获取PDF输出目录"""
        return self.config.get(
            "pdf_output_dir", "data/plugins/astrbot-qq-group-daily-analysis/reports"
        )

    def get_pdf_filename_format(self) -> str:
        """获取PDF文件名格式"""
        return self.config.get(
            "pdf_filename_format", "群聊分析报告_{group_id}_{date}.pdf"
        )

    def set_output_format(self, format_type: str):
        """设置输出格式"""
        # 验证格式类型
        valid_formats = ["image", "text", "pdf"]
        if format_type not in valid_formats:
            logger.error(
                f"输出格式值无效: {format_type}，必须是 {valid_formats} 之一"
            )
            raise ValueError(
                f"output_format 必须是 {valid_formats} 之一，当前值: {format_type}"
            )
        self.config["output_format"] = format_type
        self.config.save_config()

    def set_enabled_groups(self, groups: List[str]):
        """设置启用的群组列表"""
        self.config["enabled_groups"] = groups
        self.config.save_config()

    def set_max_messages(self, count: int):
        """设置最大消息数量"""
        # 验证是否为正整数
        if not isinstance(count, int) or count <= 0:
            logger.error(f"最大消息数值无效: {count}，必须是正整数")
            raise ValueError(f"max_messages 必须为正数，当前值: {count}")
        self.config["max_messages"] = count
        self.config.save_config()

    def set_analysis_days(self, days: int):
        """设置分析天数"""
        # 验证范围（1-7天）
        if not isinstance(days, int) or days < 1 or days > 7:
            logger.error(
                f"分析天数无效: {days}，必须在 1-7 之间"
            )
            raise ValueError(f"analysis_days 必须在 1-7 之间，当前值: {days}")
        self.config["analysis_days"] = days
        self.config.save_config()

    def set_auto_analysis_time(self, time_str: str):
        """设置自动分析时间"""
        self.config["auto_analysis_time"] = time_str
        self.config.save_config()

    def set_enable_auto_analysis(self, enabled: bool):
        """设置是否启用自动分析"""
        self.config["enable_auto_analysis"] = enabled
        self.config.save_config()

    def set_min_messages_threshold(self, threshold: int):
        """设置最小消息阈值"""
        # 验证是否为正整数
        if not isinstance(threshold, int) or threshold <= 0:
            logger.error(
                f"最小消息阈值无效: {threshold}，必须是正整数"
            )
            raise ValueError(
                f"min_messages_threshold 必须为正数，当前值: {threshold}"
            )
        self.config["min_messages_threshold"] = threshold
        self.config.save_config()

    def set_topic_analysis_enabled(self, enabled: bool):
        """设置是否启用话题分析"""
        self.config["topic_analysis_enabled"] = enabled
        self.config.save_config()

    def set_user_title_analysis_enabled(self, enabled: bool):
        """设置是否启用用户称号分析"""
        self.config["user_title_analysis_enabled"] = enabled
        self.config.save_config()

    def set_golden_quotes_analysis_enabled(self, enabled: bool):
        """设置是否启用金句分析"""
        self.config["golden_quotes_analysis_enabled"] = enabled
        self.config.save_config()

    def set_max_topics(self, count: int):
        """设置最大话题数量"""
        # 验证是否为正整数
        if not isinstance(count, int) or count <= 0:
            logger.error(f"最大话题数值无效: {count}，必须是正整数")
            raise ValueError(f"max_topics 必须为正数，当前值: {count}")
        self.config["max_topics"] = count
        self.config.save_config()

    def set_max_user_titles(self, count: int):
        """设置最大用户称号数量"""
        # 验证是否为正整数
        if not isinstance(count, int) or count <= 0:
            logger.error(f"最大用户称号数值无效: {count}，必须是正整数")
            raise ValueError(f"max_user_titles 必须为正数，当前值: {count}")
        self.config["max_user_titles"] = count
        self.config.save_config()

    def set_max_golden_quotes(self, count: int):
        """设置最大金句数量"""
        # 验证是否为正整数
        if not isinstance(count, int) or count <= 0:
            logger.error(f"最大金句数值无效: {count}，必须是正整数")
            raise ValueError(f"max_golden_quotes 必须为正数，当前值: {count}")
        self.config["max_golden_quotes"] = count
        self.config.save_config()

    def set_max_query_rounds(self, rounds: int):
        """设置最大查询轮数"""
        # 验证是否为正整数
        if not isinstance(rounds, int) or rounds <= 0:
            logger.error(f"最大查询轮数值无效: {rounds}，必须是正整数")
            raise ValueError(f"max_query_rounds 必须为正数，当前值: {rounds}")
        self.config["max_query_rounds"] = rounds
        self.config.save_config()

    def set_pdf_output_dir(self, directory: str):
        """设置PDF输出目录"""
        self.config["pdf_output_dir"] = directory
        self.config.save_config()

    def set_pdf_filename_format(self, format_str: str):
        """设置PDF文件名格式"""
        self.config["pdf_filename_format"] = format_str
        self.config.save_config()

    def add_enabled_group(self, group_id: str):
        """添加启用的群组"""
        enabled_groups = self.get_enabled_groups()
        if group_id not in enabled_groups:
            enabled_groups.append(group_id)
            self.config["enabled_groups"] = enabled_groups
            self.config.save_config()

    def remove_enabled_group(self, group_id: str):
        """移除启用的群组"""
        enabled_groups = self.get_enabled_groups()
        if group_id in enabled_groups:
            enabled_groups.remove(group_id)
            self.config["enabled_groups"] = enabled_groups
            self.config.save_config()

    @property
    def pyppeteer_available(self) -> bool:
        """检查pyppeteer是否可用"""
        return self._pyppeteer_available

    @property
    def pyppeteer_version(self) -> Optional[str]:
        """获取pyppeteer版本"""
        return self._pyppeteer_version

    def _check_pyppeteer_availability(self):
        """检查 pyppeteer 可用性"""
        try:
            import pyppeteer

            self._pyppeteer_available = True

            # 检查版本
            try:
                self._pyppeteer_version = pyppeteer.__version__
                logger.info(f"使用 pyppeteer {self._pyppeteer_version} 作为 PDF 引擎")
            except AttributeError:
                self._pyppeteer_version = "unknown"
                logger.info("使用 pyppeteer (版本未知) 作为 PDF 引擎")

        except ImportError:
            self._pyppeteer_available = False
            self._pyppeteer_version = None
            logger.warning(
                "pyppeteer 未安装，PDF 功能将不可用。请使用 /安装PDF 命令安装 pyppeteer==1.0.2"
            )

    def reload_pyppeteer(self) -> bool:
        """重新加载 pyppeteer 模块"""
        try:
            logger.info("开始重新加载 pyppeteer 模块...")

            # 移除所有 pyppeteer 相关模块
            modules_to_remove = [
                mod for mod in sys.modules.keys() if mod.startswith("pyppeteer")
            ]
            logger.info(f"移除模块: {modules_to_remove}")
            for mod in modules_to_remove:
                del sys.modules[mod]

            # 强制重新导入
            try:
                import pyppeteer

                # 更新全局变量
                self._pyppeteer_available = True
                try:
                    self._pyppeteer_version = pyppeteer.__version__
                    logger.info(
                        f"重新加载成功，pyppeteer 版本: {self._pyppeteer_version}"
                    )
                except AttributeError:
                    self._pyppeteer_version = "unknown"
                    logger.info("重新加载成功，pyppeteer 版本未知")

                return True

            except ImportError:
                logger.info("pyppeteer 重新导入需要重启 AstrBot 才能生效")
                logger.info(
                    "💡 提示：pyppeteer 安装成功，但需要重启 AstrBot 后才能使用 PDF 功能"
                )
                self._pyppeteer_available = False
                self._pyppeteer_version = None
                return False
            except Exception:
                logger.info("pyppeteer 重新导入需要重启 AstrBot 才能生效")
                logger.info(
                    "💡 提示：pyppeteer 安装成功，但需要重启 AstrBot 后才能使用 PDF 功能"
                )
                self._pyppeteer_available = False
                self._pyppeteer_version = None
                return False

        except Exception as e:
            logger.error(f"重新加载 pyppeteer 时出错: {e}")
            return False

    def save_config(self):
        """保存配置到AstrBot配置系统"""
        try:
            self.config.save_config()
            logger.info("配置已保存")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def reload_config(self):
        """重新加载配置"""
        try:
            # 重新从AstrBot配置系统读取所有配置
            logger.info("重新加载配置...")
            # 配置会自动从self.config中重新读取
            logger.info("配置重载完成")
        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")

    def validate_config(self) -> bool:
        """
        验证所有配置项的有效性

        Returns:
            bool: 如果所有配置有效返回True，否则返回False
        """
        is_valid = True

        # 验证分析天数(1-7)
        analysis_days = self.config.get("analysis_days", 1)
        if not isinstance(analysis_days, int) or analysis_days < 1 or analysis_days > 7:
            logger.error(
                f"配置验证失败: analysis_days 必须在 1-7 之间，当前值: {analysis_days}"
            )
            is_valid = False

        # 验证最大消息数>0
        max_messages = self.config.get("max_messages", 1000)
        if not isinstance(max_messages, int) or max_messages <= 0:
            logger.error(
                f"配置验证失败: max_messages 必须大于 0，当前值: {max_messages}"
            )
            is_valid = False

        # 验证输出格式选项
        output_format = self.config.get("output_format", "image")
        valid_formats = ["image", "text", "pdf"]
        if output_format not in valid_formats:
            logger.error(
                f"配置验证失败: output_format 必须是 {valid_formats} 之一，当前值: {output_format}"
            )
            is_valid = False

        # 验证最小消息阈值>0
        min_threshold = self.config.get("min_messages_threshold", 50)
        if not isinstance(min_threshold, int) or min_threshold <= 0:
            logger.error(
                f"配置验证失败: min_messages_threshold 必须大于 0，当前值: {min_threshold}"
            )
            is_valid = False

        # 验证最大话题数>0
        max_topics = self.config.get("max_topics", 5)
        if not isinstance(max_topics, int) or max_topics <= 0:
            logger.error(f"配置验证失败: max_topics 必须大于 0，当前值: {max_topics}")
            is_valid = False

        # 验证最大用户称号数>0
        max_titles = self.config.get("max_user_titles", 8)
        if not isinstance(max_titles, int) or max_titles <= 0:
            logger.error(
                f"配置验证失败: max_user_titles 必须大于 0，当前值: {max_titles}"
            )
            is_valid = False

        # 验证最大金句数>0
        max_quotes = self.config.get("max_golden_quotes", 5)
        if not isinstance(max_quotes, int) or max_quotes <= 0:
            logger.error(
                f"配置验证失败: max_golden_quotes 必须大于 0，当前值: {max_quotes}"
            )
            is_valid = False

        # 验证最大查询轮数>0
        max_rounds = self.config.get("max_query_rounds", 35)
        if not isinstance(max_rounds, int) or max_rounds <= 0:
            logger.error(
                f"配置验证失败: max_query_rounds 必须大于 0，当前值: {max_rounds}"
            )
            is_valid = False

        # 验证LLM超时时间>0
        llm_timeout = self.config.get("llm_timeout", 30)
        if not isinstance(llm_timeout, int) or llm_timeout <= 0:
            logger.error(f"配置验证失败: llm_timeout 必须大于 0，当前值: {llm_timeout}")
            is_valid = False

        # 验证LLM重试次数>=0
        llm_retries = self.config.get("llm_retries", 2)
        if not isinstance(llm_retries, int) or llm_retries < 0:
            logger.error(
                f"配置验证失败: llm_retries 必须大于等于 0，当前值: {llm_retries}"
            )
            is_valid = False

        # 验证LLM退避时间>0
        llm_backoff = self.config.get("llm_backoff", 2)
        if not isinstance(llm_backoff, int) or llm_backoff <= 0:
            logger.error(f"配置验证失败: llm_backoff 必须大于 0，当前值: {llm_backoff}")
            is_valid = False

        if is_valid:
            logger.info("配置验证通过")
        else:
            logger.warning("配置验证失败，某些配置项无效，将使用默认值")

        return is_valid
