"""
User Info Cache

This module provides caching functionality for user information fetched from Lark API.
It minimizes API calls by caching user data with TTL-based expiration.
"""

import time
from typing import Dict, Optional
from astrbot.api import logger
from ..models import UserInfo
from .client import LarkClientManager


class UserInfoCache:
    """
    Caches user information fetched from Lark API.
    
    This class provides single and batch user fetching with in-memory caching
    to minimize API calls. Cache entries expire after a configurable TTL.
    """
    
    def __init__(self, client_manager: LarkClientManager, ttl: int = 3600, config_manager=None):
        """
        Initialize the user info cache.
        
        Args:
            client_manager: Lark client manager for API access
            ttl: Time-to-live for cache entries in seconds (default: 1 hour)
            config_manager: Configuration manager for user name mapping (optional)
        """
        self._client_manager = client_manager
        self._config_manager = config_manager
        self._ttl = ttl
        self._cache: Dict[str, tuple[UserInfo, float]] = {}  # open_id -> (UserInfo, timestamp)
        self._user_name_mapping = {}
        
        # Load user name mapping from config
        if config_manager:
            self._user_name_mapping = config_manager.get_user_name_mapping()
            if self._user_name_mapping:
                logger.info(f"Loaded {len(self._user_name_mapping)} user name mappings from config")
        
        logger.debug(f"UserInfoCache initialized with TTL={ttl}s")
    
    async def get_user_info(self, open_id: str) -> UserInfo:
        """
        Get user information, using cache if available.
        
        This method first checks the cache for valid (non-expired) user info.
        If not found or expired, it fetches from the Lark API and updates the cache.
        
        Args:
            open_id: User's open_id
            
        Returns:
            UserInfo object with user details (never None, uses fallback if needed)
        """
        try:
            # Validate input
            if not open_id:
                logger.warning("Empty open_id provided to get_user_info, using fallback")
                return self._create_fallback_user_info("unknown")
            
            # Check if user has a custom name mapping in config
            if open_id in self._user_name_mapping:
                custom_name = self._user_name_mapping[open_id]
                logger.debug(f"Using custom name mapping for {open_id[:12]}...: {custom_name}")
                user_info = UserInfo(
                    open_id=open_id,
                    name=custom_name,
                    avatar_url="",
                    en_name=""
                )
                # Cache the custom mapping
                self._cache[open_id] = (user_info, time.time())
                return user_info
            
            # Check cache first
            if open_id in self._cache:
                try:
                    user_info, timestamp = self._cache[open_id]
                    age = time.time() - timestamp
                    
                    if age < self._ttl:
                        logger.debug(f"Cache hit for user {open_id[:8]}... (age: {age:.1f}s)")
                        return user_info
                    else:
                        logger.debug(f"Cache expired for user {open_id[:8]}... (age: {age:.1f}s)")
                except Exception as e:
                    logger.warning(f"Error reading cache for user {open_id[:8]}...: {e}")
                    # Remove corrupted cache entry
                    del self._cache[open_id]
            else:
                logger.debug(f"Cache miss for user {open_id[:12]}...")
            
            # Fetch from API
            try:
                user_info = await self._fetch_user_from_api(open_id)
            except Exception as e:
                logger.error(
                    f"Failed to fetch user info for {open_id[:8]}... from API: {e}. "
                    f"Using fallback user info.",
                    exc_info=True
                )
                user_info = self._create_fallback_user_info(open_id)
            
            # Update cache
            try:
                self._cache[open_id] = (user_info, time.time())
            except Exception as e:
                logger.warning(f"Failed to update cache for user {open_id[:8]}...: {e}")
            
            return user_info
            
        except Exception as e:
            logger.error(
                f"Unexpected error in get_user_info for {open_id[:8] if open_id else 'unknown'}...: {e}",
                exc_info=True
            )
            return self._create_fallback_user_info(open_id if open_id else "unknown")
    
    async def batch_fetch_users(self, open_ids: list[str]) -> Dict[str, UserInfo]:
        """
        Batch fetch multiple users.
        
        This method fetches multiple users efficiently. It first checks the cache
        for each user, then fetches missing users from the API. The Lark SDK
        doesn't have a native batch API, so we fetch sequentially but efficiently.
        
        Args:
            open_ids: List of user open_ids to fetch
            
        Returns:
            Dictionary mapping open_id to UserInfo
        """
        result: Dict[str, UserInfo] = {}
        to_fetch: list[str] = []
        
        # Check cache for each user
        for open_id in open_ids:
            if open_id in self._cache:
                user_info, timestamp = self._cache[open_id]
                age = time.time() - timestamp
                
                if age < self._ttl:
                    result[open_id] = user_info
                    logger.debug(f"Batch cache hit for user {open_id[:8]}...")
                else:
                    to_fetch.append(open_id)
            else:
                to_fetch.append(open_id)
        
        # Fetch missing users
        if to_fetch:
            logger.debug(f"Batch fetching {len(to_fetch)} users from API")
            
            for open_id in to_fetch:
                try:
                    user_info = await self._fetch_user_from_api(open_id)
                    result[open_id] = user_info
                    # Cache is updated in _fetch_user_from_api
                except Exception as e:
                    logger.error(f"Error in batch fetch for {open_id[:8]}...: {e}")
                    # Use fallback
                    user_info = self._create_fallback_user_info(open_id)
                    result[open_id] = user_info
                    self._cache[open_id] = (user_info, time.time())
        
        logger.debug(f"Batch fetch complete: {len(result)} users retrieved")
        return result
    
    async def _fetch_user_from_api(self, open_id: str) -> UserInfo:
        """
        Fetch user information from Lark API.
        
        This method uses the Lark SDK to fetch user details. If the fetch fails,
        it returns a fallback UserInfo with a generic name.
        
        Args:
            open_id: User's open_id
            
        Returns:
            UserInfo object with user details or fallback data
        """
        try:
            # Get client
            try:
                client = self._client_manager.get_client()
            except Exception as e:
                logger.error(
                    f"Failed to get Lark client for fetching user {open_id[:8]}...: {e}",
                    exc_info=True
                )
                return self._create_fallback_user_info(open_id)
            
            # Import Lark SDK modules
            try:
                import lark_oapi as lark
            except ImportError as e:
                logger.error(
                    f"Failed to import Lark SDK modules: {e}. "
                    f"Please ensure lark_oapi is properly installed.",
                    exc_info=True
                )
                return self._create_fallback_user_info(open_id)
            
            # Try to get user info using im.v1.chat.members API (群成员信息)
            # This is more reliable than contact.v3.user API for group chat scenarios
            try:
                # First try: Use batch get chat members API
                from lark_oapi.api.im.v1 import BatchGetIdChatMembersRequest
                
                # Note: We need chat_id to use this API, but we don't have it here
                # So we'll fall back to using a simpler approach
                logger.debug(f"Attempting to fetch user info for {open_id[:8]}... using fallback method")
                
            except Exception as e:
                logger.debug(f"Batch API not available: {e}")
            
            # Validate open_id format before making API call
            # Valid user open_ids start with "ou_"
            if not open_id.startswith("ou_"):
                logger.warning(
                    f"Invalid open_id format: {open_id[:12]}... (should start with 'ou_'). "
                    f"This might be an app_id or other type of ID."
                )
                return self._create_fallback_user_info(open_id)
            
            # Use contact.v3.user API (requires contact:user.base:readonly permission)
            try:
                from lark_oapi.api.contact.v3 import GetUserRequest
                
                logger.debug(f"Fetching user info from Lark API for {open_id[:12]}...")
                
                request = GetUserRequest.builder() \
                    .user_id_type("open_id") \
                    .user_id(open_id) \
                    .build()
                
                response = client.contact.v3.user.get(request)
                
                logger.debug(f"API response for {open_id[:12]}...: success={response.success()}, code={response.code if hasattr(response, 'code') else 'N/A'}")
                
            except AttributeError as e:
                logger.error(
                    f"Lark client structure error when fetching user {open_id[:8]}...: {e}. "
                    f"The client may not be properly initialized.",
                    exc_info=True
                )
                return self._create_fallback_user_info(open_id)
            except Exception as e:
                logger.error(
                    f"API call failed when fetching user {open_id[:8]}...: {e}. "
                    f"This may be due to network issues or API rate limiting.",
                    exc_info=True
                )
                return self._create_fallback_user_info(open_id)
            
            # Check if request was successful
            if not response.success():
                error_code = response.code if hasattr(response, 'code') else 'unknown'
                error_msg = response.msg if hasattr(response, 'msg') else 'unknown error'
                
                # Provide specific guidance based on error code
                if error_code == 99992351:
                    logger.warning(
                        f"Lark API error for user {open_id[:12]}...: Invalid open_id or user not found. "
                        f"Error code: {error_code}, message: {error_msg}"
                    )
                elif error_code == 99991663:
                    logger.warning(
                        f"Lark API permission denied for user {open_id[:12]}...: "
                        f"Missing 'contact:user.base:readonly' permission. "
                        f"Please add this permission in Feishu Open Platform: https://open.feishu.cn/"
                    )
                else:
                    logger.warning(
                        f"Lark API returned error for user {open_id[:12]}...: "
                        f"code={error_code}, msg={error_msg}. "
                        f"The bot may not have permission to access user information."
                    )
                
                return self._create_fallback_user_info(open_id)
            
            # Extract user data
            try:
                user = response.data.user
                
                # Safely extract user fields
                name = user.name if hasattr(user, 'name') and user.name else f"User_{open_id[:8]}"
                
                # Extract avatar URL - try different sizes
                avatar_url = ""
                if hasattr(user, 'avatar') and user.avatar:
                    # Try different avatar sizes (prefer larger ones for better quality)
                    for size_attr in ['avatar_640', 'avatar_240', 'avatar_72']:
                        if hasattr(user.avatar, size_attr):
                            url = getattr(user.avatar, size_attr)
                            if url:
                                avatar_url = url
                                logger.debug(f"Found avatar URL ({size_attr}) for {open_id[:12]}...")
                                break
                    
                    if not avatar_url:
                        logger.debug(f"No avatar URL found for {open_id[:12]}..., available attrs: {[a for a in dir(user.avatar) if not a.startswith('_')]}")
                else:
                    logger.debug(f"User {open_id[:12]}... has no avatar attribute")
                
                en_name = user.en_name if hasattr(user, 'en_name') and user.en_name else ""
                
                user_info = UserInfo(
                    open_id=open_id,
                    name=name,
                    avatar_url=avatar_url,
                    en_name=en_name
                )
                
                logger.info(f"Fetched user info for {open_id[:12]}...: name={user_info.name}, has_avatar={bool(avatar_url)}")
                if avatar_url:
                    logger.debug(f"Avatar URL for {open_id[:12]}...: {avatar_url[:80]}...")
                return user_info
                
            except AttributeError as e:
                logger.error(
                    f"Failed to extract user data from response for {open_id[:8]}...: {e}",
                    exc_info=True
                )
                return self._create_fallback_user_info(open_id)
            
        except Exception as e:
            logger.error(
                f"Unexpected error fetching user info for {open_id[:8]}...: {e}",
                exc_info=True
            )
            return self._create_fallback_user_info(open_id)
    
    def clear_cache(self):
        """
        Clear the entire cache.
        
        This method removes all cached user information. Useful for testing
        or when you want to force fresh data from the API.
        """
        try:
            cache_size = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared: {cache_size} entries removed")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}", exc_info=True)
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics (size, expired count)
        """
        current_time = time.time()
        expired_count = sum(
            1 for _, timestamp in self._cache.values()
            if current_time - timestamp >= self._ttl
        )
        
        return {
            "size": len(self._cache),
            "expired": expired_count,
            "valid": len(self._cache) - expired_count
        }
    
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
        
        logger.debug(f"Created fallback user info for {open_id[:12]}...: {fallback_name}")
        
        return UserInfo(
            open_id=open_id,
            name=fallback_name,
            avatar_url="",
            en_name=""
        )
