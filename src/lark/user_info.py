"""
用户信息缓存

本模块为从飞书API获取的用户信息提供缓存功能
通过基于TTL的过期缓存用户数据来最小化API调用
"""

import time
from typing import Dict
from astrbot.api import logger
from ..models import UserInfo
from .client import LarkClientManager


class UserInfoCache:
    """
    缓存从飞书API获取的用户信息

    此类提供单个和批量用户获取功能，使用内存缓存来最小化API调用
    缓存条目在可配置的TTL后过期
    """

    def __init__(
        self, client_manager: LarkClientManager, ttl: int = 3600, config_manager=None
    ):
        """
        初始化用户信息缓存

        Args:
            client_manager: 用于API访问的飞书客户端管理器
            ttl: 缓存条目的生存时间（秒，默认：1小时）
            config_manager: 用于用户名映射的配置管理器（可选）
        """
        self._client_manager = client_manager
        self._config_manager = config_manager
        self._ttl = ttl
        self._cache: Dict[
            str, tuple[UserInfo, float]
        ] = {}  # open_id -> (UserInfo, timestamp)
        self._user_name_mapping = {}

        # 从配置加载用户名映射
        if config_manager:
            self._user_name_mapping = config_manager.get_user_name_mapping()
            if self._user_name_mapping:
                logger.info(f"从配置加载了{len(self._user_name_mapping)}个用户名映射")

        logger.debug(f"用户信息缓存初始化完成，TTL={ttl}秒")

    async def get_user_info(self, open_id: str) -> UserInfo:
        """
        获取用户信息，如果缓存可用则使用缓存。

        此方法首先检查缓存中是否有有效的（未过期的）用户信息。
        如果未找到或已过期，则从飞书API获取并更新缓存。

        参数:
            open_id: 用户的open_id

        返回:
            包含用户详情的UserInfo对象（永远不会为None，需要时使用降级数据）
        """
        try:
            # 验证输入
            if not open_id:
                logger.warning(
                    "提供给get_user_info的open_id为空，使用降级方案"
                )
                return self._create_fallback_user_info("unknown")

            # 检查用户是否在配置中有自定义名称映射
            if open_id in self._user_name_mapping:
                custom_name = self._user_name_mapping[open_id]
                logger.debug(
                    f"为 {open_id[:12]}... 使用自定义名称映射: {custom_name}"
                )
                user_info = UserInfo(
                    open_id=open_id, name=custom_name, avatar_url="", en_name=""
                )
                # 缓存自定义映射
                self._cache[open_id] = (user_info, time.time())
                return user_info

            # 首先检查缓存
            if open_id in self._cache:
                try:
                    user_info, timestamp = self._cache[open_id]
                    age = time.time() - timestamp

                    if age < self._ttl:
                        logger.debug(
                            f"用户 {open_id[:8]}... 缓存命中 (年龄: {age:.1f}秒)"
                        )
                        return user_info
                    else:
                        logger.debug(
                            f"用户 {open_id[:8]}... 缓存过期 (年龄: {age:.1f}秒)"
                        )
                except Exception as e:
                    logger.warning(
                        f"读取用户 {open_id[:8]}... 缓存时出错: {e}"
                    )
                    # 移除损坏的缓存条目
                    del self._cache[open_id]
            else:
                logger.debug(f"用户 {open_id[:12]}... 缓存未命中")

            # 从API获取
            try:
                user_info = await self._fetch_user_from_api(open_id)
            except Exception as e:
                logger.error(
                    f"从API获取用户 {open_id[:8]}... 的信息失败: {e}。 "
                    f"使用降级用户信息。",
                    exc_info=True,
                )
                user_info = self._create_fallback_user_info(open_id)

            # 更新缓存
            try:
                self._cache[open_id] = (user_info, time.time())
            except Exception as e:
                logger.warning(f"更新用户 {open_id[:8]}... 缓存失败: {e}")

            return user_info

        except Exception as e:
            logger.error(
                f"在get_user_info中获取 {open_id[:8] if open_id else 'unknown'}... 的信息时发生意外错误: {e}",
                exc_info=True,
            )
            return self._create_fallback_user_info(open_id if open_id else "unknown")

    async def fetch_chat_members(self, chat_id: str, fetch_avatars: bool = False) -> Dict[str, UserInfo]:
        """
        获取群聊中所有成员的信息（推荐用于群聊场景）
        
        使用群成员列表API，可以获取群内所有成员，不受通讯录可见范围限制。
        需要权限：im:chat:read 或 im:chat:readonly
        
        Args:
            chat_id: 群聊ID
            fetch_avatars: 是否额外获取头像（需要 contact:user.base:readonly 权限）
            
        Returns:
            字典，映射 open_id 到 UserInfo
        """
        result: Dict[str, UserInfo] = {}
        
        try:
            client = self._client_manager.get_client()
            
            # 导入群成员API
            try:
                from lark_oapi.api.im.v1 import GetChatMembersRequest
            except ImportError as e:
                logger.error(f"无法导入飞书SDK模块: {e}")
                return result
            
            # 分页获取群成员
            page_token = None
            page_count = 0
            
            logger.info(f"开始获取群 {chat_id} 的成员列表")
            
            while True:
                page_count += 1
                
                # 构建请求
                req_builder = (
                    GetChatMembersRequest.builder()
                    .chat_id(chat_id)
                    .member_id_type("open_id")
                    .page_size(100)
                )
                
                if page_token:
                    req_builder = req_builder.page_token(page_token)
                
                request = req_builder.build()
                
                # 调用API
                logger.debug(f"获取群成员列表（第{page_count}页）")
                
                try:
                    # 使用同步调用（飞书SDK的chat_members.get是同步方法）
                    response = client.im.v1.chat_members.get(request)
                except Exception as e:
                    logger.error(f"获取群成员列表API调用失败: {e}", exc_info=True)
                    break
                
                if not response.success():
                    error_code = response.code if hasattr(response, 'code') else 'unknown'
                    error_msg = response.msg if hasattr(response, 'msg') else 'unknown'
                    
                    logger.error(
                        f"获取群成员列表失败: code={error_code}, msg={error_msg}"
                    )
                    
                    # 提供具体的错误提示
                    if error_code == 99991663:
                        logger.error("权限不足！需要 im:chat:read 或 im:chat:readonly 权限")
                    elif error_code == 230002:
                        logger.error("群聊不存在或机器人不在群内")
                    
                    break
                
                # 提取成员信息
                try:
                    members = response.data.items or []
                    logger.info(f"第{page_count}页: 获取到{len(members)}个成员")
                    
                    for member in members:
                        try:
                            # ListMember对象有以下字段：
                            # - member_id_type: str
                            # - member_id: str (这是我们需要的 open_id)
                            # - name: str (用户名称)
                            # - tenant_key: str
                            
                            open_id = member.member_id if member.member_id else None
                            if not open_id:
                                logger.debug(f"成员没有member_id")
                                continue
                            
                            # 提取成员名称
                            name = member.name if member.name else None
                            
                            if not name:
                                # 使用降级名称
                                name = f"用户{open_id[3:8]}" if open_id.startswith("ou_") else f"用户{open_id[:5]}"
                            
                            # 创建UserInfo
                            user_info = UserInfo(
                                open_id=open_id,
                                name=name,
                                avatar_url="",  # 群成员API不返回头像
                                en_name=""
                            )
                            
                            result[open_id] = user_info
                            # 更新缓存
                            self._cache[open_id] = (user_info, time.time())
                            
                            # 调试：显示前几个成员
                            if len(result) <= 3:
                                logger.debug(f"成员 {len(result)}: {name} ({open_id[:12]}...)")
                            
                        except Exception as e:
                            logger.warning(f"处理群成员信息时出错: {e}", exc_info=True)
                            continue
                    
                except Exception as e:
                    logger.error(f"提取成员信息失败: {e}", exc_info=True)
                    break
                
                # 检查是否还有更多页
                if not hasattr(response.data, 'has_more') or not response.data.has_more:
                    logger.debug("没有更多页面")
                    break
                
                page_token = response.data.page_token
            
            logger.info(f"从群 {chat_id} 获取了 {len(result)} 个成员信息")
            
            # 尝试批量获取头像（使用通讯录API）
            if result:
                logger.info(f"尝试获取 {len(result)} 个成员的头像...")
                avatar_count = 0
                failed_users = []
                
                for open_id, user_info in result.items():
                    try:
                        # 尝试从通讯录API获取详细信息（包含头像）
                        detailed_info = await self._fetch_user_from_api(open_id)
                        if detailed_info and detailed_info.avatar_url:
                            # 更新头像信息
                            user_info.avatar_url = detailed_info.avatar_url
                            # 更新缓存
                            self._cache[open_id] = (user_info, time.time())
                            avatar_count += 1
                        else:
                            failed_users.append(open_id)
                    except Exception as e:
                        # 获取头像失败，记录但不影响整体流程
                        logger.debug(f"获取用户 {open_id[:12]}... 的头像失败: {e}")
                        failed_users.append(open_id)
                        continue
                
                if avatar_count > 0:
                    logger.info(f"✅ 成功获取 {avatar_count}/{len(result)} 个成员的头像")
                else:
                    logger.info(f"⚠️ 未能获取成员头像（用户不在应用可见范围内）")
                
                # 为没有头像的用户生成默认头像
                if failed_users:
                    logger.info(f"为 {len(failed_users)} 个用户使用默认头像方案")
                    for open_id in failed_users:
                        if open_id in result:
                            user_info = result[open_id]
                            # 使用用户名首字母生成头像URL（使用第三方服务）
                            user_info.avatar_url = self._generate_avatar_url(user_info.name, open_id)
                            # 更新缓存
                            self._cache[open_id] = (user_info, time.time())
            
            return result
            
        except Exception as e:
            logger.error(f"获取群成员列表时出错: {e}", exc_info=True)
            return result

    async def batch_fetch_users(self, open_ids: list[str]) -> Dict[str, UserInfo]:
        """
        批量获取多个用户。

        此方法高效地获取多个用户。它首先检查每个用户的缓存，
        然后从API获取缺失的用户。飞书SDK没有原生的批量API，
        所以我们按顺序但高效地获取。

        参数:
            open_ids: 要获取的用户open_id列表

        返回:
            将open_id映射到UserInfo的字典
        """
        result: Dict[str, UserInfo] = {}
        to_fetch: list[str] = []

        # 检查每个用户的缓存
        for open_id in open_ids:
            if open_id in self._cache:
                user_info, timestamp = self._cache[open_id]
                age = time.time() - timestamp

                if age < self._ttl:
                    result[open_id] = user_info
                    logger.debug(f"批量缓存命中用户 {open_id[:8]}...")
                else:
                    to_fetch.append(open_id)
            else:
                to_fetch.append(open_id)

        # 获取缺失的用户
        if to_fetch:
            logger.debug(f"从API批量获取 {len(to_fetch)} 个用户")

            for open_id in to_fetch:
                try:
                    user_info = await self._fetch_user_from_api(open_id)
                    result[open_id] = user_info
                    # 缓存在_fetch_user_from_api中更新
                except Exception as e:
                    logger.error(f"批量获取 {open_id[:8]}... 时出错: {e}")
                    # 使用降级方案
                    user_info = self._create_fallback_user_info(open_id)
                    result[open_id] = user_info
                    self._cache[open_id] = (user_info, time.time())

        logger.debug(f"批量获取完成: 获取了 {len(result)} 个用户")
        return result

    async def get_user_info_from_message(self, message) -> UserInfo:
        """
        从消息对象中提取用户信息（推荐方法）
        
        飞书消息对象中包含发送者的基本信息，直接使用可以避免额外的API调用
        和权限限制问题
        
        Args:
            message: 飞书消息对象
            
        Returns:
            UserInfo对象
        """
        try:
            if not hasattr(message, 'sender'):
                logger.warning("消息对象没有sender字段")
                return self._create_fallback_user_info("unknown")
            
            sender = message.sender
            open_id = sender.id if hasattr(sender, 'id') else "unknown"
            
            # 检查缓存
            if open_id in self._cache:
                user_info, timestamp = self._cache[open_id]
                if time.time() - timestamp < self._ttl:
                    return user_info
            
            # 从sender中提取信息
            # 飞书消息的sender包含：id, id_type, sender_type, tenant_key
            # 但不包含用户名，所以还是需要调用API或使用降级方案
            
            # 尝试从配置的映射中获取
            if open_id in self._user_name_mapping:
                custom_name = self._user_name_mapping[open_id]
                user_info = UserInfo(
                    open_id=open_id, name=custom_name, avatar_url="", en_name=""
                )
                self._cache[open_id] = (user_info, time.time())
                return user_info
            
            # 尝试从API获取
            try:
                user_info = await self._fetch_user_from_api(open_id)
                return user_info
            except Exception as e:
                logger.debug(f"从API获取用户信息失败: {e}，使用降级方案")
                return self._create_fallback_user_info(open_id)
                
        except Exception as e:
            logger.error(f"从消息中提取用户信息失败: {e}", exc_info=True)
            return self._create_fallback_user_info("unknown")

    async def _fetch_user_from_api(self, open_id: str) -> UserInfo:
        """
        从飞书API获取用户信息
        
        注意：此方法需要 contact:user.base:readonly 权限，
        且只能获取应用可见范围内的用户信息。
        如果获取失败，会返回降级的UserInfo。

        Args:
            open_id: 用户的open_id

        Returns:
            UserInfo对象（包含用户详情或降级数据）
        """
        try:
            # 获取客户端
            try:
                client = self._client_manager.get_client()
            except Exception as e:
                logger.error(
                    f"获取用于获取用户 {open_id[:8]}... 的飞书客户端失败: {e}",
                    exc_info=True,
                )
                return self._create_fallback_user_info(open_id)

            # 导入飞书SDK模块
            try:
                import lark_oapi  # noqa: F401
            except ImportError as e:
                logger.error(
                    f"导入飞书SDK模块失败: {e}。 "
                    f"请确保已正确安装 lark_oapi。",
                    exc_info=True,
                )
                return self._create_fallback_user_info(open_id)

            # 尝试使用 im.v1.chat.members API 获取用户信息（群成员信息）
            # 对于群聊场景，这比 contact.v3.user API 更可靠
            try:
                # 第一次尝试：使用批量获取群成员API

                # 注意：我们需要 chat_id 才能使用此API，但在这里我们没有
                # 所以我们将回退到使用更简单的方法
                logger.debug(
                    f"尝试使用降级方法获取 {open_id[:8]}... 的用户信息"
                )

            except Exception as e:
                logger.debug(f"批量API不可用: {e}")

            # 在进行API调用前验证open_id格式
            # 有效的用户open_id以"ou_"开头
            if not open_id.startswith("ou_"):
                logger.warning(
                    f"无效的open_id格式: {open_id[:12]}... (应以'ou_'开头)。 "
                    f"这可能是app_id或其他类型的ID。"
                )
                return self._create_fallback_user_info(open_id)

            # 使用 contact.v3.user API（需要 contact:user.base:readonly 权限）
            try:
                from lark_oapi.api.contact.v3 import GetUserRequest

                logger.debug(f"从飞书API获取 {open_id[:12]}... 的用户信息")

                request = (
                    GetUserRequest.builder()
                    .user_id_type("open_id")
                    .user_id(open_id)
                    .build()
                )

                response = client.contact.v3.user.get(request)

                logger.debug(
                    f"{open_id[:12]}... 的API响应: 成功={response.success()}, 代码={response.code if hasattr(response, 'code') else 'N/A'}"
                )

            except AttributeError as e:
                logger.error(
                    f"获取用户 {open_id[:8]}... 时飞书客户端结构错误: {e}。 "
                    f"客户端可能未正确初始化。",
                    exc_info=True,
                )
                return self._create_fallback_user_info(open_id)
            except Exception as e:
                logger.error(
                    f"获取用户 {open_id[:8]}... 时API调用失败: {e}。 "
                    f"这可能是由于网络问题或API限流。",
                    exc_info=True,
                )
                return self._create_fallback_user_info(open_id)

            # 检查请求是否成功
            if not response.success():
                error_code = response.code if hasattr(response, "code") else "unknown"
                error_msg = (
                    response.msg if hasattr(response, "msg") else "unknown error"
                )

                # 根据错误代码提供具体指导
                if error_code == 99992351:
                    logger.warning(
                        f"飞书API错误，用户 {open_id[:12]}...: 无效的open_id或用户未找到。 "
                        f"错误代码: {error_code}, 消息: {error_msg}"
                    )
                elif error_code == 99991663:
                    logger.warning(
                        f"飞书API权限被拒绝，用户 {open_id[:12]}...: "
                        f"缺少 'contact:user.base:readonly' 权限。 "
                        f"请在飞书开放平台添加此权限: https://open.feishu.cn/"
                    )
                else:
                    logger.warning(
                        f"飞书API返回用户 {open_id[:12]}... 错误: "
                        f"代码={error_code}, 消息={error_msg}。 "
                        f"机器人可能没有权限访问用户信息。"
                    )

                return self._create_fallback_user_info(open_id)

            # 提取用户数据
            try:
                user = response.data.user

                # 安全地提取用户字段
                name = (
                    user.name
                    if hasattr(user, "name") and user.name
                    else f"用户{open_id[:8]}"
                )

                # 提取头像URL - 尝试不同尺寸
                avatar_url = ""
                if hasattr(user, "avatar") and user.avatar:
                    # 尝试不同的头像尺寸（优先选择更大的尺寸以获得更好的质量）
                    for size_attr in ["avatar_640", "avatar_240", "avatar_72"]:
                        if hasattr(user.avatar, size_attr):
                            url = getattr(user.avatar, size_attr)
                            if url:
                                avatar_url = url
                                logger.debug(
                                    f"找到 {open_id[:12]}... 的头像URL ({size_attr})"
                                )
                                break

                    if not avatar_url:
                        logger.debug(
                            f"未找到 {open_id[:12]}... 的头像URL, 可用属性: {[a for a in dir(user.avatar) if not a.startswith('_')]}"
                        )
                else:
                    logger.debug(f"用户 {open_id[:12]}... 没有头像属性")

                en_name = (
                    user.en_name if hasattr(user, "en_name") and user.en_name else ""
                )

                user_info = UserInfo(
                    open_id=open_id, name=name, avatar_url=avatar_url, en_name=en_name
                )

                logger.info(
                    f"获取了 {open_id[:12]}... 的用户信息: 名称={user_info.name}, 有头像={bool(avatar_url)}"
                )
                if avatar_url:
                    logger.debug(
                        f"{open_id[:12]}... 的头像URL: {avatar_url[:80]}..."
                    )
                return user_info

            except AttributeError as e:
                logger.error(
                    f"从响应中提取 {open_id[:8]}... 的用户数据失败: {e}",
                    exc_info=True,
                )
                return self._create_fallback_user_info(open_id)

        except Exception as e:
            logger.error(
                f"获取 {open_id[:8]}... 的用户信息时发生意外错误: {e}",
                exc_info=True,
            )
            return self._create_fallback_user_info(open_id)

    def clear_cache(self):
        """
        清空整个缓存。

        此方法移除所有缓存的用户信息。适用于测试
        或当你想要强制从API获取新数据时。
        """
        try:
            cache_size = len(self._cache)
            self._cache.clear()
            logger.info(f"缓存已清空: 移除了 {cache_size} 个条目")
        except Exception as e:
            logger.error(f"清空缓存时出错: {e}", exc_info=True)

    def get_cache_stats(self) -> Dict[str, int]:
        """
        获取缓存统计信息。

        返回:
            包含缓存统计信息的字典（大小、过期数量）
        """
        current_time = time.time()
        expired_count = sum(
            1
            for _, timestamp in self._cache.values()
            if current_time - timestamp >= self._ttl
        )

        return {
            "size": len(self._cache),
            "expired": expired_count,
            "valid": len(self._cache) - expired_count,
        }

    def _generate_avatar_url(self, name: str, open_id: str) -> str:
        """
        为用户生成默认头像URL
        
        使用第三方头像生成服务，基于用户名生成个性化头像
        
        Args:
            name: 用户名
            open_id: 用户ID
            
        Returns:
            头像URL
        """
        try:
            # 方案1: 使用 UI Avatars 服务（免费、稳定）
            # 提取用户名的首字母或前两个字符
            import urllib.parse
            
            # 获取用户名的前2个字符作为头像文字
            if len(name) >= 2:
                avatar_text = name[:2]
            elif len(name) == 1:
                avatar_text = name
            else:
                # 使用open_id的一部分
                avatar_text = open_id[3:5].upper() if len(open_id) > 5 else "U"
            
            # URL编码
            encoded_text = urllib.parse.quote(avatar_text)
            
            # 生成颜色（基于open_id的哈希值）
            color_hash = hash(open_id) % 16777215  # 0xFFFFFF
            bg_color = f"{color_hash:06x}"
            
            # UI Avatars API: https://ui-avatars.com/
            avatar_url = f"https://ui-avatars.com/api/?name={encoded_text}&background={bg_color}&color=fff&size=128&bold=true"
            
            logger.debug(f"为用户 {name} 生成默认头像: {avatar_url}")
            return avatar_url
            
        except Exception as e:
            logger.warning(f"生成默认头像失败: {e}")
            # 返回一个简单的默认头像
            return "https://ui-avatars.com/api/?name=U&background=random&size=128"
    
    def _create_fallback_user_info(self, open_id: str) -> UserInfo:
        """
        创建降级用户信息（当 API 获取失败时使用）

        Args:
            open_id: 用户的 open_id

        Returns:
            包含降级数据的 UserInfo 对象
        """
        # 创建更友好的降级显示名称
        # open_id 格式通常为 "ou_xxxxxxxxxxxx"
        if open_id and len(open_id) >= 8:
            if open_id.startswith("ou_"):
                # 提取 ou_ 后面的前5个字符，更简洁
                # 例如 "ou_b492d551235..." -> "用户b492d"
                fallback_name = f"用户{open_id[3:8]}"
            else:
                # 其他格式的 ID
                fallback_name = f"用户{open_id[:5]}"
        else:
            fallback_name = "未知用户"

        logger.debug(
            f"为 {open_id[:12]}... 创建降级用户信息: {fallback_name}"
        )

        return UserInfo(open_id=open_id, name=fallback_name, avatar_url="", en_name="")
