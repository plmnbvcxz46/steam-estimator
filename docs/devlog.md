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

## 2026-11-09（采集）

- 实测 Steam `appdetails` 接口返回格式（请求 413150、440、1 三个 appid，参数 `cc=us&l=english`）：
  - 返回形如 `{"413150": {"success": true, "data": {...}}}`，最外层键是 appid 的文本。
  - 不存在的 appid 返回 `{"success": false}`，没有 `data`，记为“未收录”。
  - 付费游戏有 `price_overview`，`initial` 的单位是美分（1499 表示 $14.99）；免费游戏没有这个字段，价格存空值。
  - `release_date` 是英文文本（如 `Feb 26, 2016`），raw 层存原文，不在 crawler 里解析；日期规则（含抢先体验改用第一条评测日期）统一放在 pipeline。DEVELOPMENT.md 的数据表已注明。
  - `genres` 是 `[{"id", "description"}]` 列表，只取 `description`，用 `|` 连成一个文本。
- 测试用的接口样本放在 `tests/fixtures/`：由上述真实返回挑出用到的字段拼成，不是完整原样；完整返回含大段 HTML 与截图链接，不入库。
- 限速数值尚未实测，`min_interval=1.5` 只是暂定值，待小批量真实运行后再定。
- appdetails 小批量实测（从 Ars 表按固定种子取 20 款）：20 款全部成功，无失败、无限流（429）；耗时 44 秒，约 2.2 秒一个，比 `min_interval=1.5` 慢，说明瓶颈是单次请求的耗时而不是间隔（每次请求都新建连接）。只发了 20 个请求，限流的真实上限仍未测出，`min_interval` 保持暂定。
- 实测发现：20 款里有 3 款 `is_free=0` 但没有 `price_overview`（价格为空），说明“付费但无当前价格”的游戏存在（推测是已下架或不可购买），pipeline 处理价格兜底时要考虑这种情况。
- 实测发现：`genres` 里会出现 `Early Access`（如 appid 791390），可用来识别抢先体验游戏。
- 续传验证：第二次运行同样的命令，日志显示“已完成 20 个，本次要爬 0 个”，没有重复请求。
