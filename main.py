"""
飞书群日常分析插件
基于群聊记录生成精美的日常分析报告，包含话题总结、用户画像、统计数据等

重构版本 - 使用模块化架构，适配飞书平台
"""

import time
import asyncio
from typing import Optional
from pathlib import Path

from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.api import logger, AstrBotConfig
from astrbot.core.platform.sources.lark.lark_event import LarkMessageEvent
from astrbot.core.message.components import File
from astrbot.core.star.filter.permission import PermissionType

# 导入重构后的模块
from .src.core.config import ConfigManager
from .src.lark.client import LarkClientManager
from .src.lark.user_info import UserInfoCache
from .src.lark.message_fetcher import MessageFetcher
from .src.lark.message_parser import MessageParser
from .src.analysis.topics import TopicsAnalyzer
from .src.analysis.users import UsersAnalyzer
from .src.analysis.quotes import QuotesAnalyzer
from .src.analysis.statistics import StatisticsCalculator
from .src.reports.generators import ReportGenerator
from .src.scheduler.auto_scheduler import AutoScheduler
from .src.utils.pdf_utils import PDFInstaller


# 全局变量
config_manager = None
lark_client_manager = None
user_info_cache = None
message_fetcher = None
message_parser = None
topics_analyzer = None
users_analyzer = None
quotes_analyzer = None
statistics_calculator = None
report_generator = None
auto_scheduler = None


