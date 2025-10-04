# Technical Stack

## Framework & Platform

- **Base Framework**: AstrBot plugin system
- **Platform**: QQ group chat (via aiocqhttp adapter)
- **Language**: Python 3.x (async/await)

## Core Dependencies

- **astrbot**: Plugin framework and API
- **pyppeteer==1.0.2**: PDF generation (optional, headless browser control)
- **aiohttp**: Async HTTP client for API calls and avatar fetching

## Architecture

Modular architecture with clear separation of concerns:

- `src/core/`: Configuration management, bot instance management, message handling
- `src/analysis/`: LLM-based analysis (topics, user titles, golden quotes) and statistics
- `src/models/`: Data models (Pydantic-style dataclasses)
- `src/reports/`: Report generation (HTML templates, image/PDF/text formats)
- `src/scheduler/`: Automatic scheduled analysis with APScheduler
- `src/utils/`: Helper utilities (PDF installation, message analysis)
- `src/visualization/`: Activity charts and visualizations

## Key Technologies

- **Async Programming**: Extensive use of asyncio for non-blocking operations
- **LLM Integration**: Supports custom OpenAI-compatible API providers with retry/timeout logic
- **HTML Rendering**: Uses AstrBot's built-in HTML render service for image generation
- **PDF Generation**: pyppeteer for HTML-to-PDF conversion (requires Chromium)

## Common Commands

### Installation
```bash
# Install PDF dependencies (via plugin command)
/安装PDF
```

### Usage
```bash
# Analyze group chat
/群分析 [days]

# Configure output format
/设置格式 [image|text|pdf]

# Manage analysis settings
/分析设置 [enable|disable|status|reload|test]
```

### Development
- Plugin follows AstrBot's Star plugin pattern
- Configuration managed through AstrBot's config system
- Uses AstrBot's logger for consistent logging
- Permissions controlled via AstrBot's permission system (ADMIN required)

## Configuration

Plugin configuration stored in AstrBot's config system with options for:
- Enabled groups list
- Analysis parameters (days, message thresholds, max topics/titles/quotes)
- Auto-analysis scheduling (time, enabled groups)
- Output format preferences
- LLM provider settings (custom API key, base URL, model name)
- LLM request parameters (timeout, retries, backoff)
- PDF output directory and filename format
