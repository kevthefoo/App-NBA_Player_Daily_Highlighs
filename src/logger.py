"""
Centralized logging system for NBA Player Daily Highlights Automation.

Provides consistent logging across all modules with both console and file output.
Errors and critical issues are logged to separate error log files for easy debugging.
"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler


# Log format with timestamp, level, module, and message
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Log directory (in project root)
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")


def setup_logger(
    name: str,
    log_level: int = logging.DEBUG,
    console_level: int = logging.INFO,
    log_to_file: bool = True,
) -> logging.Logger:
    """
    Set up a logger with console and file handlers.

    Args:
        name: Logger name (usually module name like 'main', 'nba_api', etc.)
        log_level: Minimum level to log to file (default: DEBUG)
        console_level: Minimum level to log to console (default: INFO)
        log_to_file: Whether to log to file (default: True)

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(log_level)

    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    # Console handler (with color support for Windows)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(ColoredFormatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(console_handler)

    # File handlers
    if log_to_file:
        os.makedirs(LOG_DIR, exist_ok=True)

        # Get today's date for log file names
        today = datetime.now().strftime("%Y-%m-%d")

        # Main log file (all levels) - rotating, max 10MB, keep 5 backups
        main_log_path = os.path.join(LOG_DIR, f"nba_highlights_{today}.log")
        main_handler = RotatingFileHandler(
            main_log_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        main_handler.setLevel(log_level)
        main_handler.setFormatter(formatter)
        logger.addHandler(main_handler)

        # Error log file (ERROR and above only)
        error_log_path = os.path.join(LOG_DIR, f"errors_{today}.log")
        error_handler = RotatingFileHandler(
            error_log_path,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=5,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)

    return logger


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to console output on supported terminals."""

    # ANSI color codes
    COLORS = {
        logging.DEBUG: "\033[36m",      # Cyan
        logging.INFO: "\033[32m",       # Green
        logging.WARNING: "\033[33m",    # Yellow
        logging.ERROR: "\033[31m",      # Red
        logging.CRITICAL: "\033[35m",   # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, fmt: str, datefmt: str = None):
        super().__init__(fmt, datefmt)
        # Check if colors are supported
        self.use_colors = self._supports_color()

    def _supports_color(self) -> bool:
        """Check if the terminal supports colors."""
        # Windows 10+ supports ANSI colors in cmd/PowerShell
        if sys.platform == "win32":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                # Enable ANSI escape sequences on Windows
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
                return True
            except Exception:
                return False
        # Unix-like systems generally support colors
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with optional colors."""
        if self.use_colors and record.levelno in self.COLORS:
            # Add color to the level name
            record.levelname = f"{self.COLORS[record.levelno]}{record.levelname}{self.RESET}"
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with the given name.

    This is the primary function to use in other modules.

    Args:
        name: Logger name (e.g., 'main', 'nba_api', 'highlights', 'thumbnail', 'upload')

    Returns:
        Configured logger instance.

    Example:
        from src.logger import get_logger
        logger = get_logger('my_module')
        logger.info("Starting process")
        logger.error("Something went wrong", exc_info=True)
    """
    return setup_logger(name)


def log_exception(logger: logging.Logger, message: str, exc: Exception = None) -> None:
    """
    Log an exception with full traceback.

    Args:
        logger: Logger instance to use.
        message: Custom message describing the error context.
        exc: Exception instance (optional, uses current exception if not provided).
    """
    if exc:
        logger.error(f"{message}: {type(exc).__name__}: {exc}", exc_info=True)
    else:
        logger.error(message, exc_info=True)


# Create a default root logger for the application
root_logger = setup_logger("nba_highlights")
