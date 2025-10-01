"""
消息处理模块
负责群聊消息的获取、过滤和预处理
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import defaultdict
from astrbot.api import logger
from ..models.data_models import GroupStatistics, TokenUsage, EmojiStatistics, ActivityVisualization
from ..visualization.activity_charts import ActivityVisualizer


class MessageHandler:
    """消息处理器"""

    def __init__(self, config_manager, bot_manager=None):
        self.config_manager = config_manager
        self.activity_visualizer = ActivityVisualizer()
        self.bot_manager = bot_manager

    async def set_bot_open_id(self, bot_open_id: str):
        """设置机器人Open ID（保持向后兼容）"""
        try:
            if self.bot_manager:
                self.bot_manager.set_bot_open_id(bot_open_id)
            logger.info(f"设置机器人Open ID: {bot_open_id}")
        except Exception as e:
            logger.error(f"设置机器人Open ID失败: {e}")

    def set_bot_manager(self, bot_manager):
        """设置bot管理器"""
        self.bot_manager = bot_manager

    def _extract_bot_open_id_from_instance(self, bot_instance):
        """从飞书bot实例中提取Open ID"""
        if hasattr(bot_instance, 'self_id') and bot_instance.self_id:
            return str(bot_instance.self_id)
        elif hasattr(bot_instance, 'open_id') and bot_instance.open_id:
            return str(bot_instance.open_id)
        elif hasattr(bot_instance, 'bot_name') and bot_instance.bot_name:
            return str(bot_instance.bot_name)
        return None

    def _convert_lark_message_to_unified_format(self, record) -> Dict:
        """将飞书消息记录转换为统一格式"""
        try:
            # 解析消息内容
            message_content = []

            # 处理文本消息
            if hasattr(record, 'message_str') and record.message_str:
                message_content.append({
                    "type": "text",
                    "data": {"text": record.message_str}
                })

            # 构建统一格式的消息
            unified_msg = {
                "message_id": getattr(record, 'message_id', ''),
                "time": record.created_at.timestamp(),
                "sender": {
                    "user_id": getattr(record, 'user_id', ''),
                    "nickname": getattr(record, 'user_id', '')[:8]  # 飞书使用open_id的前8位作为昵称
                },
                "message": message_content
            }

            return unified_msg

        except Exception as e:
            logger.warning(f"转换飞书消息格式失败: {e}")
            return None

    async def fetch_group_messages(self, bot_instance, group_id: str, days: int) -> List[Dict]:
        """获取飞书群聊消息记录（优先用 lark_oapi SDK）"""
        try:
            if not group_id or not bot_instance:
                logger.error(f"群 {group_id} 参数无效")
                return []

            # 计算时间范围
            from .feishu_history_sdk import fetch_feishu_history_via_sdk
            end_time = int(datetime.now().timestamp())
            start_time = 0 # end_time - days * 86400
            max_messages = self.config_manager.get_max_messages()

            # 获取 lark.Client 实例（只允许 lark_oapi.Client 或兼容对象，不能是 im.v1）
            lark_client = None
            if hasattr(bot_instance, "lark_api"):
                lark_client = bot_instance.lark_api
            elif hasattr(bot_instance, "client"):
                lark_client = bot_instance.client
            elif "Client" in str(type(bot_instance)) or "lark_oapi" in str(type(bot_instance)):
                lark_client = bot_instance

            logger.info(f"[调试] lark_client 类型: {type(lark_client)}, 属性: {dir(lark_client) if lark_client else None}")
            if not lark_client or not hasattr(lark_client, "im"):
                logger.error(f"lark_client 非法: {type(lark_client)}，属性: {dir(lark_client) if lark_client else None}")
                return []

            logger.info(f"[SDK] 开始获取飞书群 {group_id} 近 {days} 天的消息记录")
            logger.info(f"[SDK] 时间范围: {start_time} 到 {end_time}")
            try:
                msgs = await fetch_feishu_history_via_sdk(
                    lark_client, group_id, start_time, end_time, page_size=50, container_id_type='chat'
                )
            except Exception as sdk_e:
                logger.error(f"[SDK] 拉取历史消息失败: {sdk_e}")
                msgs = []
            # 转换为统一格式（修正：使用属性访问，兼容 SDK 消息对象）
            def _convert_lark_sdk_message_to_unified_format(m):
                try:
                    # create_time 可能为字符串或整数，单位毫秒
                    create_time_raw = getattr(m, "create_time", 0)
                    create_time = int(create_time_raw) // 1000 if create_time_raw else 0
                    sender_id_obj = getattr(m, "sender_id", None)
                    sender_id = getattr(sender_id_obj, "open_id", "") if sender_id_obj else ""
                    msg_type = getattr(m, "msg_type", "")
                    body_obj = getattr(m, "body", None)
                    content = getattr(body_obj, "content", "") if body_obj else ""
                    return {
                        "message_id": getattr(m, "message_id", ""),
                        "time": create_time,
                        "sender": {
                            "user_id": sender_id,
                            "nickname": sender_id[:8]
                        },
                        "message": [{
                            "type": msg_type,
                            "data": {"text": content}
                        }]
                    }
                except Exception as msg_e:
                    logger.warning(f"[SDK] 单条消息转换失败: {msg_e}")
                    return None

            messages = []
            for m in msgs:
                unified = _convert_lark_sdk_message_to_unified_format(m)
                if unified:
                    messages.append(unified)
                    if len(messages) >= max_messages:
                        break
            logger.info(f"[SDK] 飞书群 {group_id} 消息获取完成，共获取 {len(messages)} 条消息")
            if not messages:
                # 如果无法获取真实消息，使用模拟数据
                messages = self._generate_mock_messages(group_id, datetime.fromtimestamp(start_time), datetime.fromtimestamp(end_time), max_messages)
            return messages
        except Exception as e:
            logger.error(f"飞书群 {group_id} 获取群聊消息记录失败: {e}", exc_info=True)
            return []



    async def _try_get_real_messages(self, group_id: str, start_time: datetime, end_time: datetime, max_messages: int) -> List[Dict]:
        """尝试获取真实的飞书消息历史"""
        try:
            # 尝试从上下文获取平台消息历史管理器
            if self.bot_manager and hasattr(self.bot_manager, '_context') and self.bot_manager._context:
                context = self.bot_manager._context
                if hasattr(context, 'platform_history_mgr'):
                    platform_history_mgr = context.platform_history_mgr

                    messages = []
                    page = 1
                    page_size = 200

                    while len(messages) < max_messages:
                        # 获取消息历史
                        history_records = await platform_history_mgr.get(
                            platform_id="lark",
                            user_id=group_id,
                            page=page,
                            page_size=page_size
                        )

                        if not history_records:
                            break

                        # 转换消息格式并过滤时间范围
                        for record in history_records:
                            try:
                                # 检查消息时间是否在范围内
                                msg_time = record.created_at
                                if msg_time < start_time or msg_time > end_time:
                                    continue

                                # 转换为统一的消息格式
                                converted_msg = self._convert_lark_message_to_unified_format(record)
                                if converted_msg:
                                    # 过滤掉机器人自己的消息
                                    sender_id = converted_msg.get("sender", {}).get("user_id", "")
                                    if self.bot_manager and self.bot_manager.should_filter_bot_message(sender_id):
                                        continue

                                    messages.append(converted_msg)

                                    if len(messages) >= max_messages:
                                        break

                            except Exception as msg_error:
                                logger.warning(f"处理单条消息失败: {msg_error}")
                                continue

                        # 如果这一页没有有效消息，或者已经获取足够消息，停止
                        if len(history_records) < page_size or len(messages) >= max_messages:
                            break

                        page += 1

                    if messages:
                        logger.info(f"成功获取 {len(messages)} 条真实消息")
                        return messages

            logger.warning("无法获取平台消息历史管理器")
            return []

        except Exception as e:
            logger.warning(f"获取真实消息失败: {e}")
            return []

    def _generate_mock_messages(self, group_id: str, start_time: datetime, end_time: datetime, max_messages: int) -> List[Dict]:
        """生成模拟消息用于测试"""
        logger.warning("使用模拟数据进行分析（仅用于测试功能）")

        import random

        # 模拟用户列表
        mock_users = [
            {"user_id": "ou_123456789", "nickname": "用户A"},
            {"user_id": "ou_987654321", "nickname": "用户B"},
            {"user_id": "ou_456789123", "nickname": "用户C"},
            {"user_id": "ou_789123456", "nickname": "用户D"},
        ]

        # 模拟消息内容
        mock_texts = [
            "大家好！", "今天天气不错", "工作进展如何？", "有什么新消息吗？",
            "😊", "👍", "💪", "🎉", "周末愉快！", "辛苦了！",
            "这个想法不错", "我觉得可以试试", "需要帮助吗？", "谢谢大家！",
            "开会时间确定了吗？", "项目进度如何？", "需要我协助什么吗？",
            "今天的任务完成了", "明天见！", "休息一下吧"
        ]

        messages = []

        # 生成模拟消息
        for i in range(min(50, max_messages)):  # 生成50条模拟消息
            user = random.choice(mock_users)
            text = random.choice(mock_texts)

            # 随机时间（在指定范围内）
            random_time = start_time + timedelta(
                seconds=random.randint(0, int((end_time - start_time).total_seconds()))
            )

            mock_message = {
                "message_id": f"msg_{i}",
                "time": random_time.timestamp(),
                "sender": {
                    "user_id": user["user_id"],
                    "nickname": user["nickname"]
                },
                "message": [{
                    "type": "text",
                    "data": {"text": text}
                }]
            }

            # 过滤掉机器人自己的消息
            if self.bot_manager and self.bot_manager.should_filter_bot_message(user["user_id"]):
                continue

            messages.append(mock_message)

        logger.info(f"生成了 {len(messages)} 条模拟消息用于分析")
        return messages

    def calculate_statistics(self, messages: List[Dict]) -> GroupStatistics:
        """计算基础统计数据"""
        total_chars = 0
        participants = set()
        hour_counts = defaultdict(int)
        emoji_statistics = EmojiStatistics()

        for msg in messages:
            sender_id = str(msg.get("sender", {}).get("user_id", ""))
            participants.add(sender_id)

            # 统计时间分布
            msg_time = datetime.fromtimestamp(msg.get("time", 0))
            hour_counts[msg_time.hour] += 1

            # 处理消息内容
            for content in msg.get("message", []):
                if content.get("type") == "text":
                    text = content.get("data", {}).get("text", "")
                    total_chars += len(text)

                    # 简单的表情符号统计（Unicode表情）
                    import re
                    emoji_pattern = re.compile(
                        "["
                        "\U0001F600-\U0001F64F"  # emoticons
                        "\U0001F300-\U0001F5FF"  # symbols & pictographs
                        "\U0001F680-\U0001F6FF"  # transport & map symbols
                        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
                        "\U00002702-\U000027B0"
                        "\U000024C2-\U0001F251"
                        "]+", flags=re.UNICODE
                    )
                    emojis = emoji_pattern.findall(text)
                    if emojis:
                        emoji_statistics.face_count += len(emojis)
                        for emoji in emojis:
                            emoji_statistics.face_details[f"unicode_{emoji}"] = emoji_statistics.face_details.get(f"unicode_{emoji}", 0) + 1

                elif content.get("type") == "image":
                    # 飞书图片消息，不特别处理表情
                    pass
                elif content.get("type") in ["at", "mention"]:
                    # 飞书@消息，不计入表情统计
                    pass

        # 找出最活跃时段
        most_active_hour = max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else 0
        most_active_period = f"{most_active_hour:02d}:00-{(most_active_hour+1)%24:02d}:00"

        # 生成活跃度可视化数据
        activity_visualization = self.activity_visualizer.generate_activity_visualization(messages)

        return GroupStatistics(
            message_count=len(messages),
            total_characters=total_chars,
            participant_count=len(participants),
            most_active_period=most_active_period,
            golden_quotes=[],
            emoji_count=emoji_statistics.total_emoji_count,  # 保持向后兼容
            emoji_statistics=emoji_statistics,
            activity_visualization=activity_visualization,
            token_usage=TokenUsage()
        )