import logging
import logging.config
import sys
from typing import List

def get_logging_config():
    """
    定义统一的日志配置字典
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,  # 关键：不禁用已存在的 Logger
        "formatters": {
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "app": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "memobase_server": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": "INFO",
        },
    }

def setup_logging():
    """
    初始设置日志系统
    """
    config = get_logging_config()
    logging.config.dictConfig(config)

def refresh_app_logging():
    """
    强制刷新 app 命名空间的日志状态。
    解决 Uvicorn 在启动或重载时可能禁用了 Logger 或重置了 Root 级别的问题。
    """
    # 1. 重新应用配置字典 (确保 Root 和命名空间级别/Handler 正确)
    logging.config.dictConfig(get_logging_config())
    
    # 2. 强力复活被 Uvicorn 禁用的 Logger (针对已经 import 的模块)
    # 这部分虽然看起来不优雅，但却是处理 Uvicorn disable_existing_loggers=True 最彻底的办法
    logger_manager = logging.Logger.manager
    target_prefixes = ["app.", "app", "memobase_server"]
    
    for name, logger_obj in logger_manager.loggerDict.items():
        if isinstance(logger_obj, logging.Logger):
            if any(name.startswith(pre) for pre in target_prefixes):
                logger_obj.disabled = False
                
    logging.getLogger("app").info("Logging configuration refreshed and loggers resurrected.")
