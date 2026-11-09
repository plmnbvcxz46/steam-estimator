"""项目里所有固定路径的唯一出处。其他模块从这里导入，不要自己再算根目录。"""

from pathlib import Path

# 本文件在 <根目录>/common/ 下，往上两级就是项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
SOURCE_DIR = DATA_DIR / "source"  # 外部原件
LOG_DIR = DATA_DIR / "logs"
DB_PATH = DATA_DIR / "steam.db"
