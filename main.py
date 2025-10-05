"""
飞书群日常分析插件
基于群聊记录生成精美的日常分析报告，包含话题总结、用户画像、统计数据等

重构版本 - 使用模块化架构，适配飞书平台
"""

import time
import asyncio
from typing import Optional

from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.api import logger, AstrBotConfig
from astrbot.core.platform.sources.lark.lark_event import LarkMessageEvent
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
from .src.scheduler.lark_auto_scheduler import LarkAutoScheduler
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
        global \
            config_manager, \
            lark_client_manager, \
            user_info_cache, \
            message_fetcher, \
            message_parser
        global topics_analyzer, users_analyzer, quotes_analyzer, statistics_calculator
        global report_generator, auto_scheduler

        try:
            # 初始化配置管理器
            config_manager = ConfigManager(config)

            # 初始化飞书客户端管理器（延迟初始化 - 首次使用时连接）
            lark_client_manager = LarkClientManager(context)
            logger.info("飞书客户端管理器已创建（将在首次使用时初始化）")

            # 初始化用户信息缓存，包含用户名映射配置
            user_info_cache = UserInfoCache(
                lark_client_manager, ttl=3600, config_manager=config_manager
            )
            logger.info("用户信息缓存已初始化")

            # 初始化消息获取器和解析器
            message_fetcher = MessageFetcher(lark_client_manager)
            message_parser = MessageParser(user_info_cache)
            logger.info("消息获取器和解析器已初始化")

            # 初始化分析器
            topics_analyzer = TopicsAnalyzer(context, config_manager)
            users_analyzer = UsersAnalyzer(context, config_manager)
            quotes_analyzer = QuotesAnalyzer(context, config_manager)
            statistics_calculator = StatisticsCalculator()
            logger.info("分析模块已初始化")

            # 初始化报告生成器
            report_generator = ReportGenerator(config_manager)
            logger.info("报告生成器已初始化")

            # 初始化自动调度器
            auto_scheduler = LarkAutoScheduler(
                config_manager=config_manager,
                lark_client_manager=lark_client_manager,
                message_fetcher=message_fetcher,
                message_parser=message_parser,
                topics_analyzer=topics_analyzer,
                users_analyzer=users_analyzer,
                quotes_analyzer=quotes_analyzer,
                statistics_calculator=statistics_calculator,
                report_generator=report_generator,
                context=context,
                html_render_func=self.html_render,
            )
            logger.info("自动调度器已初始化")

            # 延迟启动自动调度器
            if config_manager.get_enable_auto_analysis():
                asyncio.create_task(self._delayed_start_scheduler())

            logger.info("飞书群日常分析插件已初始化（重构版本）")

        except Exception as e:
            logger.error(f"插件初始化失败: {e}", exc_info=True)
            raise

    async def _delayed_start_scheduler(self):
        """延迟启动调度器，给系统时间初始化"""
        try:
            # 等待10秒让系统完全初始化
            await asyncio.sleep(10)

            # 启动自动调度器
            await auto_scheduler.start_scheduler()
            logger.info("自动调度器已启动")

        except Exception as e:
            logger.error(f"延迟启动调度器失败: {e}", exc_info=True)

    async def _reload_config_and_restart_scheduler(self):
        """重新加载配置并重启调度器"""
        try:
            # 重新加载配置
            config_manager.reload_config()
            logger.info(
                f"重新加载配置: 自动分析={config_manager.get_enable_auto_analysis()}"
            )

            # 重启自动调度器
            if auto_scheduler:
                await auto_scheduler.restart_scheduler()
                logger.info("自动调度器已重启")

            logger.info("配置重载完成")

        except Exception as e:
            logger.error(f"重新加载配置失败: {e}", exc_info=True)

    async def _send_lark_file(self, chat_id: str, file_path: str):
        """使用飞书SDK发送文件"""
        try:
            from lark_oapi.api.im.v1 import (
                CreateMessageRequest,
                CreateMessageRequestBody,
                CreateFileRequest,
                CreateFileRequestBody,
            )
            import json
            import io
            from pathlib import Path

            # 获取飞书客户端
            client = lark_client_manager.get_client()

            # 检查文件是否存在
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.error(f"文件不存在: {file_path}")
                raise FileNotFoundError(f"文件不存在: {file_path}")

            # 读取文件
            logger.info(f"开始读取文件: {file_path}")
            with open(file_path, "rb") as f:
                file_data = f.read()

            # 上传文件到飞书
            logger.info("开始上传文件到飞书")
            upload_request = (
                CreateFileRequest.builder()
                .request_body(
                    CreateFileRequestBody.builder()
                    .file_type("pdf" if file_path.endswith(".pdf") else "stream")
                    .file_name(file_path_obj.name)
                    .file(io.BytesIO(file_data))
                    .build()
                )
                .build()
            )

            upload_response = client.im.v1.file.create(upload_request)

            if not upload_response.success():
                error_msg = f"上传文件到飞书失败: code={upload_response.code}, msg={upload_response.msg}"
                logger.error(error_msg)
                raise Exception(error_msg)

            # 获取文件key
            file_key = upload_response.data.file_key
            logger.info(f"文件上传成功，file_key={file_key}")

            # 发送文件消息
            message_request = (
                CreateMessageRequest.builder()
                .receive_id_type("chat_id")
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("file")
                    .content(json.dumps({"file_key": file_key}))
                    .build()
                )
                .build()
            )

            message_response = client.im.v1.message.create(message_request)

            if not message_response.success():
                error_msg = f"发送飞书文件消息失败: code={message_response.code}, msg={message_response.msg}"
                logger.error(error_msg)
                raise Exception(error_msg)

            logger.info(f"飞书文件消息发送成功: chat_id={chat_id}")

        except Exception as e:
            logger.error(f"发送飞书文件失败: {e}", exc_info=True)
            raise

    async def terminate(self):
        """插件被卸载/停用时调用，清理资源"""
        try:
            logger.info("开始清理飞书群日常分析插件资源...")

            global config_manager, lark_client_manager, user_info_cache
            global message_fetcher, message_parser
            global \
                topics_analyzer, \
                users_analyzer, \
                quotes_analyzer, \
                statistics_calculator
            global report_generator, auto_scheduler

            # 停止自动调度器（如果已初始化）
            if auto_scheduler:
                logger.info("正在停止自动调度器...")
                await auto_scheduler.stop_scheduler()
                logger.info("自动调度器已停止")

            # 清理用户信息缓存
            if user_info_cache:
                logger.info("正在清理用户信息缓存...")
                # 清空缓存
                if hasattr(user_info_cache, "_cache"):
                    user_info_cache._cache.clear()
                logger.info("用户信息缓存已清理")

            # 重置全局变量
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

            logger.info("飞书群日常分析插件资源清理完成")

        except Exception as e:
            logger.error(f"插件资源清理失败: {e}", exc_info=True)

    @filter.command("历史消息示例")

    async def show_history_example(self, event: LarkMessageEvent, days: int = 1):
        """
        获取并展示飞书群历史消息示例
        用法: /历史消息示例 [天数]
        """

        # 检查插件是否可用
        if lark_client_manager is None or not lark_client_manager.is_available():
            yield event.plain_result(
                "❌ 插件未启用：未找到 Lark 平台适配器。请先配置 Lark 平台。"
            )
            return

        if not isinstance(event, LarkMessageEvent):
            yield event.plain_result("❌ 此功能仅支持飞书群聊")
            return

        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        try:
            # 使用新架构获取消息
            raw_messages = await message_fetcher.fetch_messages(
                chat_id=group_id, days=days, max_messages=20, container_id_type="chat"
            )

            if not raw_messages:
                yield event.plain_result("❌ 未获取到历史消息")
                return

            # 解析消息
            parsed_messages = []
            for msg in raw_messages[:5]:
                parsed_msg = await message_parser.parse_message(msg)
                if parsed_msg:
                    parsed_messages.append(parsed_msg)

            if not parsed_messages:
                yield event.plain_result("❌ 无法解析历史消息")
                return

            # 格式化预览
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

    async def analyze_group_daily(
        self, event: LarkMessageEvent, days: Optional[int] = None
    ):
        """
        分析群聊日常活动
        用法: /群分析 [天数]
        """
        # 检查插件是否可用
        if lark_client_manager is None or not lark_client_manager.is_available():
            yield event.plain_result(
                "❌ 插件未启用：未找到 Lark 平台适配器。请先配置 Lark 平台。"
            )
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
        analysis_days = (
            days if days and 1 <= days <= 30 else config_manager.get_analysis_days()
        )

        yield event.plain_result(f"🔍 开始分析群聊近{analysis_days}天的活动，请稍候...")

        logger.info(f"当前输出格式配置: {config_manager.get_output_format()}")

        try:
            # 步骤1: 使用新的消息获取器获取原始消息
            raw_messages = await message_fetcher.fetch_messages(
                chat_id=group_id,
                days=analysis_days,
                max_messages=config_manager.get_max_messages(),
                container_id_type="chat",
            )

            if not raw_messages:
                yield event.plain_result(
                    "❌ 未找到足够的群聊记录，请确保群内有足够的消息历史"
                )
                return

            # 步骤2: 将消息解析为统一格式
            parsed_messages = []
            for msg in raw_messages:
                parsed_msg = await message_parser.parse_message(msg)
                if parsed_msg:
                    parsed_messages.append(parsed_msg)

            if not parsed_messages:
                yield event.plain_result("❌ 无法解析群聊消息")
                return

            # 检查消息数量阈值
            min_threshold = config_manager.get_min_messages_threshold()
            if len(parsed_messages) < min_threshold:
                yield event.plain_result(
                    f"❌ 消息数量不足（{len(parsed_messages)}条），"
                    f"至少需要{min_threshold}条消息才能进行有效分析"
                )
                return

            yield event.plain_result(
                f"📊 已获取{len(parsed_messages)}条消息，正在进行智能分析..."
            )

            # 步骤3: 使用新分析器进行分析
            from .src.models import AnalysisResult, TokenUsage
            from datetime import datetime

            # 获取LLM提供者的统一消息来源
            umo = event.unified_msg_origin

            # 分析话题
            topics = []
            topics_token_usage = TokenUsage(
                prompt_tokens=0, completion_tokens=0, total_tokens=0
            )
            if config_manager.get_topic_analysis_enabled():
                try:
                    topics, topics_token_usage = await topics_analyzer.analyze(
                        parsed_messages, umo
                    )
                    logger.info(f"Topics analysis complete: {len(topics)} topics found")
                except Exception as e:
                    logger.error(f"Topics analysis failed: {e}", exc_info=True)

            # 分析用户
            user_titles = []
            users_token_usage = TokenUsage(
                prompt_tokens=0, completion_tokens=0, total_tokens=0
            )
            if config_manager.get_user_title_analysis_enabled():
                try:
                    user_titles, users_token_usage = await users_analyzer.analyze(
                        parsed_messages, umo
                    )
                    logger.info(f"用户分析完成: 分配了{len(user_titles)}个称号")
                except Exception as e:
                    logger.error(f"用户分析失败: {e}", exc_info=True)

            # 提取金句
            quotes = []
            quotes_token_usage = TokenUsage(
                prompt_tokens=0, completion_tokens=0, total_tokens=0
            )
            try:
                quotes, quotes_token_usage = await quotes_analyzer.analyze(
                    parsed_messages, umo
                )
                logger.info(f"金句分析完成: 提取了{len(quotes)}条金句")
            except Exception as e:
                logger.error(f"金句分析失败: {e}", exc_info=True)

            # 计算统计数据
            statistics = statistics_calculator.calculate(parsed_messages)
            logger.info(f"统计数据计算完成: {statistics.message_count}条消息")

            # 汇总token使用量
            total_token_usage = TokenUsage(
                prompt_tokens=(
                    topics_token_usage.prompt_tokens
                    + users_token_usage.prompt_tokens
                    + quotes_token_usage.prompt_tokens
                ),
                completion_tokens=(
                    topics_token_usage.completion_tokens
                    + users_token_usage.completion_tokens
                    + quotes_token_usage.completion_tokens
                ),
                total_tokens=(
                    topics_token_usage.total_tokens
                    + users_token_usage.total_tokens
                    + quotes_token_usage.total_tokens
                ),
            )

            # 确定分析时间段
            if parsed_messages:
                timestamps = [msg.timestamp for msg in parsed_messages]
                start_time = datetime.fromtimestamp(min(timestamps))
                end_time = datetime.fromtimestamp(max(timestamps))
            else:
                start_time = datetime.now()
                end_time = datetime.now()

            # 创建分析结果
            analysis_result = AnalysisResult(
                topics=topics,
                user_titles=user_titles,
                quotes=quotes,
                statistics=statistics,
                token_usage=total_token_usage,
                analysis_period=(start_time, end_time),
            )

            # 步骤4: 生成报告
            output_format = config_manager.get_output_format()
            if output_format == "image":
                image_url = await report_generator.generate_image_report(
                    analysis_result, group_id, self.html_render
                )
                if image_url:
                    yield event.image_result(image_url)
                else:
                    logger.warning("图片报告生成失败，回退到文本报告")
                    text_report = report_generator.generate_text_report(analysis_result)
                    yield event.plain_result(
                        f"⚠️ 图片报告生成失败，以下是文本版本：\n\n{text_report}"
                    )
            elif output_format == "pdf":
                if not config_manager.pyppeteer_available:
                    yield event.plain_result(
                        "❌ PDF 功能不可用，请使用 /安装PDF 命令安装 pyppeteer==1.0.2"
                    )
                    return

                pdf_path = await report_generator.generate_pdf_report(
                    analysis_result, group_id
                )
                if pdf_path:
                    # 使用飞书SDK直接发送文件
                    try:
                        yield event.plain_result("📊 PDF报告生成成功，正在发送...")
                        await self._send_lark_file(group_id, pdf_path)
                        yield event.plain_result("✅ PDF报告已发送")
                    except Exception as e:
                        logger.error(f"发送PDF文件失败: {e}", exc_info=True)
                        yield event.plain_result(f"❌ PDF文件发送失败: {str(e)}")
                        yield event.plain_result(f"📁 PDF文件已保存至: {pdf_path}")
                else:
                    yield event.plain_result("❌ PDF 报告生成失败")
                    yield event.plain_result("🔧 可能的解决方案：")
                    yield event.plain_result("1. 使用 /安装PDF 命令重新安装依赖")
                    yield event.plain_result("2. 检查网络连接是否正常")
                    yield event.plain_result("3. 暂时使用图片格式：/设置格式 image")

                    logger.warning("PDF 报告生成失败，回退到文本报告")
                    text_report = report_generator.generate_text_report(analysis_result)
                    yield event.plain_result(
                        f"\n📝 以下是文本版本的分析报告：\n\n{text_report}"
                    )
            else:
                text_report = report_generator.generate_text_report(analysis_result)
                yield event.plain_result(text_report)

        except Exception as e:
            logger.error(f"群分析失败: {e}", exc_info=True)
            yield event.plain_result(
                f"❌ 分析失败: {str(e)}。请检查网络连接和LLM配置，或联系管理员"
            )

    @filter.command("设置格式")

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
            pdf_status = (
                "✅" if config_manager.pyppeteer_available else "❌ (需安装 pyppeteer)"
            )
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
            yield event.plain_result(
                "❌ PDF 格式不可用，请使用 /安装PDF 命令安装 pyppeteer==1.0.2"
            )
            return

        config_manager.set_output_format(format_type)
        yield event.plain_result(f"✅ 输出格式已设置为: {format_type}")

    @filter.command("安装PDF")

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
                # 重启调度器以应用新配置
                if auto_scheduler:
                    await auto_scheduler.restart_scheduler()
            else:
                yield event.plain_result("ℹ️ 当前群已启用日常分析功能")

        elif action == "disable":
            enabled_groups = config_manager.get_enabled_groups()
            if group_id in enabled_groups:
                config_manager.remove_enabled_group(group_id)
                yield event.plain_result("✅ 已为当前群禁用日常分析功能")
                # 重启调度器以应用新配置
                if auto_scheduler:
                    await auto_scheduler.restart_scheduler()
            else:
                yield event.plain_result("ℹ️ 当前群未启用日常分析功能")

        elif action == "reload":
            # 重新加载配置
            config_manager.reload_config()
            # 重启调度器以应用新配置
            if auto_scheduler:
                await auto_scheduler.restart_scheduler()
            yield event.plain_result("✅ 已重新加载配置")

        elif action == "test":
            # 测试自动分析功能
            enabled_groups = config_manager.get_enabled_groups()
            if group_id not in enabled_groups:
                yield event.plain_result("❌ 请先启用当前群的分析功能")
                return

            if not auto_scheduler:
                yield event.plain_result("❌ 自动调度器未初始化")
                return

            yield event.plain_result("🧪 开始测试自动分析功能...")
            try:
                # 手动触发一次分析
                await auto_scheduler._perform_auto_analysis_for_group(group_id)
                yield event.plain_result("✅ 测试完成，请查看群消息")
            except Exception as e:
                logger.error(f"测试自动分析失败: {e}", exc_info=True)
                yield event.plain_result(f"❌ 测试失败: {str(e)}")

        else:  # 状态查询
            enabled_groups = config_manager.get_enabled_groups()
            status = "已启用" if group_id in enabled_groups else "未启用"
            auto_status = (
                "已启用" if config_manager.get_enable_auto_analysis() else "未启用"
            )
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
