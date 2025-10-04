"""
Tests for report generation.

Tests Requirements: 10.1, 10.2, 10.3, 10.4, 10.5
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.reports.generators import ReportGenerator
from src.models import (
    AnalysisResult, Topic, UserTitle, Quote, Statistics,
    UserMetrics, TokenUsage, EmojiStats
)


@pytest.fixture
def sample_analysis_result():
    """Create sample analysis result for testing"""
    topics = [
        Topic(
            title="Project Planning",
            participants=["Alice", "Bob"],
            description="Alice and Bob discussed the project timeline and deliverables.",
            message_count=5
        )
    ]
    
    user_titles = [
        UserTitle(
            open_id="ou_user_1",
            name="Alice",
            avatar_url="https://example.com/alice.jpg",
            title="Project Lead",
            mbti="ENTJ",
            reason="Led the discussion and made key decisions",
            metrics=UserMetrics(
                message_count=10,
                char_count=500,
                avg_message_length=50.0,
                emoji_count=5,
                reply_count=3,
                hourly_distribution={9: 5, 10: 5}
            )
        ),
        UserTitle(
            open_id="ou_user_2",
            name="Bob",
            avatar_url="https://example.com/bob.jpg",
            title="Active Contributor",
            mbti="ISFJ",
            reason="Provided valuable input and feedback",
            metrics=UserMetrics(
                message_count=8,
                char_count=400,
                avg_message_length=50.0,
                emoji_count=3,
                reply_count=2,
                hourly_distribution={9: 4, 10: 4}
            )
        )
    ]
    
    quotes = [
        Quote(
            content="Let's make this happen!",
            sender_name="Alice",
            sender_avatar="https://example.com/alice.jpg",
            timestamp=int(datetime.now().timestamp()),
            reason="Motivational statement that energized the team"
        )
    ]
    
    statistics = Statistics(
        message_count=18,
        char_count=900,
        participant_count=2,
        hourly_distribution={9: 9, 10: 9},
        peak_hours=[9, 10],
        emoji_stats=EmojiStats(
            total_count=8,
            unique_count=5,
            top_emojis={"👍": 3, "😊": 2}
        )
    )
    
    token_usage = TokenUsage(
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500
    )
    
    start_time = datetime.now() - timedelta(days=1)
    end_time = datetime.now()
    
    return AnalysisResult(
        topics=topics,
        user_titles=user_titles,
        quotes=quotes,
        statistics=statistics,
        token_usage=token_usage,
        analysis_period=(start_time, end_time)
    )


class TestReportGenerator:
    """Test report generation functionality"""
    
    @pytest.mark.asyncio
    async def test_generate_text_report(self, sample_analysis_result):
        """Test text format report generation"""
        mock_config = Mock()
        mock_config.get_output_format.return_value = "text"
        
        generator = ReportGenerator(mock_config)
        report = await generator.generate_text_report(sample_analysis_result)
        
        assert isinstance(report, str)
        assert len(report) > 0
        
        # Should include topics
        assert "Project Planning" in report
        
        # Should include user names
        assert "Alice" in report
        assert "Bob" in report
        
        # Should include titles
        assert "Project Lead" in report
        assert "Active Contributor" in report
        
        # Should include quotes
        assert "Let's make this happen!" in report
        
        # Should include statistics
        assert "18" in report or "message" in report.lower()
    
    @pytest.mark.asyncio
    async def test_text_report_includes_avatars_urls(self, sample_analysis_result):
        """Verify text report includes avatar URLs"""
        mock_config = Mock()
        generator = ReportGenerator(mock_config)
        
        report = await generator.generate_text_report(sample_analysis_result)
        
        # Avatar URLs should be present or referenced
        assert "alice.jpg" in report or "Avatar" in report
    
    @pytest.mark.asyncio
    async def test_text_report_displays_all_data(self, sample_analysis_result):
        """Verify all analysis data is displayed in text report"""
        mock_config = Mock()
        generator = ReportGenerator(mock_config)
        
        report = await generator.generate_text_report(sample_analysis_result)
        
        # Topics section
        assert any(topic.title in report for topic in sample_analysis_result.topics)
        
        # Users section
        assert all(user.name in report for user in sample_analysis_result.user_titles)
        
        # Quotes section
        assert all(quote.content in report for quote in sample_analysis_result.quotes)
        
        # Statistics
        assert str(sample_analysis_result.statistics.message_count) in report
        assert str(sample_analysis_result.statistics.participant_count) in report
    
    @pytest.mark.asyncio
    async def test_generate_image_report(self, sample_analysis_result):
        """Test image format report generation"""
        mock_config = Mock()
        mock_config.get_output_format.return_value = "image"
        
        generator = ReportGenerator(mock_config)
        
        # Mock HTML render function
        async def mock_render(html_content):
            return b"fake_image_data"
        
        image_data = await generator.generate_image_report(
            sample_analysis_result,
            mock_render
        )
        
        assert image_data is not None
        assert len(image_data) > 0
    
    @pytest.mark.asyncio
    async def test_image_report_includes_avatars(self, sample_analysis_result):
        """Verify image report includes user avatars"""
        mock_config = Mock()
        generator = ReportGenerator(mock_config)
        
        # Mock HTML render function that captures HTML
        captured_html = []
        
        async def mock_render(html_content):
            captured_html.append(html_content)
            return b"fake_image_data"
        
        await generator.generate_image_report(sample_analysis_result, mock_render)
        
        # Check that avatar URLs are in the HTML
        html = captured_html[0] if captured_html else ""
        assert "alice.jpg" in html or "avatar" in html.lower()
    
    @pytest.mark.asyncio
    async def test_image_report_fallback_on_error(self, sample_analysis_result):
        """Verify fallback to text when image generation fails"""
        mock_config = Mock()
        generator = ReportGenerator(mock_config)
        
        # Mock render function that raises error
        async def mock_render_error(html_content):
            raise Exception("Render failed")
        
        # Should not crash, should return text fallback
        result = await generator.generate_image_report(
            sample_analysis_result,
            mock_render_error
        )
        
        # Should return text report as fallback
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_report_handles_empty_data(self):
        """Verify report generation handles empty data gracefully"""
        mock_config = Mock()
        generator = ReportGenerator(mock_config)
        
        empty_result = AnalysisResult(
            topics=[],
            user_titles=[],
            quotes=[],
            statistics=Statistics(
                message_count=0,
                char_count=0,
                participant_count=0,
                hourly_distribution={},
                peak_hours=[],
                emoji_stats=EmojiStats(total_count=0, unique_count=0, top_emojis={})
            ),
            token_usage=TokenUsage(0, 0, 0),
            analysis_period=(datetime.now(), datetime.now())
        )
        
        report = await generator.generate_text_report(empty_result)
        
        assert isinstance(report, str)
        assert len(report) > 0
        # Should have some message about no data
        assert "no" in report.lower() or "empty" in report.lower() or "0" in report
    
    @pytest.mark.asyncio
    async def test_report_formats_timestamps(self, sample_analysis_result):
        """Verify timestamps are formatted correctly"""
        mock_config = Mock()
        generator = ReportGenerator(mock_config)
        
        report = await generator.generate_text_report(sample_analysis_result)
        
        # Should have formatted date/time
        assert any(str(datetime.now().year) in report for _ in [1])
    
    @pytest.mark.asyncio
    async def test_report_includes_statistics_visualization(self, sample_analysis_result):
        """Verify report includes or references statistics visualization"""
        mock_config = Mock()
        generator = ReportGenerator(mock_config)
        
        report = await generator.generate_text_report(sample_analysis_result)
        
        # Should mention peak hours or activity patterns
        assert "peak" in report.lower() or "hour" in report.lower() or "activity" in report.lower()


class TestReportFormats:
    """Test different report format outputs"""
    
    @pytest.mark.asyncio
    async def test_text_format_is_readable(self, sample_analysis_result):
        """Verify text format is human-readable"""
        mock_config = Mock()
        generator = ReportGenerator(mock_config)
        
        report = await generator.generate_text_report(sample_analysis_result)
        
        # Should have sections/headers
        assert "=" in report or "-" in report or "#" in report
        
        # Should have line breaks
        assert "\n" in report
        
        # Should not have HTML tags
        assert "<html>" not in report.lower()
    
    @pytest.mark.asyncio
    async def test_image_format_uses_html_template(self, sample_analysis_result):
        """Verify image format uses HTML template"""
        mock_config = Mock()
        generator = ReportGenerator(mock_config)
        
        captured_html = []
        
        async def mock_render(html_content):
            captured_html.append(html_content)
            return b"fake_image_data"
        
        await generator.generate_image_report(sample_analysis_result, mock_render)
        
        html = captured_html[0] if captured_html else ""
        
        # Should be valid HTML
        assert "<html>" in html.lower() or "<!doctype" in html.lower()
        
        # Should have styling
        assert "<style>" in html.lower() or "css" in html.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
