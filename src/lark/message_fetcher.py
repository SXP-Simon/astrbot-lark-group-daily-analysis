"""
消息获取器

负责从飞书API检索消息历史记录，处理分页、时间戳转换和基础过滤
"""

from typing import List
from datetime import datetime, timedelta
from lark_oapi.api.im.v1 import ListMessageRequest
from astrbot.api import logger

from .client import LarkClientManager


class MessageFetcher:
    """
    从飞书API获取消息历史记录

    处理分页检索、时间戳转换、消息过滤和日期范围筛选
    """

    def __init__(self, client_manager: LarkClientManager):
        """
        初始化消息获取器

        Args:
            client_manager: 用于API访问的LarkClientManager实例
        """
        self._client_manager = client_manager

    async def fetch_messages(
        self,
        chat_id: str,
        days: int,
        max_messages: int = 1000,
        container_id_type: str = "chat",
    ) -> List:
        """
        从飞书API获取消息，支持分页

        Args:
            chat_id: 聊天/群组ID（例如：oc_xxx）
            days: 回溯天数
            max_messages: 最大消息数量
            container_id_type: 容器类型（"chat"或"user"）

        Returns:
            飞书消息对象列表（原始SDK格式），失败时返回空列表
        """
        try:
            # 验证输入参数
            if not chat_id or days <= 0 or max_messages <= 0:
                logger.error(
                    f"参数无效：chat_id={chat_id}, days={days}, max_messages={max_messages}"
                )
                return []

            # 计算时间范围（用于客户端过滤）
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            # 转换为毫秒级时间戳（飞书API使用毫秒）
            start_timestamp_ms = int(start_time.timestamp() * 1000)
            end_timestamp_ms = int(end_time.timestamp() * 1000)

            # 调试日志
            logger.info(
                f"获取消息：chat_id={chat_id}, 天数={days}, 最大数量={max_messages}"
            )
            logger.info(
                f"时间范围: {start_time.strftime('%Y-%m-%d %H:%M:%S')} 至 {end_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            logger.info(
                f"时间戳(毫秒): start={start_timestamp_ms}, end={end_timestamp_ms}"
            )

            # 分页获取消息（不使用时间过滤，让API返回所有消息）
            all_messages = await self._fetch_with_pagination(
                chat_id=chat_id,
                start_timestamp=None,  # 不传时间参数，获取所有消息
                end_timestamp=None,
                max_messages=max_messages * 2,  # 获取更多消息以便过滤
                container_id_type=container_id_type,
            )

            # 客户端过滤：只保留指定时间范围内的消息
            filtered_messages = []

            # 调试：显示前几条和最后几条消息的时间戳
            if all_messages:
                logger.info(f"调试：检查前3条消息的时间戳（最旧的消息）")
                for i, msg in enumerate(all_messages[:3]):
                    if hasattr(msg, "create_time"):
                        msg_time_raw = msg.create_time
                        # 尝试不同的时间戳格式
                        try:
                            if isinstance(msg_time_raw, str):
                                timestamp_val = int(msg_time_raw)
                            else:
                                timestamp_val = int(msg_time_raw)

                            # 自动检测时间戳格式（秒 vs 毫秒）
                            if timestamp_val > 10000000000:  # 看起来像毫秒
                                msg_time = datetime.fromtimestamp(timestamp_val / 1000)
                                logger.info(
                                    f"  消息{i+1}: create_time={msg_time_raw} (毫秒) "
                                    f"→ {msg_time.strftime('%Y-%m-%d %H:%M:%S')}"
                                )
                            else:  # 看起来像秒
                                msg_time = datetime.fromtimestamp(timestamp_val)
                                logger.info(
                                    f"  消息{i+1}: create_time={msg_time_raw} (秒) "
                                    f"→ {msg_time.strftime('%Y-%m-%d %H:%M:%S')}"
                                )
                        except Exception as e:
                            logger.warning(f"  消息{i+1}: 无法解析时间戳 {msg_time_raw}: {e}")
                
                if len(all_messages) > 3:
                    logger.info(f"调试：检查最后3条消息的时间戳（最新的消息）")
                    for i, msg in enumerate(all_messages[-3:]):
                        if hasattr(msg, "create_time"):
                            msg_time_raw = msg.create_time
                            try:
                                if isinstance(msg_time_raw, str):
                                    timestamp_val = int(msg_time_raw)
                                else:
                                    timestamp_val = int(msg_time_raw)

                                if timestamp_val > 10000000000:
                                    msg_time = datetime.fromtimestamp(timestamp_val / 1000)
                                    logger.info(
                                        f"  消息{len(all_messages)-2+i}: create_time={msg_time_raw} (毫秒) "
                                        f"→ {msg_time.strftime('%Y-%m-%d %H:%M:%S')}"
                                    )
                                else:
                                    msg_time = datetime.fromtimestamp(timestamp_val)
                                    logger.info(
                                        f"  消息{len(all_messages)-2+i}: create_time={msg_time_raw} (秒) "
                                        f"→ {msg_time.strftime('%Y-%m-%d %H:%M:%S')}"
                                    )
                            except Exception as e:
                                logger.warning(f"  消息{len(all_messages)-2+i}: 无法解析时间戳 {msg_time_raw}: {e}")

                logger.info(
                    f"过滤范围: {start_time.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"至 {end_time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                logger.info(
                    f"过滤范围(毫秒): {start_timestamp_ms} 至 {end_timestamp_ms}"
                )

            for msg in all_messages:
                if hasattr(msg, "create_time"):
                    # 处理不同格式的时间戳
                    try:
                        if isinstance(msg.create_time, str):
                            timestamp_val = int(msg.create_time)
                        else:
                            timestamp_val = int(msg.create_time)

                        # 自动检测时间戳格式并转换为毫秒
                        if timestamp_val > 10000000000:  # 已经是毫秒
                            msg_time_ms = timestamp_val
                        else:  # 是秒，转换为毫秒
                            msg_time_ms = timestamp_val * 1000

                        # 检查消息是否在时间范围内
                        if start_timestamp_ms <= msg_time_ms <= end_timestamp_ms:
                            filtered_messages.append(msg)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"无法解析消息时间戳: {msg.create_time}, 错误: {e}")
                        # 解析失败时也保留消息
                        filtered_messages.append(msg)
                else:
                    # 如果消息没有时间戳，也保留（避免丢失数据）
                    filtered_messages.append(msg)

            # 限制消息数量
            filtered_messages = filtered_messages[:max_messages]

            logger.info(
                f"获取了 {len(all_messages)} 条消息，过滤后保留 {len(filtered_messages)} 条"
            )

            # 如果过滤后没有消息，显示警告
            if all_messages and not filtered_messages:
                logger.warning("⚠️ 所有消息都被过滤掉了！")
                # API返回的消息是从旧到新排序，最后一条是最新的
                latest_msg_time = int(all_messages[-1].create_time)
                if latest_msg_time > 10000000000:  # 毫秒
                    latest_time_str = datetime.fromtimestamp(latest_msg_time / 1000).strftime('%Y-%m-%d %H:%M:%S')
                else:  # 秒
                    latest_time_str = datetime.fromtimestamp(latest_msg_time).strftime('%Y-%m-%d %H:%M:%S')
                
                logger.warning(f"API返回的最新消息时间: {latest_time_str}")
                logger.warning(f"查询的时间范围: {start_time.strftime('%Y-%m-%d %H:%M:%S')} 至 {end_time.strftime('%Y-%m-%d %H:%M:%S')}")


            return filtered_messages

        except Exception as e:
            logger.error(
                f"获取 chat_id={chat_id}, days={days} 的消息时发生意外错误: {e}",
                exc_info=True,
            )
            return []

    async def _fetch_with_pagination(
        self,
        chat_id: str,
        start_timestamp: int,
        end_timestamp: int,
        max_messages: int,
        container_id_type: str,
        page_size: int = 50,
    ) -> List:
        """
        支持分页的消息获取

        Args:
            chat_id: 聊天/群组ID
            start_timestamp: 开始时间（秒）
            end_timestamp: 结束时间（秒）
            max_messages: 最大消息数量
            container_id_type: 容器类型
            page_size: 每页消息数量

        Returns:
            消息对象列表
        """
        client = self._client_manager.get_client()
        all_messages = []
        page_token = None
        page_count = 0

        logger.debug(
            f"开始分页获取: start={start_timestamp}, "
            f"end={end_timestamp}, page_size={page_size}"
        )

        while len(all_messages) < max_messages:
            page_count += 1

            # 构建带分页令牌的请求
            req_builder = (
                ListMessageRequest.builder()
                .container_id(chat_id)
                .container_id_type(container_id_type)
                .page_size(page_size)
            )

            # 只有在提供时间戳时才添加时间过滤
            if start_timestamp is not None:
                req_builder = req_builder.start_time(int(start_timestamp))
            if end_timestamp is not None:
                req_builder = req_builder.end_time(int(end_timestamp))

            if page_token:
                req_builder = req_builder.page_token(page_token)

            request = req_builder.build()

            # 调用API
            logger.debug(
                f"获取第 {page_count} 页 (令牌: {page_token[:20] if page_token else '无'})"
            )

            try:
                response = await client.im.v1.message.alist(request)
            except AttributeError as e:
                error_msg = (
                    f"飞书SDK客户端结构错误（第 {page_count} 页）。"
                    f"客户端可能未正确初始化: {e}"
                )
                logger.error(error_msg, exc_info=True)
                raise RuntimeError(error_msg) from e
            except Exception as e:
                error_msg = (
                    f"API调用失败（第 {page_count} 页，chat_id={chat_id}）。"
                    f"可能是网络问题或API限流: {e}"
                )
                logger.error(error_msg, exc_info=True)
                raise RuntimeError(error_msg) from e

            # 检查API错误
            if not response.success():
                error_msg = (
                    f"飞书API返回错误（第 {page_count} 页）: "
                    f"code={response.code}, msg={response.msg}, "
                    f"chat_id={chat_id}, container_id_type={container_id_type}。"
                    f"请检查机器人是否有权限访问此群聊。"
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            # 从响应中提取消息
            try:
                batch = response.data.items or []
                logger.debug(f"第 {page_count} 页: 收到 {len(batch)} 条消息")

                # 调试：显示第一条和最后一条消息的时间
                if batch:
                    first_msg = batch[0]
                    last_msg = batch[-1]
                    if hasattr(first_msg, "create_time"):
                        try:
                            # 尝试解析时间戳
                            timestamp_val = int(first_msg.create_time)
                            # 如果时间戳看起来像毫秒（大于10位数），转换为秒
                            if timestamp_val > 10000000000:
                                first_time = datetime.fromtimestamp(timestamp_val / 1000)
                                last_time = datetime.fromtimestamp(int(last_msg.create_time) / 1000)
                            else:
                                first_time = datetime.fromtimestamp(timestamp_val)
                                last_time = datetime.fromtimestamp(int(last_msg.create_time))
                            logger.debug(
                                f"消息时间范围: {first_time.strftime('%Y-%m-%d %H:%M:%S')} "
                                f"至 {last_time.strftime('%Y-%m-%d %H:%M:%S')}"
                            )
                        except Exception as e:
                            logger.debug(f"无法解析消息时间: {e}")
            except AttributeError as e:
                logger.error(
                    f"从响应中提取消息失败（第 {page_count} 页）: {e}",
                    exc_info=True,
                )
                break

            if not batch:
                logger.debug("本页没有更多消息")
                break

            # 过滤并添加消息
            try:
                filtered_batch = self._filter_messages(batch)
                all_messages.extend(filtered_batch)
            except Exception as e:
                logger.error(
                    f"过滤消息时出错（第 {page_count} 页）: {e}。跳过此批次。",
                    exc_info=True,
                )
                # 继续下一页而不是完全失败
                continue

            logger.debug(
                f"第 {page_count} 页: 过滤后 {len(filtered_batch)} 条消息 "
                f"(总计: {len(all_messages)})"
            )

            # 检查是否还有更多页
            if not response.data.has_more:
                logger.debug("没有更多页面")
                break

            page_token = response.data.page_token

            # 如果达到限制则停止
            if len(all_messages) >= max_messages:
                logger.debug(f"已达到最大消息数限制: {max_messages}")
                break

        # 如果超出限制则裁剪
        if len(all_messages) > max_messages:
            all_messages = all_messages[:max_messages]
            logger.debug(f"裁剪至 {max_messages} 条消息")

        logger.info(
            f"分页完成: {page_count} 页, {len(all_messages)} 条消息"
        )
        return all_messages

    def _filter_messages(self, messages: List) -> List:
        """
        过滤消息（排除机器人自己的消息等）

        Args:
            messages: 原始消息对象列表

        Returns:
            过滤后的消息列表
        """
        filtered = []

        for msg in messages:
            try:
                # 保持时间戳原样，在使用时再判断格式
                if hasattr(msg, "create_time"):
                    try:
                        # 确保时间戳是整数格式
                        msg.create_time = int(msg.create_time)
                        logger.debug(
                            f"消息时间戳: {msg.create_time} "
                            f"(消息ID: {getattr(msg, 'message_id', '未知')})"
                        )
                    except (ValueError, TypeError) as e:
                        logger.warning(
                            f"无法解析消息 {getattr(msg, 'message_id', '未知')} 的时间戳: {e}。"
                            f"使用当前时间作为后备。"
                        )
                        msg.create_time = int(datetime.now().timestamp() * 1000)

                filtered.append(msg)

            except Exception as e:
                logger.error(
                    f"过滤时处理消息 {getattr(msg, 'message_id', '未知')} 出错: {e}。"
                    f"跳过此消息。",
                    exc_info=True,
                )
                continue

        return filtered
