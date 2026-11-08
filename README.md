# steamsales-estimator

只用公开数据估算单款 Steam 游戏的销量，输出估计值、95% 区间、置信标签和可复查的计算过程。

设计见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)，公式推导见 [docs/DERIVATIONS.md](docs/DERIVATIONS.md)，决策记录见 [docs/devlog.md](docs/devlog.md)。

## 安装与运行

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

运行：

```bash
python -m crawler <数据源>               # 采集到 steam.db 的 raw_* 表
python -m pipeline                      # 清洗、特征、样本划分，写 cleaned_* 表
python -m analysis                      # 留一法评估 + 全量拟合，写 result_* 表与 data/models/
python -m viz                           # 图表到 figures/
python -m query <appid> [--cutoff 日期]  # 单款查询：采集、估算并生成查询页
```
