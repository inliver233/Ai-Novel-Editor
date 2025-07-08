import sys
import logging
import inspect
from dataclasses import dataclass
from pathlib import Path

try:
    from loguru import logger
except ImportError:
    raise ImportError("loguru is not installed., Please install it using pip insall loguru")

__all__ = [
    "Defaults",
    "PropagateFromLoguruHandler",
    "ColoredStreamHandler",
    "InterceptHandler",
    "intercept_logging",
    "configure_logging",
]

@dataclass(frozen=True)
class Defaults:
    LOG_FORMAT: str = (
        "<level>{level: <8}</level> | "
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    LOG_LEVEL: str = "DEBUG"
    LOG_ROTATION: str = "00:00"
    LOG_RETENTION: str = "3 days"
    LOG_COMPRESSION: str = "zip"
    
class PropagateFromLoguruHandler(logging.Handler):
    """Propagate loguru messages to logging

    Usage:
        logger.add(PropagateHandler(), format="{message}")
    """
    def emit(self, record: logging.LogRecord) -> None:
        logging.getLogger(record.name).handle(record)


class InterceptHandler(logging.Handler):
    """
    Default handler from examples in loguru documentation.

    This handler intercepts all log requests and
    passes them to loguru.

    For more info see:
    https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging
    """
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists.
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())
        
        
        
class ColoredStreamHandler(logging.StreamHandler):
    """Colored stream handler
    
    """
    def __init__(self):
        super().__init__()
        try:
            from colorlog import ColoredFormatter
        except ImportError:
            raise ImportError("colorlog is not installed")

        self.setFormatter(ColoredFormatter(
            "%(green)s%(asctime)s.%(msecs)03d"
            "%(red)s | "
            "%(log_color)s%(levelname)-8s"
            "%(red)s | "
            "%(cyan)s%(name)s"
            "%(red)s:"
            "%(cyan)s%(module)s"
            "%(red)s:"
            "%(cyan)s%(funcName)s"
            "%(red)s:"
            "%(cyan)s%(lineno)d"
            "%(red)s - "
            "%(log_color)s%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            reset=True,
            log_colors={
                'DEBUG': 'blue',
                'INFO': 'white',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'white,bg_red',
            },
            style='%'
        ))
        

def intercept_logging() -> None:
    """intercept all logging to loguru"""
    intercept_handler = InterceptHandler()
    # Configuares global logging
    logging.basicConfig(handlers=[intercept_handler], level=0, force=True)


def configure_logging(
    config: dict | str | Path | None = None,
    *,
    level: str = Defaults.LOG_LEVEL,
    format: str = Defaults.LOG_FORMAT,
    log_file: Path | None = None,
    rotation: str = Defaults.LOG_ROTATION,
    retention: str = Defaults.LOG_RETENTION,
    compression: str = Defaults.LOG_COMPRESSION,

) -> None:
    """配置logging由loguru 控制台和文件输出

    Args:
        config (Optional[Union[Dict, str, Path]], optional): config or file, 用于loguru_config. Defaults to None.
        level (str, optional): Defaults to Defaults.LOG_LEVEL.
        format (str, optional): Defaults to Defaults.LOG_FORMAT.
        name (Optional[str], optional): 日志二级目录名称，通常是应用名称. Defaults to None.
        rotation (str, optional): 轮转方式. Defaults to Defaults.LOG_ROTATION.
        retention (str, optional): 保留方式. Defaults to Defaults.LOG_RETENTION.
        compression (str, optional): 压缩方式. Defaults to Defaults.LOG_COMPRESSION.

    Raises:
        ImportError: 导入异常
    """
    intercept_logging()
    
    if config is not None:
        try:
            from loguru_config import LoguruConfig
        except ImportError:
            raise ImportError("loguru_config is not installed")
        LoguruConfig.load(config)
        return 
    
    logger.remove()
    logger.add(
        sys.stdout,
        level=level,
        format=format,
    )
    if log_file is not None:
        logger.add(
            log_file,
            level=level,
            format=format,
            rotation=rotation,
            retention=retention,
            compression=compression
        )