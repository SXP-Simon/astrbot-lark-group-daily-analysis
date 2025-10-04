"""
群聊活跃度可视化模块
生成活跃度图表的HTML可视化
"""

from typing import Dict


class ActivityVisualizer:
    """活跃度可视化器"""
    
    def __init__(self):
        pass
    

    
    def generate_hourly_chart_html(self, hourly_distribution: Dict[int, int]) -> str:
        """生成每小时活动分布的HTML图表
        
        Args:
            hourly_distribution: 小时分布字典，键为小时(0-23)，值为消息数
            
        Returns:
            HTML字符串，包含24小时活跃度条形图
        """
        html_parts = []
        max_activity = max(hourly_distribution.values()) if hourly_distribution else 1
        threshold_percentage = 20  # 数值显示阈值（当条形图宽度小于此值时，数值显示在外部）
        
        for hour in range(24):
            count = hourly_distribution.get(hour, 0)
            percentage = (count / max_activity) * 100 if max_activity > 0 else 0
            
            if count > 0 and percentage >= threshold_percentage:
                # 活动数较多，数值显示在条形图内部
                html_segment = f"""
                <div class="hour-bar-container">
                    <span class="hour-label">{hour:02d}:00</span>
                    <div class="bar-wrapper">
                        <div class="bar" style="width: {percentage}%;">
                            <span class="hourly-value-inside">({count})</span>
                        </div>
                    </div>
                </div>
                """
            elif count > 0:
                # 活动数较少，数值显示在条形图外部
                html_segment = f"""
                <div class="hour-bar-container">
                    <span class="hour-label">{hour:02d}:00</span>
                    <div class="bar-wrapper">
                        <div class="bar" style="width: {percentage}%;"></div>
                        <span class="hourly-value-outside">({count})</span>
                    </div>
                </div>
                """
            else:
                # 无活动
                html_segment = f"""
                <div class="hour-bar-container">
                    <span class="hour-label">{hour:02d}:00</span>
                    <div class="bar-wrapper">
                        <span class="hourly-value-outside">({count})</span>
                    </div>
                </div>
                """
            html_parts.append(html_segment)
        
        return "".join(html_parts)


