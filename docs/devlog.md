# devlog

按日期记录决策与踩坑。事后加的规则注明"事后加"；涉及留一法结果的选择注明试过的变体数。

## 2026-11-05

- 建仓库骨架。
- 重整 DEVELOPMENT.md：新增架构一章（模块与数据流、数据表、单款查询）。方法内容未改。
- 降低文档与代码的耦合：文档只定职责、主键与原则，名字和数值以代码/配置为准；代码与 AGENTS 引用文档不写章节号；AGENTS 只做摘要，冲突以文档为准。
- 按朴素、客观的学术风格重写 DEVELOPMENT.md 与 README 的行文（由 agy / Gemini 4 Argon 依据事实清单成文，人工核对数值与编号）；公式改为 LaTeX。内容未改。

## 2026-11-09

- 找回 2018 训练真值的原始文件：Ars Technica 在 2018-07-01 公开的玩家数表（Steam 成就接口泄露），共 13,281 行，表头 `Title, Players Estimate ,Steam App ID`。来源地址 `arstechnica.com/wp-content/uploads/2018/07/games_achievements_players_2018-07-01.csv`。
- 原件取自早期探索仓库 plmnbvcxz46/steamsales-guess 的 `data/raw/source/`，原样复制到本仓库 `data/source/`，不改动；清洗和入库 `raw_ars_players_2018` 留到下一步。
- 已知待处理：玩家数带引号和千分位逗号（如 `" 50,191,347 "`），导入时需清洗。
- 修正上一条："原样复制"不准确：原件不是 UTF-8（标题里的特殊符号导出时已乱码），为了省掉编码处理，已手工转成 UTF-8，文件名沿用 `_ars_original`；行数与玩家数、appid 未变，乱码的标题未修（建模只用 appid，游戏名以后取自 appdetails）。
- 原件固定在本地，导入只防两件事：表头对不对，玩家数能不能解析；重复 appid（6 个，内容相同）只保留第一条并写日志。格式出错就让它直接报错，不逐行防御。以后网络采集的外部输入再严格校验。