class LarkGroupDailyAnalysis(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 初始化模块化组件
        global config_manager, lark_client_manager, user_info_cache, message_fetcher, message_parser
        global topics_analyzer, users_analyzer, quotes_analyzer, statistics_calculator
        global report_generator, auto_scheduler

        try:
            # Initialize configuration
            config_manager = ConfigManager(config)
            
            # Initialize Lark client manager (lazy initialization - will connect on first use)
            lark_client_manager = LarkClientManager(context)
            logger.info("Lark client manager created (will initialize on first use)")
            
            # Initialize user info cache with config manager for user name mapping
            user_info_cache = UserInfoCache(lark_client_manager, ttl=3600, config_manager=config_manager)
            logger.info("User info cache initialized")
            
            # Initialize message fetcher and parser
            message_fetcher = MessageFetcher(lark_client_manager)
            message_parser = MessageParser(user_info_cache)
            logger.info("Message fetcher and parser initialized")
            
            # Initialize analyzers
            topics_analyzer = TopicsAnalyzer(context, config_manager)
            users_analyzer = UsersAnalyzer(context, config_manager)
            quotes_analyzer = QuotesAnalyzer(context, config_manager)
            statistics_calculator = StatisticsCalculator()
            logger.info("Analysis modules initialized")
            
            # Initialize report generator
            report_generator = ReportGenerator(config_manager)
            logger.info("Report generator initialized")
            
            # Initialize auto scheduler (if needed)
            # TODO: Update auto_scheduler to use new architecture
            # auto_scheduler = AutoScheduler(...)
            
            logger.info("飞书群日常分析插件已初始化（重构版本）")
            
        except Exception as e:
            logger.error(f"Failed to initialize plugin: {e}", exc_info=True)
            raise

    async def _delayed_start_scheduler(self):
        """延迟启动调度器，给系统时间初始化"""
        try:
            # 等待10秒让系统完全初始化
            await asyncio.sleep(10)

            # TODO: Update auto_scheduler to use new architecture
            # await auto_scheduler.start_scheduler()
            logger.info("Auto scheduler will be implemented in a future task")

        except Exception as e:
            logger.error(f"延迟启动调度器失败: {e}")




    async def _reload_config_and_restart_scheduler(self):
        """重新加载配置并重启调度器"""
        try:
            # 重新加载配置
            config_manager.reload_config()
            logger.info(f"重新加载配置: 自动分析={config_manager.get_enable_auto_analysis()}")

            # TODO: Update auto_scheduler to use new architecture
            # await auto_scheduler.restart_scheduler()
            logger.info("配置重载完成")

        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")

    @filter.command("历史消息示例")
    @filter.permission_type(PermissionType.ADMIN)
    async def show_history_example(self, event: LarkMessageEvent, days: int = 1):
        """
        获取并展示飞书群历史消息示例
        用法: /历史消息示例 [天数]
        """
        import time
        
        # Check if plugin is available
        if lark_client_manager is None or not lark_client_manager.is_available():
            yield event.plain_result("❌ 插件未启用：未找到 Lark 平台适配器。请先配置 Lark 平台。")
            return
        
        if not isinstance(event, LarkMessageEvent):
            yield event.plain_result("❌ 此功能仅支持飞书群聊")
            return
            
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return
        
        try:
            # Fetch messages using new architecture
            raw_messages = await message_fetcher.fetch_messages(
                chat_id=group_id,
                days=days,
                max_messages=20,
                container_id_type='chat'
            )
            
            if not raw_messages:
                yield event.plain_result("❌ 未获取到历史消息")
                return
            
            # Parse messages
            parsed_messages = []
            for msg in raw_messages[:5]:
                parsed_msg = await message_parser.parse_message(msg)
                if parsed_msg:
                    parsed_messages.append(parsed_msg)
            
            if not parsed_messages:
                yield event.plain_result("❌ 无法解析历史消息")
                return
            
            # Format preview
            preview = []
            for msg in parsed_messages:
                tstr = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(msg.timestamp))
                preview.append(
                    f"[{tstr}] {msg.sender_name} ({msg.message_type}): "
                    f"{msg.content[:100]}{'...' if len(msg.content) > 100 else ''}"
                )
            
            yield event.plain_result("\n".join(preview))
            
        except Exception as e:
            logger.error(f"历史消息获取失败: {e}", exc_info=True)
            yield event.plain_result(f"❌ 历史消息获取失败: {e}")

    @filter.command("群分析")
    @filter.permission_type(PermissionType.ADMIN)
    async def analyze_group_daily(self, event: LarkMessageEvent, days: Optional[int] = None):
        """
        分析群聊日常活动
        用法: /群分析 [天数]
        """
        # Check if plugin is available
        if lark_client_manager is None or not lark_client_manager.is_available():
            yield event.plain_result("❌ 插件未启用：未找到 Lark 平台适配器。请先配置 Lark 平台。")
            return
        
        if not isinstance(event, LarkMessageEvent):
            yield event.plain_result("❌ 此功能仅支持飞书群聊")
            return

        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        # 检查群组权限
        enabled_groups = config_manager.get_enabled_groups()
        if enabled_groups and group_id not in enabled_groups:
            yield event.plain_result("❌ 此群未启用日常分析功能")
            return

        # 设置分析天数
        analysis_days = days if days and 1 <= days <= 30 else config_manager.get_analysis_days()

        yield event.plain_result(f"🔍 开始分析群聊近{analysis_days}天的活动，请稍候...")

        logger.info(f"当前输出格式配置: {config_manager.get_output_format()}")

        try:
            # Step 1: Fetch raw messages using new message fetcher
            raw_messages = await message_fetcher.fetch_messages(
                chat_id=group_id,
                days=analysis_days,
                max_messages=config_manager.get_max_messages(),
                container_id_type='chat'
            )
            
            if not raw_messages:
                yield event.plain_result("❌ 未找到足够的群聊记录，请确保群内有足够的消息历史")
                return

            # Step 2: Parse messages into unified format
            parsed_messages = []
            for msg in raw_messages:
                parsed_msg = await message_parser.parse_message(msg)
                if parsed_msg:
                    parsed_messages.append(parsed_msg)
            
            if not parsed_messages:
                yield event.plain_result("❌ 无法解析群聊消息")
                return

            # Check message count threshold
            min_threshold = config_manager.get_min_messages_threshold()
            if len(parsed_messages) < min_threshold:
                yield event.plain_result(
                    f"❌ 消息数量不足（{len(parsed_messages)}条），"
                    f"至少需要{min_threshold}条消息才能进行有效分析"
                )
                return

            yield event.plain_result(f"📊 已获取{len(parsed_messages)}条消息，正在进行智能分析...")

            # Step 3: Perform analysis using new analyzers
            from .src.models import AnalysisResult, TokenUsage
            from datetime import datetime
            
            # Get unified_msg_origin for LLM provider
            umo = event.unified_msg_origin
            
            # Analyze topics
            topics = []
            topics_token_usage = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
            if config_manager.get_topic_analysis_enabled():
                try:
                    topics, topics_token_usage = await topics_analyzer.analyze(parsed_messages, umo)
                    logger.info(f"Topics analysis complete: {len(topics)} topics found")
                except Exception as e:
                    logger.error(f"Topics analysis failed: {e}", exc_info=True)
            
            # Analyze users
            user_titles = []
            users_token_usage = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
            if config_manager.get_user_title_analysis_enabled():
                try:
                    user_titles, users_token_usage = await users_analyzer.analyze(parsed_messages, umo)
                    logger.info(f"Users analysis complete: {len(user_titles)} titles assigned")
                except Exception as e:
                    logger.error(f"Users analysis failed: {e}", exc_info=True)
            
            # Extract quotes
            quotes = []
            quotes_token_usage = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
            try:
                quotes, quotes_token_usage = await quotes_analyzer.analyze(parsed_messages, umo)
                logger.info(f"Quotes analysis complete: {len(quotes)} quotes extracted")
            except Exception as e:
                logger.error(f"Quotes analysis failed: {e}", exc_info=True)
            
            # Calculate statistics
            statistics = statistics_calculator.calculate(parsed_messages)
            logger.info(f"Statistics calculated: {statistics.message_count} messages")
            
            # Aggregate token usage
            total_token_usage = TokenUsage(
                prompt_tokens=(
                    topics_token_usage.prompt_tokens +
                    users_token_usage.prompt_tokens +
                    quotes_token_usage.prompt_tokens
                ),
                completion_tokens=(
                    topics_token_usage.completion_tokens +
                    users_token_usage.completion_tokens +
                    quotes_token_usage.completion_tokens
                ),
                total_tokens=(
                    topics_token_usage.total_tokens +
                    users_token_usage.total_tokens +
                    quotes_token_usage.total_tokens
                )
            )
            
            # Determine analysis period
            if parsed_messages:
                timestamps = [msg.timestamp for msg in parsed_messages]
                start_time = datetime.fromtimestamp(min(timestamps))
                end_time = datetime.fromtimestamp(max(timestamps))
            else:
                start_time = datetime.now()
                end_time = datetime.now()
            
            # Create analysis result
            analysis_result = AnalysisResult(
                topics=topics,
                user_titles=user_titles,
                quotes=quotes,
                statistics=statistics,
                token_usage=total_token_usage,
                analysis_period=(start_time, end_time)
            )

            # Step 4: Generate report
            output_format = config_manager.get_output_format()
            if output_format == "image":
                image_url = await report_generator.generate_image_report(analysis_result, group_id, self.html_render)
                if image_url:
                    yield event.image_result(image_url)
                else:
                    logger.warning("图片报告生成失败，回退到文本报告")
                    text_report = report_generator.generate_text_report(analysis_result)
                    yield event.plain_result(f"⚠️ 图片报告生成失败，以下是文本版本：\n\n{text_report}")
            elif output_format == "pdf":
                if not config_manager.pyppeteer_available:
                    yield event.plain_result("❌ PDF 功能不可用，请使用 /安装PDF 命令安装 pyppeteer==1.0.2")
                    return

                pdf_path = await report_generator.generate_pdf_report(analysis_result, group_id)
                if pdf_path:
                    from pathlib import Path
                    pdf_file = File(name=Path(pdf_path).name, file=pdf_path)
                    result = event.make_result()
                    result.chain.append(pdf_file)
                    yield result
                else:
                    yield event.plain_result("❌ PDF 报告生成失败")
                    yield event.plain_result("🔧 可能的解决方案：")
                    yield event.plain_result("1. 使用 /安装PDF 命令重新安装依赖")
                    yield event.plain_result("2. 检查网络连接是否正常")
                    yield event.plain_result("3. 暂时使用图片格式：/设置格式 image")

                    logger.warning("PDF 报告生成失败，回退到文本报告")
                    text_report = report_generator.generate_text_report(analysis_result)
                    yield event.plain_result(f"\n📝 以下是文本版本的分析报告：\n\n{text_report}")
            else:
                text_report = report_generator.generate_text_report(analysis_result)
                yield event.plain_result(text_report)

        except Exception as e:
            logger.error(f"群分析失败: {e}", exc_info=True)
            yield event.plain_result(f"❌ 分析失败: {str(e)}。请检查网络连接和LLM配置，或联系管理员")



    @filter.command("设置格式")
    @filter.permission_type(PermissionType.ADMIN)
    async def set_output_format(self, event: LarkMessageEvent, format_type: str = ""):
        """
        设置分析报告输出格式
        用法: /设置格式 [image|text|pdf]
        """
        if not isinstance(event, LarkMessageEvent):
            yield event.plain_result("❌ 此功能仅支持飞书群聊")
            return

        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        if not format_type:
            current_format = config_manager.get_output_format()
            pdf_status = '✅' if config_manager.pyppeteer_available else '❌ (需安装 pyppeteer)'
            yield event.plain_result(f"""📊 当前输出格式: {current_format}

可用格式:
• image - 图片格式 (默认)
• text - 文本格式
• pdf - PDF 格式 {pdf_status}

用法: /设置格式 [格式名称]""")
            return

        format_type = format_type.lower()
        if format_type not in ["image", "text", "pdf"]:
            yield event.plain_result("❌ 无效的格式类型，支持: image, text, pdf")
            return

        if format_type == "pdf" and not config_manager.pyppeteer_available:
            yield event.plain_result("❌ PDF 格式不可用，请使用 /安装PDF 命令安装 pyppeteer==1.0.2")
            return

        config_manager.set_output_format(format_type)
        yield event.plain_result(f"✅ 输出格式已设置为: {format_type}")

    @filter.command("安装PDF")
    @filter.permission_type(PermissionType.ADMIN)
    async def install_pdf_deps(self, event: LarkMessageEvent):
        """
        安装 PDF 功能依赖
        用法: /安装PDF
        """
        if not isinstance(event, LarkMessageEvent):
            yield event.plain_result("❌ 此功能仅支持飞书群聊")
            return

        yield event.plain_result("🔄 开始安装 PDF 功能依赖，请稍候...")

        try:
            # 使用模块化的PDF安装器
            result = await PDFInstaller.install_pyppeteer(config_manager)
            yield event.plain_result(result)

        except Exception as e:
            logger.error(f"安装 PDF 依赖失败: {e}", exc_info=True)
            yield event.plain_result(f"❌ 安装过程中出现错误: {str(e)}")

    @filter.command("分析设置")
    @filter.permission_type(PermissionType.ADMIN)
    async def analysis_settings(self, event: LarkMessageEvent, action: str = "status"):
        """
        管理分析设置
        用法: /分析设置 [enable|disable|status|reload|test]
        - enable: 启用当前群的分析功能
        - disable: 禁用当前群的分析功能
        - status: 查看当前状态
        - reload: 重新加载配置并重启定时任务
        - test: 测试自动分析功能
        """
        if not isinstance(event, LarkMessageEvent):
            yield event.plain_result("❌ 此功能仅支持飞书群聊")
            return

        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        if action == "enable":
            enabled_groups = config_manager.get_enabled_groups()
            if group_id not in enabled_groups:
                config_manager.add_enabled_group(group_id)
                yield event.plain_result("✅ 已为当前群启用日常分析功能")
                # TODO: Update auto_scheduler to use new architecture
                # await auto_scheduler.restart_scheduler()
            else:
                yield event.plain_result("ℹ️ 当前群已启用日常分析功能")

        elif action == "disable":
            enabled_groups = config_manager.get_enabled_groups()
            if group_id in enabled_groups:
                config_manager.remove_enabled_group(group_id)
                yield event.plain_result("✅ 已为当前群禁用日常分析功能")
                # TODO: Update auto_scheduler to use new architecture
                # await auto_scheduler.restart_scheduler()
            else:
                yield event.plain_result("ℹ️ 当前群未启用日常分析功能")

        elif action == "reload":
            # 重新加载配置
            config_manager.reload_config()
            # TODO: Update auto_scheduler to use new architecture
            # await auto_scheduler.restart_scheduler()
            yield event.plain_result("✅ 已重新加载配置")

        elif action == "test":
            # 测试自动分析功能
            enabled_groups = config_manager.get_enabled_groups()
            if group_id not in enabled_groups:
                yield event.plain_result("❌ 请先启用当前群的分析功能")
                return

            yield event.plain_result("🧪 测试功能将在自动调度器更新后可用")
            # TODO: Implement test functionality with new architecture

        else:  # status
            enabled_groups = config_manager.get_enabled_groups()
            status = "已启用" if group_id in enabled_groups else "未启用"
            auto_status = "已启用" if config_manager.get_enable_auto_analysis() else "未启用"
            auto_time = config_manager.get_auto_analysis_time()

            pdf_status = PDFInstaller.get_pdf_status(config_manager)
            output_format = config_manager.get_output_format()
            min_threshold = config_manager.get_min_messages_threshold()
            max_rounds = config_manager.get_max_query_rounds()

            yield event.plain_result(f"""📊 当前群分析功能状态:
• 群分析功能: {status}
• 自动分析: {auto_status} ({auto_time})
• 输出格式: {output_format}
• PDF 功能: {pdf_status}
• 最小消息数: {min_threshold}
• 最大查询轮数: {max_rounds}

💡 可用命令: enable, disable, status, reload, test
💡 支持的输出格式: image, text, pdf (图片和PDF包含活跃度可视化)
💡 其他命令: /设置格式, /安装PDF""")


