<div align="center">

# 飞书群日常分析插件


[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-ff69b4?style=for-the-badge)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

_✨ 一个基于AstrBot的智能群聊分析插件，能够生成精美的群聊日常分析报告。从 [QQ 总结插件](https://github.com/SXP-Simon/astrbot-qq-group-daily-analysis) 迁移飞书插件。[灵感来源](https://github.com/LSTM-Kirigaya/openmcp-tutorial/tree/main/qq-group-summary)。 ✨_

 </div>


## 功能特色

### 🎯 智能分析
- **统计数据**: 全面的群聊活跃度和参与度统计
- **话题分析**: 使用LLM智能提取群聊中的热门话题和讨论要点
- **用户画像**: 基于聊天行为分析用户特征，分配个性化称号
- **圣经识别**: 自动筛选出群聊中的精彩发言

### 📊 可视化报告
- **多种格式**: 支持图片和文本输出格式
    - **精美图片**: 生成美观的可视化报告
    - **PDF报告**: 生成专业的PDF格式分析报告（需配置）
- **详细数据**: 包含消息统计、时间分布、关键词、金句等

### 🛠️ 灵活配置
- **群组管理**: 支持指定特定群组启用功能
- **参数调节**: 可自定义分析天数、消息数量等参数
- **定时任务**: 支持设置每日自动分析时间
- **自定义LLM服务** ：支持自定义指定的LLM服务

### 配置选项

| 配置项 | 说明 | 备注 |
|--------|------|--------|
| 启用自动分析 | 启用定时触发自动分析功能需要按照插件配置里面的说明填写相关的需要的字段；简略说明：打开自动分析功能，在群聊列表中添加群号或者使用 `/分析设置 enable` 启用当前群聊 | 默认关闭 |
| PDF格式的报告 | 初次使用需要使用 `/安装PDF` 命令安装依赖，首次使用命令安装，最后出现提示告诉你需要重启生效，是对的，需要重启 astrbot，而不是热重载插件。 | 输出格式需要设置为 PDF |
| 自定义LLM服务 | 通过配置文件设置自定义LLM服务的API Key、Base URL和模型名称，注意配置中的文字说明， Base URL 需要填写完整，例如 `https://openrouter.ai/api/v1/chat/completions` | 留空则使用 Astrbot 指定的当前提供商 |

上述配置情况仅供参考，注意仔细阅读插件配置页面中各个字段的说明，以插件配置中的说明为准

## 使用方法

### 基础命令

#### 群分析
```
/群分析 [天数]
```
- 分析群聊近期活动
- 天数可选，默认为1天
- 例如：`/群分析 3` 分析最近3天的群聊

#### 分析设置
```
/分析设置 [操作]
```
- `enable`: 为当前群启用分析功能
- `disable`: 为当前群禁用分析功能  
- `status`: 查看当前群的启用状态
- 例如：`/分析设置 enable`

#### 设置格式
```
/设置格式 [格式]
```
- `text`: 文本格式
- `image`: 图片格式
- `pdf`: PDF格式
- 例如：`/设置格式 pdf`

#### 安装PDF
```
/安装PDF
```
- 安装依赖，首次使用命令安装，最后出现提示告诉你需要重启生效，是对的，需要重启 astrbot，而不是热重载插件。
- 例如：`/安装PDF`

## 飞书权限

飞书开放平台 -> 企业自建应用 -> 权限管理 -> 批量导入权限

希望满足权限最小化可以进行精简，下面是可以跑通的版本

```json
{
  "scopes": {
    "tenant": [
      "im:chat:read",
      "im:chat:readonly",
      "contact:contact.base:readonly",
      "contact:user.base:readonly",
      "im:message",
      "im:message.group_at_msg:readonly",
      "im:message.group_msg",
      "im:message.p2p_msg:readonly",
      "im:message:readonly",
      "im:message:send_as_bot",
      "im:resource"
    ],
    "user": []
  }
}
```