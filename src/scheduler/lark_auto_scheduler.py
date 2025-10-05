"""
飞书自动调度器模块
负责定时任务和自动分析功能（适配新架构）
"""

import asyncio
from datetime import datetime, timedelta
from astrbot.api import logger


class LarkAutoScheduler:
    """飞书自动调度器（新架构）"""

    def __init__(
        self,
        config_manager,
        lark_client_manager,
        message_fetcher,
        message_parser,
        topics_analyzer,
        users_analyzer,
        quotes_analyzer,
        statistics_calculator,
        report_generator,
        context,
        html_render_func=None,
    ):
        """
        初始化飞书自动调度器

        Args:
            config_manager: 配置管理器
            lark_client_manager: 飞书客户端管理器
            message_fetcher: 消息获取器
            message_parser: 消息解析器
            topics_analyzer: 话题分析器
            users_analyzer: 用户分析器
            quotes_analyzer: 金句分析器
            statistics_calculator: 统计计算器
            report_generator: 报告生成器
            context: AstrBot上下文
            html_render_func: HTML渲染函数
        """
        self.config_manager = config_manager
        self.lark_client_manager = lark_client_manager
        self.message_fetcher = message_fetcher
        self.message_parser = message_parser
        self.topics_analyzer = topics_analyzer
        self.users_analyzer = users_analyzer
        self.quotes_analyzer = quotes_analyzer
        self.statistics_calculator = statistics_calculator
        self.report_generator = report_generator
        self.context = context
        self.html_render_func = html_render_func
        self.scheduler_task = None
        self.last_execution_date = None  # 记录上次执行日期，防止重复执行

    async def start_scheduler(self):
        """启动定时任务调度器"""
        if not self.config_manager.get_enable_auto_analysis():
            logger.info("自动分析功能未启用")
            return

        # 检查飞书客户端是否可用
        if not self.lark_client_manager.is_available():
            logger.warning("飞书客户端不可用，无法启动自动调度器")
            return

        logger.info(
            f"启动定时任务调度器，自动分析时间: {self.config_manager.get_auto_analysis_time()}"
        )

        self.scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def stop_scheduler(self):
        """停止定时任务调度器"""
        if self.scheduler_task and not self.scheduler_task.done():
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
            logger.info("已停止定时任务调度器")

    async def restart_scheduler(self):
        """重启定时任务调度器"""
        await self.stop_scheduler()
        if self.config_manager.get_enable_auto_analysis():
            await self.start_scheduler()

    async def _scheduler_loop(self):
        """调度器主循环"""
        while True:
            try:
                now = datetime.now()
                target_time = datetime.strptime(
                    self.config_manager.get_auto_analysis_time(), "%H:%M"
                ).replace(year=now.year, month=now.month, day=now.day)

                # 如果今天的目标时间已过，设置为明天
                if now >= target_time:
                    target_time += timedelta(days=1)

                # 计算等待时间
                wait_seconds = (target_time - now).total_seconds()
                logger.info(
                    f"定时分析将在 {target_time.strftime('%Y-%m-%d %H:%M:%S')} 执行，等待 {wait_seconds:.0f} 秒"
                )

                # 等待到目标时间
                await asyncio.sleep(wait_seconds)

                # 执行自动分析
                if self.config_manager.get_enable_auto_analysis():
                    # 检查是否今天已经执行过
                    if self.last_execution_date == target_time.date():
                        logger.info(
                            f"今天 {target_time.date()} 已经执行过自动分析，跳过执行"
                        )
                        # 等待到明天再检查
                        await asyncio.sleep(3600)  # 等待1小时后再检查
                        continue

                    logger.info("开始执行定时分析")
                    await self._run_auto_analysis()
                    self.last_execution_date = target_time.date()  # 记录执行日期
                    logger.info(f"定时分析执行完成，记录执行日期: {target_time.date()}")
                else:
                    logger.info("自动分析已禁用，跳过执行")
                    break

            except asyncio.CancelledError:
                logger.info("调度器任务被取消")
                break
            except Exception as e:
                logger.error(f"定时任务调度器错误: {e}", exc_info=True)
                # 等待5分钟后重试
                await asyncio.sleep(300)

    async def _run_auto_analysis(self):
        """执行自动分析"""
        try:
            logger.info("开始执行自动群聊分析")

            # 为每个启用的群执行分析
            enabled_groups = self.config_manager.get_enabled_groups()
            if not enabled_groups:
                logger.info("没有启用的群组，跳过自动分析")
                return

            for group_id in enabled_groups:
                try:
                    logger.info(f"为群 {group_id} 执行自动分析")
                    await self._perform_auto_analysis_for_group(group_id)
                except Exception as e:
                    logger.error(f"群 {group_id} 自动分析失败: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"自动分析执行失败: {e}", exc_info=True)

    async def _perform_auto_analysis_for_group(self, group_id: str):
        """为指定群执行自动分析"""
        try:
            logger.info(f"开始为群 {group_id} 执行自动分析")

            # 获取分析天数
            analysis_days = self.config_manager.get_analysis_days()

            # 步骤1: 获取原始消息
            raw_messages = await self.message_fetcher.fetch_messages(
                chat_id=group_id,
                days=analysis_days,
                max_messages=self.config_manager.get_max_messages(),
                container_id_type="chat",
            )

            if not raw_messages:
                logger.warning(f"群 {group_id} 未获取到足够的消息记录")
                return

            # 步骤2: 解析消息
            parsed_messages = []
            for msg in raw_messages:
                parsed_msg = await self.message_parser.parse_message(msg)
                if parsed_msg:
                    parsed_messages.append(parsed_msg)

            if not parsed_messages:
                logger.warning(f"群 {group_id} 无法解析消息")
                return

            # 检查消息数量
            min_threshold = self.config_manager.get_min_messages_threshold()
            if len(parsed_messages) < min_threshold:
                logger.warning(
                    f"群 {group_id} 消息数量不足（{len(parsed_messages)}条），跳过分析"
                )
                return

            logger.info(f"群 {group_id} 获取到 {len(parsed_messages)} 条消息，开始分析")

            # 步骤3: 执行分析
            from ..models import AnalysisResult, TokenUsage

            # 构造 unified_msg_origin
            umo = f"lark:group:{group_id}"

            # 分析话题
            topics = []
            topics_token_usage = TokenUsage(
                prompt_tokens=0, completion_tokens=0, total_tokens=0
            )
            if self.config_manager.get_topic_analysis_enabled():
                try:
                    topics, topics_token_usage = await self.topics_analyzer.analyze(
                        parsed_messages, umo
                    )
                    logger.info(f"话题分析完成: 提取了{len(topics)}个话题")
                except Exception as e:
                    logger.error(f"话题分析失败: {e}", exc_info=True)

            # 分析用户
            user_titles = []
            users_token_usage = TokenUsage(
                prompt_tokens=0, completion_tokens=0, total_tokens=0
            )
            if self.config_manager.get_user_title_analysis_enabled():
                try:
                    user_titles, users_token_usage = await self.users_analyzer.analyze(
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
            if self.config_manager.get_golden_quotes_analysis_enabled():
                try:
                    quotes, quotes_token_usage = await self.quotes_analyzer.analyze(
                        parsed_messages, umo
                    )
                    logger.info(f"金句分析完成: 提取了{len(quotes)}条金句")
                except Exception as e:
                    logger.error(f"金句分析失败: {e}", exc_info=True)

            # 计算统计数据
            statistics = self.statistics_calculator.calculate(parsed_messages)
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

            # 步骤4: 生成并发送报告
            await self._send_analysis_report(group_id, analysis_result)

        except Exception as e:
            logger.error(f"群 {group_id} 自动分析执行失败: {e}", exc_info=True)

    async def _send_analysis_report(self, group_id: str, analysis_result):
        """发送分析报告到群"""
        try:
            output_format = self.config_manager.get_output_format()

            if output_format == "image":
                if self.html_render_func:
                    # 使用图片格式
                    logger.info(f"群 {group_id} 自动分析使用图片报告格式")
                    try:
                        image_url = await self.report_generator.generate_image_report(
                            analysis_result, group_id, self.html_render_func
                        )
                        if image_url:
                            await self._send_lark_message(
                                group_id,
                                "📊 每日群聊分析报告已生成",
                                image_url=image_url,
                            )
                            logger.info(f"群 {group_id} 图片报告发送成功")
                        else:
                            # 图片生成失败，回退到文本
                            logger.warning(
                                f"群 {group_id} 图片报告生成失败，回退到文本报告"
                            )
                            text_report = self.report_generator.generate_text_report(
                                analysis_result
                            )
                            await self._send_lark_message(
                                group_id, f"📊 每日群聊分析报告：\n\n{text_report}"
                            )
                    except Exception as img_e:
                        logger.error(
                            f"群 {group_id} 图片报告生成异常: {img_e}，回退到文本报告",
                            exc_info=True,
                        )
                        text_report = self.report_generator.generate_text_report(
                            analysis_result
                        )
                        await self._send_lark_message(
                            group_id, f"📊 每日群聊分析报告：\n\n{text_report}"
                        )
                else:
                    # 没有html_render函数，回退到文本报告
                    logger.warning(f"群 {group_id} 缺少html_render函数，回退到文本报告")
                    text_report = self.report_generator.generate_text_report(
                        analysis_result
                    )
                    await self._send_lark_message(
                        group_id, f"📊 每日群聊分析报告：\n\n{text_report}"
                    )

            elif output_format == "pdf":
                if not self.config_manager.pyppeteer_available:
                    logger.warning(f"群 {group_id} PDF功能不可用，回退到文本报告")
                    text_report = self.report_generator.generate_text_report(
                        analysis_result
                    )
                    await self._send_lark_message(
                        group_id, f"📊 每日群聊分析报告：\n\n{text_report}"
                    )
                else:
                    try:
                        pdf_path = await self.report_generator.generate_pdf_report(
                            analysis_result, group_id
                        )
                        if pdf_path:
                            await self._send_lark_message(
                                group_id,
                                "📊 每日群聊分析报告已生成",
                                file_path=pdf_path,
                            )
                            logger.info(f"群 {group_id} PDF报告发送成功")
                        else:
                            logger.error(
                                f"群 {group_id} PDF报告生成失败，回退到文本报告"
                            )
                            text_report = self.report_generator.generate_text_report(
                                analysis_result
                            )
                            await self._send_lark_message(
                                group_id, f"📊 每日群聊分析报告：\n\n{text_report}"
                            )
                    except Exception as pdf_e:
                        logger.error(
                            f"群 {group_id} PDF报告生成异常: {pdf_e}，回退到文本报告",
                            exc_info=True,
                        )
                        text_report = self.report_generator.generate_text_report(
                            analysis_result
                        )
                        await self._send_lark_message(
                            group_id, f"📊 每日群聊分析报告：\n\n{text_report}"
                        )
            else:
                text_report = self.report_generator.generate_text_report(
                    analysis_result
                )
                await self._send_lark_message(
                    group_id, f"📊 每日群聊分析报告：\n\n{text_report}"
                )

            logger.info(f"群 {group_id} 自动分析完成，已发送报告")

        except Exception as e:
            logger.error(f"发送分析报告到群 {group_id} 失败: {e}", exc_info=True)

    async def _send_lark_message(
        self, chat_id: str, text: str, image_url: str = None, file_path: str = None
    ):
        """发送飞书消息"""
        try:
            # 获取飞书客户端
            client = self.lark_client_manager.get_client()

            # 构建消息内容
            if image_url:
                # 发送图片消息
                await self._send_image_message(client, chat_id, text, image_url)
            elif file_path:
                # 发送文件消息
                await self._send_file_message(client, chat_id, text, file_path)
            else:
                # 发送文本消息
                await self._send_text_message(client, chat_id, text)

        except Exception as e:
            logger.error(f"发送飞书消息失败: {e}", exc_info=True)

    async def _send_text_message(self, client, chat_id: str, text: str):
        """发送文本消息到飞书群"""
        try:
            # 使用飞书SDK发送消息
            from lark_oapi.api.im.v1 import (
                CreateMessageRequest,
                CreateMessageRequestBody,
            )
            import json

            request = (
                CreateMessageRequest.builder()
                .receive_id_type("chat_id")
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("text")
                    .content(json.dumps({"text": text}))
                    .build()
                )
                .build()
            )

            response = client.im.v1.message.create(request)

            if not response.success():
                logger.error(
                    f"发送飞书文本消息失败: code={response.code}, msg={response.msg}"
                )
            else:
                logger.info(f"飞书文本消息发送成功: chat_id={chat_id}")

        except Exception as e:
            logger.error(f"发送飞书文本消息失败: {e}", exc_info=True)

    async def _send_image_message(
        self, client, chat_id: str, text: str, image_url: str
    ):
        """发送图片消息到飞书群"""
        try:
            from lark_oapi.api.im.v1 import (
                CreateMessageRequest,
                CreateMessageRequestBody,
                CreateImageRequest,
                CreateImageRequestBody,
            )
            import json
            import aiohttp
            import io

            # 先发送文本消息
            await self._send_text_message(client, chat_id, text)

            # 下载图片
            logger.info(f"开始下载图片: {image_url}")
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status != 200:
                        logger.error(f"下载图片失败: HTTP {resp.status}")
                        return
                    image_data = await resp.read()

            # 上传图片到飞书
            logger.info("开始上传图片到飞书")
            upload_request = (
                CreateImageRequest.builder()
                .request_body(
                    CreateImageRequestBody.builder()
                    .image_type("message")
                    .image(io.BytesIO(image_data))
                    .build()
                )
                .build()
            )

            upload_response = client.im.v1.image.create(upload_request)

            if not upload_response.success():
                logger.error(
                    f"上传图片到飞书失败: code={upload_response.code}, msg={upload_response.msg}"
                )
                return

            # 获取图片key
            image_key = upload_response.data.image_key
            logger.info(f"图片上传成功，image_key={image_key}")

            # 发送图片消息
            message_request = (
                CreateMessageRequest.builder()
                .receive_id_type("chat_id")
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("image")
                    .content(json.dumps({"image_key": image_key}))
                    .build()
                )
                .build()
            )

            message_response = client.im.v1.message.create(message_request)

            if not message_response.success():
                logger.error(
                    f"发送飞书图片消息失败: code={message_response.code}, msg={message_response.msg}"
                )
            else:
                logger.info(f"飞书图片消息发送成功: chat_id={chat_id}")

        except Exception as e:
            logger.error(f"发送飞书图片消息失败: {e}", exc_info=True)
            # 失败时回退到文本消息
            logger.info("图片发送失败，回退到文本消息")
            await self._send_text_message(
                client, chat_id, f"{text}\n\n图片链接: {image_url}"
            )

    async def _send_file_message(self, client, chat_id: str, text: str, file_path: str):
        """发送文件消息到飞书群"""
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

            # 先发送文本消息
            await self._send_text_message(client, chat_id, text)

            # 检查文件是否存在
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.error(f"文件不存在: {file_path}")
                return

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
                logger.error(
                    f"上传文件到飞书失败: code={upload_response.code}, msg={upload_response.msg}"
                )
                return

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
                logger.error(
                    f"发送飞书文件消息失败: code={message_response.code}, msg={message_response.msg}"
                )
            else:
                logger.info(f"飞书文件消息发送成功: chat_id={chat_id}")

        except Exception as e:
            logger.error(f"发送飞书文件消息失败: {e}", exc_info=True)
            # 失败时回退到文本消息
            logger.info("文件发送失败，回退到文本消息")
            await self._send_text_message(
                client, chat_id, f"{text}\n\n文件路径: {file_path}"
            )
