# steamsales-estimator

只用公开数据估算单款 Steam 游戏的销量，输出估计值、80% 预测区间和置信标签。

设计见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)，公式推导见 [docs/DERIVATIONS.md](docs/DERIVATIONS.md)，决策记录见 [docs/devlog.md](docs/devlog.md)，讲解稿见 [docs/PRESENTATION.md](docs/PRESENTATION.md)。

## 安装与运行

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

运行（当前能跑的）：

```bash
python -m crawler.sources.ars            # 导入 Ars 2018 年玩家数表（只需一次）
python -m crawler [--workers 路数]      # 采集全部数据源到 steam.db 的 raw_* 表：真值、商店、价格、在线人数、评测；已采过的自动跳过（要 .env 里的 ITAD 密钥）
python -m pipeline                      # 清洗并建样本表，写 cleaned_* 表；单独重建一张用 python -m pipeline.games 等
python -m analysis.baselines            # 两个对照（固定倍数、线性回归）的五折交叉验证成绩
python -m analysis.signal_a             # 三种方法的五折交叉验证，写 result_cv_* 表
python -m viz.k_by_reviews              # 图表到 figures/；另有 viz.reviews_vs_players
python -m viz.method_comparison         # 三种方法的对比图（要先跑 analysis.signal_a）
python -m analysis.tree_params          # 树模型参数比较，写 result_cv_scores（约 5 分钟）
python -m viz.tree_params               # 参数比较的曲线图（要先跑 analysis.tree_params）
python -m analysis.feature_importance   # 特征按组重要性，写 result_cv_scores（约 1 分钟）
python -m viz.feature_importance        # 重要性图（要先跑 analysis.feature_importance 和 analysis.signal_a）
python -m analysis.signal_b             # 信号 B 的五折成绩，和 A 比（要先跑 analysis.signal_a）
python -m viz.signal_b_fit              # 信号 B 的拟合图；另有 viz.signal_b_comparison（要先跑 analysis.signal_b）
python -m analysis.fusion               # 两路按评测数分档加权融合的五折成绩（要先跑 analysis.signal_b）
python -m viz.fusion_comparison         # 融合的对比图；另有 viz.fusion_by_reviews（要先跑 analysis.fusion）
python -m analysis.calibration          # 校准集上两路的校准、融合和留一法成绩，并把最终模型冻结到 data/models/frozen.joblib（要先跑 analysis.signal_b）
python -m viz.calibration_comparison    # 校准的对比图；另有 viz.calibration_age（要先跑 analysis.calibration）
pytest                                  # 测试
```

新增近年真值：在 `data/source/sales_truth_manual.csv` 里加一行（出处链接和原话必填），再依次跑 `python -m crawler`、`python -m pipeline`、`python -m analysis.calibration`。

单款查询（要先跑过 `analysis.calibration`，要 .env 里的 ITAD 密钥）：

```bash
python -m query <appid>                 # 现场采这一款、重跑清洗，打印估计销量、80% 区间和置信标签（约 1 分钟）
```

## 当前进度

- **数据**：商店信息、评测计数、评测抽样、价格历史、在线人数（SteamCharts）已采集并清洗。样本表的训练集是 2018 年的 11716 款，信号 A 的四类特征都已算好。
- **三种方法的五折成绩**（均方根误差、±30% 命中率）：固定倍数 1.018、26.1%；线性回归 0.824、36.3%；树模型 0.701、46.3%（参数已比较选定）。
- **特征重要性**：8 组特征都有用，最重要的是游戏年龄、Steam 内购买占比、价格。
- **信号 B**：训练集评测 10 条以上的游戏里 3722 款能算。同这 3722 款上，信号 A 0.604、53.1%，信号 B 0.578、49.4%。
- **融合**（两路按评测数分档加权）：同这 3722 款上 0.447、63.5%；全部 9623 款上 0.653、50.4%（只用 A 为 0.701、46.3%）。
- **校准**：校准集用 Gamalytic 博客的公开销量对照表（评测 10 条以上的 116 款，其中两路都有的 78 款）。留一法成绩：全部 116 款上固定倍数 0.730、34.5%，信号 A 校准后 0.641、37.9%，融合 0.586、38.8%；两路都有的 78 款上信号 A 0.521、47.4%，信号 B 0.478、52.6%，融合 0.413、48.7%，差两倍以上的比例从 A 的 20.5%、B 的 15.4% 降到 9.0%。
- **预测区间**：80%，取留一法误差的第 10、第 90 百分位。有 B 的 0.59 到 1.73 倍，没有 B 的 0.42 到 3.32 倍。
- **置信标签**：按两路分歧和评测数分高、中、低，留一法下“高”的 41 款命中 66%。
- **查询**：模型已冻结，单款查询 `python -m query <appid>` 可用。
