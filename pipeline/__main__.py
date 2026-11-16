"""清洗的总入口：python -m pipeline

按顺序重建全部 cleaned 表，最后建样本表。不联网，只读 raw 表，随时可以重跑。
各脚本自己的入口照常能用（如 python -m pipeline.games），改了某一张表的规则时单独重建它。

顺序：样本表要读前面所有的表，所以排在最后；前面几张互相不依赖。
"""

from common.log import setup_logging
from pipeline import charts, games, prices, review_counts, sales_truth
from pipeline.samples import build

# 日志只在这里配置一次：后面各脚本再配置不会生效，所有日志都写进同一个文件
setup_logging("pipeline.log")

games.main()
prices.main()
review_counts.main()
charts.main()
sales_truth.main()
build.main()
