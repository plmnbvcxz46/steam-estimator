"""日志配置：命令行入口调用一次，之后各模块的 logger 自动生效。"""

import logging

from common.paths import LOG_DIR


def setup_logging(log_filename):
    """日志同时输出到屏幕和 data/logs/<log_filename>：屏幕上当场看，文件留作记录。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        # %(name)s 是发出这条日志的模块名（来自各文件里的 getLogger(__name__)）
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_DIR / log_filename, encoding="utf-8"),
        ],
    )
