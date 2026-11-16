# steamsales-estimator

只用公开数据估算单款 Steam 游戏的销量，输出估计值、95% 区间、置信标签和可复查的计算过程。免费游戏只输出玩家数，不换算成销量。

设计见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)，公式推导见 [docs/DERIVATIONS.md](docs/DERIVATIONS.md)，决策记录见 [docs/devlog.md](docs/devlog.md)。

## 安装与运行

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

运行（当前能跑的）：

```bash
python -m crawler.sources.<源>          # 采集到 steam.db 的 raw_* 表；源：store_items、review_counts、reviews、itad、ars、steamcharts
python -m pipeline.games                # 清洗，写 cleaned_* 表；另有 pipeline.prices、pipeline.review_counts、pipeline.charts
python -m pipeline.samples              # 样本表 cleaned_samples（要先跑完上面四个清洗）
python -m analysis.baselines            # 两个对照（固定倍数、线性回归）的五折交叉验证成绩
python -m analysis.signal_a             # 三种方法的五折交叉验证，写 result_cv_* 表
python -m viz.k_by_reviews              # 图表到 figures/；另有 viz.reviews_vs_players
python -m viz.method_comparison         # 三种方法的对比图（要先跑 analysis.signal_a）
python -m analysis.tree_params          # 树模型参数比较，写 result_cv_scores（约 5 分钟）
python -m viz.tree_params               # 参数比较的曲线图（要先跑 analysis.tree_params）
python -m analysis.feature_importance   # 特征按组重要性，写 result_cv_scores（约 1 分钟）
python -m viz.feature_importance        # 重要性图（要先跑 analysis.feature_importance 和 analysis.signal_a）
pytest                                  # 测试
```

全量训练、校准、留一法评估、单款查询还没做（规划中）：

```bash
python -m analysis                      # 留一法评估 + 全量拟合，写 result_* 表（规划中）
python -m query <appid> [--cutoff 日期]  # 单款查询（规划中）
```

## 当前进度

已完成采集和清洗的数据：商店信息、评测计数、评测抽样、价格历史。样本表已有训练集（2018 年 11716 款），信号 A 的四类特征都已算好；五折成绩：固定倍数的均方根误差 1.018、±30% 命中率 26.1%；线性回归 0.824、36.3%；树模型 0.701、46.3%（参数已比较选定）。特征按组重要性已算出：8 组特征都有用，最重要的是游戏年龄、Steam 内购买占比、价格。模型还没全量训练和保存，校准和信号 B 未开始。
