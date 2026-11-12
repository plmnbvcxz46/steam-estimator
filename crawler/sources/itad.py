"""采集 IsThereAnyDeal（ITAD）的历史价格。

商店接口只能拿到今天的价格，ITAD 记录了每次调价的时刻和价格，用来还原截止日当时的价格。
ITAD 不认 Steam 的 appid，所以分两步：先把 appid 换成 ITAD 的游戏编号（raw_itad_ids），
再按编号逐款查价格历史（raw_price_history）。

接口要 API 密钥，放在项目根目录的 .env 里（ITAD_API_KEY=...），.env 不进仓库。
"""

from dotenv import dotenv_values

from common.paths import PROJECT_ROOT

ENV_PATH = PROJECT_ROOT / ".env"


def load_api_key():
    """从 .env 读 ITAD 密钥。没填就直接报错，并说清楚怎么填。"""
    # dotenv_values 只把文件读成字典，不改系统环境变量，密钥从哪来一目了然
    key = dotenv_values(ENV_PATH).get("ITAD_API_KEY")
    if not key:
        raise RuntimeError(f"缺少 ITAD_API_KEY：照 .env.example 在 {ENV_PATH} 里写一行 ITAD_API_KEY=你的密钥")
    return key
