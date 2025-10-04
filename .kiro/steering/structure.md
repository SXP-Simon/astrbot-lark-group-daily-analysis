# Project Structure

## Root Files

- `main.py`: Plugin entry point, command handlers, lifecycle management
- `metadata.yaml`: Plugin metadata (name, version, author, description)
- `requirements.txt`: Python dependencies (pyppeteer==1.0.2)
- `README.md`: User documentation (Chinese)
- `PDF_功能说明.md`: PDF feature documentation (Chinese)

## Source Code Organization

```
src/
├── __init__.py
├── core/                    # Core functionality
│   ├── config.py           # ConfigManager - plugin configuration
│   ├── bot_manager.py      # BotManager - bot instance management
│   └── message_handler.py  # MessageHandler - fetch/process messages
├── analysis/               # Analysis modules
│   ├── llm_analyzer.py    # LLMAnalyzer - topic/title/quote analysis
│   └── statistics.py      # StatisticsAnalyzer - message statistics
├── models/                 # Data models
│   └── data_models.py     # SummaryTopic, UserTitle, GoldenQuote, etc.
├── reports/                # Report generation
│   ├── generators.py      # ReportGenerator - image/PDF/text reports
│   └── templates.py       # HTMLTemplates - HTML templates
├── scheduler/              # Scheduled tasks
│   └── auto_scheduler.py  # AutoScheduler - automatic analysis
├── utils/                  # Utilities
│   ├── helpers.py         # MessageAnalyzer - message analysis helpers
│   └── pdf_utils.py       # PDFInstaller - PDF dependency management
└── visualization/          # Data visualization
    └── activity_charts.py # ActivityVisualizer - activity charts
```

## Module Responsibilities

### Core Modules
- **ConfigManager**: Centralized configuration access and persistence
- **BotManager**: Manages bot instance lifecycle and context
- **MessageHandler**: Fetches and preprocesses group messages

### Analysis Modules
- **LLMAnalyzer**: LLM-powered analysis with retry/timeout logic
- **StatisticsAnalyzer**: Calculates message statistics and activity patterns

### Report Modules
- **ReportGenerator**: Orchestrates report generation in multiple formats
- **HTMLTemplates**: Provides HTML templates for image and PDF reports

### Scheduler Module
- **AutoScheduler**: Manages scheduled automatic analysis tasks

### Utility Modules
- **MessageAnalyzer**: High-level message analysis orchestration
- **PDFInstaller**: Handles pyppeteer installation and verification
- **ActivityVisualizer**: Generates HTML-based activity visualizations

## Design Patterns

- **Modular Architecture**: Clear separation of concerns with single-responsibility modules
- **Dependency Injection**: Components receive dependencies via constructor
- **Async/Await**: Non-blocking I/O throughout the codebase
- **Configuration-Driven**: Behavior controlled via centralized configuration
- **Graceful Degradation**: Fallback mechanisms for LLM failures and missing dependencies

## File Naming Conventions

- Snake_case for Python files and modules
- Descriptive names indicating module purpose
- `__init__.py` files for package initialization
- Chinese filenames for user-facing documentation
