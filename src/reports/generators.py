"""
报告生成器模块
负责生成各种格式的分析报告
"""

from datetime import datetime
from typing import Dict, Optional
from pathlib import Path
from astrbot.api import logger
from .templates import HTMLTemplates
from ..visualization.activity_charts import ActivityVisualizer
from ..models import AnalysisResult


class ReportGenerator:
    """报告生成器"""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.activity_visualizer = ActivityVisualizer()

    async def generate_image_report(
        self, analysis_result: AnalysisResult, group_id: str, html_render_func
    ) -> Optional[str]:
        """生成图片格式的分析报告

        Args:
            analysis_result: 分析结果对象
            group_id: 群组ID
            html_render_func: HTML渲染函数

        Returns:
            图片URL或None（如果生成失败）
        """
        if not analysis_result or not html_render_func:
            logger.error("生成图片报告失败：缺少必要参数")
            return None

        # 准备渲染数据
        render_payload = self._prepare_render_data(analysis_result)
        template = HTMLTemplates.get_image_template()

        # 图片生成选项
        image_options = {
            "full_page": True,
            "type": "jpeg",
            "quality": 95,
        }

        try:
            image_url = await html_render_func(
                template, render_payload, True, image_options
            )
            if image_url:
                logger.info(f"图片生成成功: {image_url}")
                return image_url
            else:
                # 尝试低质量选项
                logger.info("尝试使用低质量选项重新生成...")
                simple_options = {"full_page": True, "type": "jpeg", "quality": 70}
                image_url = await html_render_func(
                    template, render_payload, True, simple_options
                )
                if image_url:
                    logger.info(f"使用低质量选项生成成功: {image_url}")
                    return image_url
        except Exception as e:
            logger.error(f"生成图片报告失败: {e}")

        logger.warning("图片报告生成失败，建议使用文本格式")
        return None

    async def generate_pdf_report(
        self, analysis_result: AnalysisResult, group_id: str
    ) -> Optional[str]:
        """生成PDF格式的分析报告

        Args:
            analysis_result: 分析结果对象
            group_id: 群组ID

        Returns:
            PDF文件路径或None（如果生成失败）
        """
        if not self.config_manager.pyppeteer_available:
            logger.warning("pyppeteer不可用，无法生成PDF报告")
            return None

        # 确保输出目录存在
        output_dir = Path(self.config_manager.get_pdf_output_dir())
        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        current_date = datetime.now().strftime("%Y%m%d")
        filename = self.config_manager.get_pdf_filename_format().format(
            group_id=group_id, date=current_date
        )
        pdf_path = output_dir / filename

        # 准备渲染数据并生成HTML内容
        render_data = self._prepare_render_data(analysis_result)
        html_content = self._render_html_template(
            HTMLTemplates.get_pdf_template(), render_data, use_jinja_style=False
        )

        # 转换为PDF
        success = await self._html_to_pdf(html_content, str(pdf_path))
        if success:
            logger.info(f"PDF报告生成成功: {pdf_path}")
            return str(pdf_path.absolute())

        logger.warning("PDF转换失败")
        return None

    def generate_text_report(self, analysis_result: AnalysisResult) -> str:
        """生成文本格式的分析报告

        Args:
            analysis_result: 分析结果对象

        Returns:
            格式化的文本报告
        """
        if not analysis_result:
            return "❌ 报告生成失败：分析结果为空"

        try:
            # 安全提取数据
            stats = analysis_result.statistics
            topics = analysis_result.topics or []
            user_titles = analysis_result.user_titles or []
            quotes = analysis_result.quotes or []

            # 计算最活跃时段
            if stats and stats.peak_hours:
                peak_hours = stats.peak_hours[:3]
                most_active_period = "、".join(
                    [f"{h:02d}:00-{h + 1:02d}:00" for h in peak_hours]
                )
            else:
                most_active_period = "无数据"

            # 基础统计数据
            message_count = stats.message_count if stats else 0
            participant_count = stats.participant_count if stats else 0
            char_count = stats.char_count if stats else 0
            emoji_count = (
                stats.emoji_stats.total_count if stats and stats.emoji_stats else 0
            )

            report = f"""
🎯 群聊日常分析报告
📅 {datetime.now().strftime("%Y年%m月%d日")}

📊 基础统计
• 消息总数: {message_count}
• 参与人数: {participant_count}
• 总字符数: {char_count}
• 表情数量: {emoji_count}
• 最活跃时段: {most_active_period}

💬 热门话题
"""

            try:
                max_topics = self.config_manager.get_max_topics()
            except Exception as e:
                logger.warning(f"Error getting max_topics config: {e}")
                max_topics = 5

            if topics:
                for i, topic in enumerate(topics[:max_topics], 1):
                    try:
                        contributors_str = (
                            "、".join(topic.participants)
                            if topic.participants
                            else "未知"
                        )
                        title = topic.title if topic.title else "未命名话题"
                        description = (
                            topic.description if topic.description else "暂无描述"
                        )

                        report += f"{i}. {title}\n"
                        report += f"   参与者: {contributors_str}\n"
                        report += f"   {description}\n\n"
                    except AttributeError as e:
                        logger.warning(f"Error formatting topic {i}: {e}")
                        continue
            else:
                report += "暂无热门话题数据\n\n"

            report += "🏆 群友称号\n"

            try:
                max_user_titles = self.config_manager.get_max_user_titles()
            except Exception as e:
                logger.warning(f"Error getting max_user_titles config: {e}")
                max_user_titles = 10

            if user_titles:
                for title in user_titles[:max_user_titles]:
                    try:
                        name = title.name if title.name else "未知用户"
                        title_text = title.title if title.title else "无称号"
                        mbti = title.mbti if title.mbti else "N/A"
                        reason = title.reason if title.reason else "暂无说明"

                        report += f"• {name} - {title_text} ({mbti})\n"
                        report += f"  {reason}\n\n"
                    except AttributeError as e:
                        logger.warning(f"Error formatting user title: {e}")
                        continue
            else:
                report += "暂无群友称号数据\n\n"

            report += "💬 群圣经\n"

            try:
                max_golden_quotes = self.config_manager.get_max_golden_quotes()
            except Exception as e:
                logger.warning(f"Error getting max_golden_quotes config: {e}")
                max_golden_quotes = 5

            if quotes:
                for i, quote in enumerate(quotes[:max_golden_quotes], 1):
                    try:
                        content = quote.content if quote.content else "暂无内容"
                        sender_name = quote.sender_name if quote.sender_name else "未知"
                        reason = quote.reason if quote.reason else "暂无说明"

                        report += f'{i}. "{content}" —— {sender_name}\n'
                        report += f"   {reason}\n\n"
                    except AttributeError as e:
                        logger.warning(f"Error formatting quote {i}: {e}")
                        continue
            else:
                report += "暂无群圣经数据\n\n"

            logger.info("文本报告生成成功")
            return report

        except Exception as e:
            logger.error(f"生成文本报告时发生意外错误: {e}", exc_info=True)
            return f"""
❌ 报告生成失败

生成文本报告时发生错误。请检查日志获取详细信息。

错误信息: {str(e)}
"""

    def _prepare_render_data(self, analysis_result: AnalysisResult) -> Dict:
        """准备渲染数据，使用新的AnalysisResult模型，包含完整的fallback处理

        Args:
            analysis_result: AnalysisResult对象，包含完整的分析结果

        Returns:
            渲染数据字典，所有字段都有fallback值
        """
        try:
            stats = analysis_result.statistics
            topics = analysis_result.topics if analysis_result.topics else []
            user_titles = (
                analysis_result.user_titles if analysis_result.user_titles else []
            )
            quotes = analysis_result.quotes if analysis_result.quotes else []

            # 计算最活跃时段，带fallback
            peak_hours = stats.peak_hours[:3] if stats.peak_hours else []
            most_active_period = (
                "、".join([f"{h:02d}:00-{h + 1:02d}:00" for h in peak_hours])
                if peak_hours
                else "无数据"
            )

            # 构建话题HTML，带fallback
            topics_html = ""
            max_topics = self.config_manager.get_max_topics()
            if topics:
                for i, topic in enumerate(topics[:max_topics], 1):
                    # 安全获取参与者列表
                    contributors = topic.participants if topic.participants else []
                    contributors_str = (
                        "、".join(contributors) if contributors else "未知"
                    )

                    # 安全获取话题信息
                    title = topic.title if topic.title else "未命名话题"
                    description = topic.description if topic.description else "暂无描述"

                    topics_html += f"""
                    <div class="topic-item">
                        <div class="topic-header">
                            <span class="topic-number">{i}</span>
                            <span class="topic-title">{title}</span>
                        </div>
                        <div class="topic-contributors">参与者: {contributors_str}</div>
                        <div class="topic-detail">{description}</div>
                    </div>
                    """
            else:
                # 无话题时的fallback
                topics_html = """
                <div class="topic-item">
                    <div class="topic-detail" style="text-align: center; color: #999;">暂无热门话题数据</div>
                </div>
                """

            # 构建用户称号HTML（包含头像），带fallback
            titles_html = ""
            max_user_titles = self.config_manager.get_max_user_titles()
            if user_titles:
                for title in user_titles[:max_user_titles]:
                    # Debug: log avatar URL
                    logger.debug(
                        f"Generating report for user {title.name}: avatar_url={title.avatar_url[:80] if title.avatar_url else 'None'}..."
                    )

                    # 安全获取头像，带fallback
                    if title.avatar_url:
                        try:
                            avatar_html = f'<img src="{title.avatar_url}" class="user-avatar" alt="头像" onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'flex\';">'
                            avatar_html += '<div class="user-avatar-placeholder" style="display:none;">👤</div>'
                        except Exception:
                            avatar_html = (
                                '<div class="user-avatar-placeholder">👤</div>'
                            )
                    else:
                        avatar_html = '<div class="user-avatar-placeholder">👤</div>'

                    # 安全获取用户信息
                    user_name = title.name if title.name else "未知用户"
                    user_title = title.title if title.title else "无称号"
                    user_mbti = title.mbti if title.mbti else "N/A"
                    user_reason = title.reason if title.reason else "暂无说明"

                    titles_html += f"""
                    <div class="user-title">
                        <div class="user-info">
                            {avatar_html}
                            <div class="user-details">
                                <div class="user-name">{user_name}</div>
                                <div class="user-badges">
                                    <div class="user-title-badge">{user_title}</div>
                                    <div class="user-mbti">{user_mbti}</div>
                                </div>
                            </div>
                        </div>
                        <div class="user-reason">{user_reason}</div>
                    </div>
                    """
            else:
                # 无用户称号时的fallback
                titles_html = """
                <div class="user-title">
                    <div class="user-info" style="width: 100%; text-align: center; color: #999;">暂无群友称号数据</div>
                </div>
                """

            # 构建金句HTML，带fallback
            quotes_html = ""
            max_golden_quotes = self.config_manager.get_max_golden_quotes()
            if quotes:
                for quote in quotes[:max_golden_quotes]:
                    # 安全获取金句信息
                    content = quote.content if quote.content else "暂无内容"
                    sender_name = quote.sender_name if quote.sender_name else "未知"
                    reason = quote.reason if quote.reason else "暂无说明"

                    quotes_html += f"""
                    <div class="quote-item">
                        <div class="quote-content">"{content}"</div>
                        <div class="quote-author">—— {sender_name}</div>
                        <div class="quote-reason">{reason}</div>
                    </div>
                    """
            else:
                # 无金句时的fallback
                quotes_html = """
                <div class="quote-item">
                    <div class="quote-content" style="text-align: center; color: #999;">暂无群圣经数据</div>
                </div>
                """

            # 生成活跃度可视化HTML，带fallback
            try:
                hourly_chart_html = self.activity_visualizer.generate_hourly_chart_html(
                    stats.hourly_distribution if stats.hourly_distribution else {}
                )
            except Exception as e:
                logger.warning(f"生成活跃度图表失败: {e}")
                hourly_chart_html = '<div style="text-align: center; color: #999;">活跃度数据不可用</div>'

            # 返回扁平化的渲染数据，所有字段都有安全的fallback
            return {
                "current_date": datetime.now().strftime("%Y年%m月%d日"),
                "current_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message_count": stats.message_count if stats.message_count else 0,
                "participant_count": stats.participant_count
                if stats.participant_count
                else 0,
                "total_characters": stats.char_count if stats.char_count else 0,
                "emoji_count": stats.emoji_stats.total_count
                if stats.emoji_stats and stats.emoji_stats.total_count
                else 0,
                "most_active_period": most_active_period,
                "topics_html": topics_html,
                "titles_html": titles_html,
                "quotes_html": quotes_html,
                "hourly_chart_html": hourly_chart_html,
                "total_tokens": analysis_result.token_usage.total_tokens
                if analysis_result.token_usage
                else 0,
                "prompt_tokens": analysis_result.token_usage.prompt_tokens
                if analysis_result.token_usage
                else 0,
                "completion_tokens": analysis_result.token_usage.completion_tokens
                if analysis_result.token_usage
                else 0,
            }
        except Exception as e:
            logger.error(f"准备渲染数据时发生错误: {e}", exc_info=True)
            # 返回最小可用的fallback数据
            return {
                "current_date": datetime.now().strftime("%Y年%m月%d日"),
                "current_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message_count": 0,
                "participant_count": 0,
                "total_characters": 0,
                "emoji_count": 0,
                "most_active_period": "无数据",
                "topics_html": '<div style="text-align: center; color: #999;">数据加载失败</div>',
                "titles_html": '<div style="text-align: center; color: #999;">数据加载失败</div>',
                "quotes_html": '<div style="text-align: center; color: #999;">数据加载失败</div>',
                "hourly_chart_html": '<div style="text-align: center; color: #999;">数据加载失败</div>',
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            }

    def _render_html_template(
        self, template: str, data: Dict, use_jinja_style: bool = False
    ) -> str:
        """HTML模板渲染，支持两种占位符格式

        Args:
            template: HTML模板字符串
            data: 渲染数据
            use_jinja_style: 是否使用Jinja2风格的{{ }}占位符，否则使用{}占位符
        """
        result = template

        # 调试：记录渲染数据
        logger.info(
            f"渲染数据键: {list(data.keys())}, 使用Jinja风格: {use_jinja_style}"
        )

        for key, value in data.items():
            if use_jinja_style:
                # 图片模板使用{{ }}占位符
                placeholder = f"{{{{ {key} }}}}"
            else:
                # PDF模板使用{}占位符
                placeholder = f"{{{key}}}"

            # 调试：记录替换过程
            if placeholder in result:
                logger.debug(f"替换 {placeholder} -> {str(value)[:100]}...")
            result = result.replace(placeholder, str(value))

        # 检查是否还有未替换的占位符
        import re

        if use_jinja_style:
            remaining_placeholders = re.findall(r"\{\{[^}]+\}\}", result)
        else:
            remaining_placeholders = re.findall(r"\{[^}]+\}", result)

        if remaining_placeholders:
            logger.warning(f"未替换的占位符: {remaining_placeholders[:10]}")

        return result

    async def _html_to_pdf(self, html_content: str, output_path: str) -> bool:
        """将 HTML 内容转换为 PDF 文件"""
        try:
            # Validate inputs
            if not html_content:
                logger.error("Cannot convert to PDF: html_content is empty")
                return False

            if not output_path:
                logger.error("Cannot convert to PDF: output_path is empty")
                return False

            # 确保 pyppeteer 可用
            if not self.config_manager.pyppeteer_available:
                logger.error(
                    "pyppeteer 不可用，无法生成 PDF。请安装 pyppeteer: pip install pyppeteer"
                )
                return False

            # 动态导入 pyppeteer
            try:
                from pyppeteer import launch
                import sys
                import os
            except ImportError as e:
                logger.error(
                    f"Failed to import pyppeteer: {e}. Please install it: pip install pyppeteer"
                )
                return False

            # 尝试启动浏览器，如果 Chromium 不存在会自动下载
            logger.info("启动浏览器进行 PDF 转换")

            # 配置浏览器启动参数，避免 Chromium 下载问题
            launch_options = {
                "headless": True,
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-first-run",
                    "--disable-extensions",
                    "--disable-default-apps",
                ],
            }

            # 如果是 Windows 系统，尝试使用系统 Chrome
            if sys.platform.startswith("win"):
                # 常见的 Chrome 安装路径
                chrome_paths = [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    r"C:\Users\{}\AppData\Local\Google\Chrome\Application\chrome.exe".format(
                        os.environ.get("USERNAME", "")
                    ),
                ]

                for chrome_path in chrome_paths:
                    if Path(chrome_path).exists():
                        launch_options["executablePath"] = chrome_path
                        logger.info(f"使用系统 Chrome: {chrome_path}")
                        break

            # Launch browser
            try:
                browser = await launch(**launch_options)
            except Exception as e:
                logger.error(
                    f"Failed to launch browser: {e}. Please check if Chrome/Chromium is installed.",
                    exc_info=True,
                )
                return False

            try:
                page = await browser.newPage()

                # 设置页面内容 (pyppeteer 1.0.2 版本的 API)
                try:
                    await page.setContent(html_content)
                except Exception as e:
                    logger.error(f"Failed to set page content: {e}", exc_info=True)
                    await browser.close()
                    return False

                # 等待页面加载完成
                try:
                    await page.waitForSelector("body", {"timeout": 10000})
                except Exception as e:
                    # 如果等待失败，继续执行（可能页面已经加载完成）
                    logger.debug(f"Wait for selector timed out (may be OK): {e}")

                # 导出 PDF
                try:
                    await page.pdf(
                        {
                            "path": output_path,
                            "format": "A4",
                            "printBackground": True,
                            "margin": {
                                "top": "10mm",
                                "right": "10mm",
                                "bottom": "10mm",
                                "left": "10mm",
                            },
                            "scale": 0.8,
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to generate PDF: {e}", exc_info=True)
                    await browser.close()
                    return False

                await browser.close()
                logger.info(f"PDF 生成成功: {output_path}")
                return True

            except Exception as e:
                logger.error(f"Error during PDF generation: {e}", exc_info=True)
                try:
                    await browser.close()
                except Exception:
                    pass
                return False

        except Exception as e:
            error_msg = str(e)
            if (
                "Chromium downloadable not found" in error_msg
                or "Chromium" in error_msg
            ):
                logger.error(
                    "Chromium 下载失败或未找到。建议：\n"
                    "1. 安装 pyppeteer2: pip install pyppeteer2\n"
                    "2. 或安装系统 Chrome 浏览器\n"
                    "3. 或使用文本/图片格式作为替代"
                )
            elif "No usable sandbox" in error_msg or "sandbox" in error_msg.lower():
                logger.error(
                    "沙盒权限问题。已尝试禁用沙盒，但仍然失败。\n"
                    "建议使用文本或图片格式作为替代。"
                )
            else:
                logger.error(f"HTML 转 PDF 失败: {e}", exc_info=True)
            return False
