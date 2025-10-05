"""
消息解析器

将飞书SDK消息对象解析为统一的ParsedMessage格式，处理文本、富文本和系统消息等各种消息类型
"""

import json
from typing import Optional
from astrbot.api import logger
from ..models import ParsedMessage
from .user_info import UserInfoCache


class MessageParser:
    """
    将飞书SDK消息对象解析为统一的ParsedMessage格式

    处理不同的飞书消息类型，提取发送者详情、内容和元数据
    """

    def __init__(self, user_info_cache: UserInfoCache):
        """
        初始化消息解析器

        Args:
            user_info_cache: 用于获取用户信息的缓存
        """
        self._user_info_cache = user_info_cache
        logger.debug("消息解析器已初始化")

    async def parse_message(self, msg) -> Optional[ParsedMessage]:
        """
        将单个飞书消息解析为ParsedMessage格式

        提取发送者的open_id，获取用户信息，根据类型解析消息内容，返回统一的ParsedMessage对象

        Args:
            msg: 飞书SDK消息对象

        Returns:
            ParsedMessage对象，解析失败时返回None
        """
        message_id = "unknown"
        try:
            # 提前提取消息ID以便更好地进行错误日志记录
            message_id = getattr(msg, "message_id", "unknown")

            # 验证消息对象
            if not msg:
                logger.warning("收到空消息对象，跳过")
                return None

            # 提取发送者open_id - 处理不同的消息结构
            sender_id = None

            # 尝试不同的发送者结构
            if hasattr(msg, "sender"):
                sender = msg.sender
                if isinstance(sender, str):
                    sender_id = sender
                elif hasattr(sender, "id") and isinstance(sender.id, str):
                    sender_id = sender.id
                elif hasattr(sender, "id") and hasattr(sender.id, "open_id"):
                    sender_id = sender.id.open_id
                elif hasattr(sender, "open_id"):
                    sender_id = sender.open_id

            # 尝试直接从sender_id字段获取
            if not sender_id and hasattr(msg, "sender_id"):
                sender_id_obj = msg.sender_id
                if isinstance(sender_id_obj, str):
                    sender_id = sender_id_obj
                elif hasattr(sender_id_obj, "open_id"):
                    sender_id = sender_id_obj.open_id
                elif hasattr(sender_id_obj, "id"):
                    sender_id = sender_id_obj.id

            if not sender_id:
                logger.warning(f"消息 {message_id} 没有发送者open_id，跳过")
                return None

            # 跳过机器人消息（app_id以'cli_'开头，用户open_id以'ou_'开头）
            if sender_id.startswith("cli_"):
                logger.debug(f"消息 {message_id} 是机器人消息，跳过")
                return None

            # 从缓存中获取发送者信息
            try:
                user_info = await self._user_info_cache.get_user_info(sender_id)
            except Exception as e:
                logger.error(
                    f"在消息 {message_id} 中获取发送者 {sender_id[:8]}... 的用户信息失败: {e}。 "
                    f"使用降级用户信息。",
                    exc_info=True,
                )
                # 创建降级用户信息
                from ..models import UserInfo

                user_info = UserInfo(
                    open_id=sender_id,
                    name=f"用户_{sender_id[:8]}",
                    avatar_url="",
                    en_name="",
                )

            # 提取消息类型
            message_type = msg.msg_type if hasattr(msg, "msg_type") else "unknown"

            # 提取时间戳（如需要，将毫秒转换为秒）
            try:
                timestamp = int(msg.create_time) if hasattr(msg, "create_time") else 0
                # 飞书时间戳为毫秒格式，需要转换为秒
                if timestamp > 10**12:  # 如果时间戳是毫秒格式
                    timestamp = timestamp // 1000
                elif timestamp == 0:
                    logger.warning(
                        f"消息 {message_id} 没有时间戳，使用当前时间"
                    )
                    from datetime import datetime

                    timestamp = int(datetime.now().timestamp())
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"解析消息 {message_id} 的时间戳失败: {e}。使用当前时间。"
                )
                from datetime import datetime

                timestamp = int(datetime.now().timestamp())

            # 获取原始内容
            try:
                raw_content = (
                    msg.body.content
                    if msg.body and hasattr(msg.body, "content")
                    else ""
                )
            except AttributeError as e:
                logger.warning(f"消息 {message_id} 的body结构无效: {e}")
                raw_content = ""

            # 根据消息类型解析内容
            content = None
            try:
                if message_type == "text":
                    content = self.parse_text_content(raw_content)
                elif message_type == "post":
                    content = self.parse_post_content(raw_content)
                elif message_type in ["system", "share_chat"]:
                    content = self.parse_system_message(msg)
                else:
                    logger.warning(
                        f"消息 {message_id} 的消息类型 '{message_type}' 不受支持。 "
                        f"支持的类型: text, post, system, share_chat"
                    )
                    return None
            except Exception as e:
                logger.error(
                    f"解析消息 {message_id} 的内容时出错 (类型: {message_type}): {e}",
                    exc_info=True,
                )
                return None

            # 如果内容解析失败，跳过此消息
            if content is None or content.strip() == "":
                logger.warning(
                    f"解析消息 {message_id} 的内容失败或内容为空 (类型: {message_type})"
                )
                return None

            # 创建ParsedMessage
            try:
                parsed_message = ParsedMessage(
                    message_id=message_id,
                    timestamp=timestamp,
                    sender_id=sender_id,
                    sender_name=user_info.name,
                    sender_avatar=user_info.avatar_url,
                    content=content,
                    message_type=message_type,
                    raw_content=raw_content,
                )
            except Exception as e:
                logger.error(
                    f"为消息 {message_id} 创建ParsedMessage对象失败: {e}",
                    exc_info=True,
                )
                return None

            logger.debug(
                f"解析了来自 {user_info.name} 的消息 {message_id[:8]}... (头像: {bool(user_info.avatar_url)}): "
                f"{content[:50]}..."
                if len(content) > 50
                else content
            )

            return parsed_message

        except Exception as e:
            logger.error(
                f"解析消息 {message_id} 时发生意外错误: {e}", exc_info=True
            )
            return None

    def parse_text_content(self, content: str) -> Optional[str]:
        """
        解析文本消息内容。

        飞书中的文本消息内容以JSON格式存储：
        {"text": "实际消息文本"}

        参数:
            content: 消息body中的原始内容字符串

        返回:
            提取的文本，解析失败时返回None
        """
        try:
            if not content:
                logger.debug("提供给parse_text_content的内容为空")
                return None

            # 内容为JSON编码
            try:
                content_json = json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"将文本内容解析为JSON失败: {e}。 "
                    f"尝试使用原始内容作为后备方案。"
                )
                # 尝试返回原始内容作为后备方案
                return content if content.strip() else None

            # 提取文本字段
            if not isinstance(content_json, dict):
                logger.warning(
                    f"文本内容JSON不是字典: {type(content_json)}"
                )
                return str(content_json) if content_json else None

            text = content_json.get("text", "")

            if not text:
                logger.debug("内容JSON中的文本字段为空")
                return None

            return text

        except Exception as e:
            logger.error(f"解析文本内容时发生意外错误: {e}", exc_info=True)
            # 最后手段：如果原始内容不为空则返回原始内容
            return content if content and content.strip() else None

    def parse_post_content(self, content: str) -> Optional[str]:
        """
        解析富文本消息内容。

        飞书中的富文本消息具有标题和内容块的结构化格式：
        {
            "zh_cn": {
                "title": "帖子标题",
                "content": [
                    [{"tag": "text", "text": "第1行"}],
                    [{"tag": "text", "text": "第2行"}, {"tag": "a", "text": "链接"}]
                ]
            }
        }

        此方法提取所有文本元素并将它们连接起来。

        参数:
            content: 消息body中的原始内容字符串

        返回:
            来自帖子的连接文本，解析失败时返回None
        """
        try:
            if not content:
                logger.debug("提供给parse_post_content的内容为空")
                return None

            # 内容为JSON编码
            try:
                content_json = json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning(f"将富文本内容解析为JSON失败: {e}")
                return None

            if not isinstance(content_json, dict):
                logger.warning(
                    f"富文本内容JSON不是字典: {type(content_json)}"
                )
                return None

            # 富文本消息可以有多种语言版本
            # 尝试获取第一个可用的语言版本
            post_data = None
            for lang_key in ["zh_cn", "zh_tw", "en_us", "ja_jp"]:
                if lang_key in content_json:
                    post_data = content_json[lang_key]
                    logger.debug(f"在语言 {lang_key} 中找到富文本数据")
                    break

            # 如果没有已知的语言键，尝试获取第一个键
            if not post_data and content_json:
                try:
                    first_key = next(iter(content_json))
                    post_data = content_json[first_key]
                    logger.debug(f"使用第一个可用的语言键: {first_key}")
                except StopIteration:
                    logger.warning("内容JSON为空")
                    return None

            if not post_data:
                logger.warning(
                    f"内容中未找到富文本数据。可用键: {list(content_json.keys()) if content_json else 'None'}"
                )
                logger.debug(f"内容JSON结构: {content_json}")
                return None

            if not isinstance(post_data, dict):
                logger.warning(f"富文本数据不是字典: {type(post_data)}")
                return None

            # 提取标题
            title = post_data.get("title", "")

            # 提取内容块
            content_blocks = post_data.get("content", [])

            if not isinstance(content_blocks, list):
                logger.warning(f"内容块不是列表: {type(content_blocks)}")
                content_blocks = []

            # 收集所有文本元素
            text_parts = []

            if title:
                text_parts.append(str(title))

            for block_idx, block in enumerate(content_blocks):
                try:
                    if not isinstance(block, list):
                        logger.debug(f"块 {block_idx} 不是列表，跳过")
                        continue

                    # 每个块是一个元素列表（一行）
                    line_parts = []
                    for element_idx, element in enumerate(block):
                        try:
                            if isinstance(element, dict):
                                # 从各种元素类型中提取文本
                                if "text" in element:
                                    line_parts.append(str(element["text"]))
                                elif "content" in element:
                                    line_parts.append(str(element["content"]))
                        except Exception as e:
                            logger.debug(
                                f"处理块 {block_idx} 中的元素 {element_idx} 时出错: {e}"
                            )
                            continue

                    if line_parts:
                        text_parts.append(" ".join(line_parts))

                except Exception as e:
                    logger.debug(f"处理块 {block_idx} 时出错: {e}")
                    continue

            # 用换行符连接所有部分
            result = "\n".join(text_parts)
            return result if result.strip() else None

        except Exception as e:
            logger.error(f"解析富文本内容时发生意外错误: {e}", exc_info=True)
            return None

    def parse_system_message(self, msg) -> Optional[str]:
        """
        解析系统消息内容。

        飞书中的系统消息使用带有变量的模板，例如：
        - "{from_user} 邀请了 {to_chatters}"
        - "{from_user} 移除了 {to_chatters}"
        - "{from_user} 将群名称改为 {new_name}"

        此方法提取模板并用实际值替换变量，
        生成人类可读的消息。

        参数:
            msg: 飞书SDK消息对象

        返回:
            人类可读的系统消息文本，解析失败时返回None
        """
        try:
            # 系统消息可能有不同的结构
            # 尝试从body获取内容
            if not msg.body or not hasattr(msg.body, "content"):
                logger.warning(f"系统消息 {msg.message_id} 没有body内容")
                return None

            raw_content = msg.body.content

            # 尝试解析为JSON
            try:
                content_json = json.loads(raw_content)

                # 查找模板字段
                template = content_json.get("template", "")

                if not template:
                    # 一些系统消息可能有"text"字段
                    text = content_json.get("text", "")
                    if text:
                        return text

                    # 如果没有模板或文本，返回通用消息
                    logger.warning(
                        f"系统消息 {msg.message_id} 没有模板或文本"
                    )
                    return "[系统消息]"

                # 从消息中提取变量
                # 变量通常格式为 {variable_name}
                # 我们将尝试用实际值替换它们（如果可用）

                # 系统消息中的常见变量
                variables = content_json.get("variables", {})

                # 在模板中替换变量
                result = template
                for var_name, var_value in variables.items():
                    placeholder = f"{{{var_name}}}"
                    result = result.replace(placeholder, str(var_value))

                # 如果还有未替换的变量，尝试从消息上下文中提取用户名
                if "{from_user}" in result or "{to_chatters}" in result:
                    # 尝试获取发送者名称
                    if msg.sender and msg.sender.id:
                        sender_id = msg.sender.id.open_id
                        # 这里不能await，所以我们使用占位符
                        result = result.replace("{from_user}", f"用户{sender_id[:8]}")

                    # 对于to_chatters，我们使用通用占位符
                    result = result.replace("{to_chatters}", "一些用户")

                return result

            except json.JSONDecodeError:
                # 如果不是JSON，返回原始内容
                logger.warning(f"系统消息 {msg.message_id} 内容不是JSON")
                return raw_content if raw_content else "[系统消息]"

        except Exception as e:
            logger.error(
                f"解析系统消息 {getattr(msg, 'message_id', 'unknown')} 时出错: {e}"
            )
            return None
