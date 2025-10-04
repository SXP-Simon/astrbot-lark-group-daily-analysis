"""
LLM调用辅助工具
提供统一的LLM调用接口，减少重复代码
"""

import asyncio
from astrbot.api import logger
from ..models import TokenUsage


class LLMHelper:
    """LLM调用辅助类"""

    def __init__(self, context, config_manager):
        """
        初始化LLM辅助类

        Args:
            context: AstrBot上下文
            config_manager: 配置管理器
        """
        self.context = context
        self.config_manager = config_manager

    async def call_llm_with_retry(
        self,
        prompt: str,
        max_tokens: int = 8000,
        temperature: float = 0.6,
        umo: str = None,
    ):
        """
        调用LLM提供者，带重试逻辑

        Args:
            prompt: 输入提示词
            max_tokens: 最大生成token数
            temperature: 采样温度
            umo: 唯一模型对象标识符

        Returns:
            LLM响应或失败时返回None
        """
        try:
            timeout = self.config_manager.get_llm_timeout()
            retries = self.config_manager.get_llm_retries()
            backoff = self.config_manager.get_llm_backoff()
        except Exception as e:
            logger.error(f"获取LLM配置时出错: {e}，使用默认值", exc_info=True)
            timeout = 30
            retries = 3
            backoff = 2

        # 获取自定义提供者参数
        try:
            custom_api_key = self.config_manager.get_custom_api_key()
            custom_api_base = self.config_manager.get_custom_api_base_url()
            custom_model = self.config_manager.get_custom_model_name()
        except Exception as e:
            logger.warning(f"获取自定义提供者配置时出错: {e}，使用默认提供者")
            custom_api_key = None
            custom_api_base = None
            custom_model = None

        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                if custom_api_key and custom_api_base and custom_model:
                    logger.info(
                        f"使用自定义LLM提供者 (尝试 {attempt}/{retries}): {custom_api_base} 模型={custom_model}"
                    )
                    try:
                        import aiohttp
                    except ImportError as e:
                        logger.error(f"自定义提供者需要aiohttp: {e}")
                        return None

                    try:
                        async with aiohttp.ClientSession() as session:
                            headers = {
                                "Authorization": f"Bearer {custom_api_key}",
                                "Content-Type": "application/json",
                            }
                            payload = {
                                "model": custom_model,
                                "messages": [{"role": "user", "content": prompt}],
                                "max_tokens": max_tokens,
                                "temperature": temperature,
                            }
                            aio_timeout = aiohttp.ClientTimeout(total=timeout)
                            async with session.post(
                                custom_api_base,
                                json=payload,
                                headers=headers,
                                timeout=aio_timeout,
                            ) as resp:
                                if resp.status != 200:
                                    error_text = await resp.text()
                                    error_msg = f"自定义LLM提供者请求失败: HTTP {resp.status}, 内容: {error_text[:200]}"
                                    logger.error(error_msg)
                                    raise Exception(error_msg)

                                try:
                                    response_json = await resp.json()
                                except Exception as json_err:
                                    error_text = await resp.text()
                                    logger.error(
                                        f"自定义LLM提供者响应JSON解析失败: {json_err}, "
                                        f"内容: {error_text[:200]}"
                                    )
                                    raise

                                # 兼容OpenAI格式
                                content = None
                                try:
                                    choices = response_json.get("choices")
                                    if (
                                        choices
                                        and isinstance(choices, list)
                                        and len(choices) > 0
                                    ):
                                        message = choices[0].get("message")
                                        if message and isinstance(message, dict):
                                            content = message.get("content")
                                    if content is None:
                                        logger.error(
                                            f"自定义LLM响应格式错误: {response_json}"
                                        )
                                        raise Exception("自定义LLM提供者响应格式无效")
                                except Exception as key_err:
                                    logger.error(
                                        f"自定义LLM响应结构解析失败: {key_err}, "
                                        f"响应: {str(response_json)[:200]}"
                                    )
                                    raise

                                # 创建兼容的响应对象
                                class CustomResponse:
                                    completion_text = content
                                    raw_completion = response_json

                                logger.info(f"自定义LLM请求成功，尝试 {attempt}")
                                return CustomResponse()
                    except aiohttp.ClientError as e:
                        logger.error(f"自定义LLM提供者网络错误: {e}")
                        raise
                else:
                    # 使用AstrBot提供者
                    try:
                        provider = self.context.get_using_provider(umo=umo)
                        if not provider:
                            error_msg = (
                                "LLM提供者为None。请在AstrBot设置中配置LLM提供者。"
                            )
                            logger.error(error_msg)
                            return None

                        logger.info(
                            f"使用LLM提供者 (尝试 {attempt}/{retries}): {provider}"
                        )
                        coro = provider.text_chat(
                            prompt=prompt,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        )
                        result = await asyncio.wait_for(coro, timeout=timeout)
                        logger.info(f"LLM请求成功，尝试 {attempt}")
                        return result
                    except AttributeError as e:
                        logger.error(
                            f"LLM提供者方法错误: {e}。提供者可能不支持text_chat。",
                            exc_info=True,
                        )
                        return None

            except asyncio.TimeoutError as e:
                last_exc = e
                logger.warning(
                    f"LLM请求超时，尝试 {attempt}/{retries} (超时={timeout}秒)。"
                    f"考虑在配置中增加超时时间。"
                )
            except Exception as e:
                last_exc = e
                logger.warning(
                    f"LLM请求失败，尝试 {attempt}/{retries}: {e}",
                    exc_info=(attempt == retries),
                )

            # 重试前等待
            if attempt < retries:
                wait_time = backoff * attempt
                logger.info(f"等待 {wait_time}秒 后重试...")
                await asyncio.sleep(wait_time)

        logger.error(
            f"所有 {retries} 次LLM重试尝试都失败了。最后错误: {last_exc}。"
            f"请检查您的LLM配置和网络连接。"
        )
        return None

    def extract_token_usage(self, response) -> TokenUsage:
        """
        从LLM响应中提取token使用量

        Args:
            response: LLM响应对象

        Returns:
            TokenUsage对象
        """
        token_usage = TokenUsage()
        try:
            if getattr(response, "raw_completion", None) is not None:
                usage = getattr(response.raw_completion, "usage", None)
                if usage:
                    token_usage.prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                    token_usage.completion_tokens = (
                        getattr(usage, "completion_tokens", 0) or 0
                    )
                    token_usage.total_tokens = getattr(usage, "total_tokens", 0) or 0
        except Exception as e:
            logger.debug(f"提取token使用量失败: {e}")

        return token_usage

    def extract_response_text(self, response) -> str:
        """
        从LLM响应中提取文本

        Args:
            response: LLM响应对象

        Returns:
            响应文本
        """
        if hasattr(response, "completion_text"):
            return response.completion_text
        else:
            return str(response)
