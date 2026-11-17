# AGENTS.md

给在本仓库工作的人和 AI 代理。设计以 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) 为准，改设计先改文档；下面只是摘要，冲突时以文档为准。个人偏好不放这里。

## 必读

- **分层**（见「架构」）：`crawler → pipeline → analysis → viz` 单向依赖；只有 crawler 发网络请求；`common` 放各模块共用的小工具（路径、日志、时间），在最底层，不含业务逻辑。三层数据都在 `data/steam.db`，用 `raw_` / `cleaned_` / `result_` 前缀区分，raw 之上可重建。截止日截断、样本划分等规则集中实现一次，各模块复用，不各写一套。单款查询入口 `query` 按顺序调用采集、清洗，再用冻结的模型估算；它不拟合，只有套冻结系数的估算公式和置信标签两小段计算。

## 约定

- Python 3.11+，依赖写入 `requirements.txt`。
- 清洗不静默丢行，一律写日志。
- 爬虫按站点限速；续传靠主键跳过已有行，空结果记 `raw_crawl_log`，不另设缓存与检查点；不爬 SteamDB。
- 密钥只放 `.env`；`data/steam.db` 不入 git。
- 文档管"做什么、为什么、不能做什么"，代码管"叫什么、取多少"。代码和其他文件引用文档时只写文件名或章节标题，不写章节号。
- 文档分工：设计 → DEVELOPMENT.md；公式推导 → DERIVATIONS.md；决策与踩坑 → devlog.md（按日期）；答辩讲解稿 → PRESENTATION.md（只写讲述线，规则细节链接到 DEVELOPMENT.md）；README 只放简介、运行命令、最新结果。不新增文档文件。
- 提交信息 `类型: 描述`（feat / fix / docs / refactor / perf / style / chore / test）。不加任何 AI 署名，作者只用提交者本人的 git 身份。

## 分支与推送

- `main` 只放能跑通的稳定版本，不直接在上面开发；所有改动在分支上做，完成后合并。
- 分支名：`类型/简述`，小写加连字符，例如 `feat/crawler-reviews`、`fix/cutoff-align`、`docs/readme`。类型同提交类型。
- 一个分支只做一件事，尽量小步提交；提交信息 `类型: 描述`。
- 推送前先跑 `pytest`；不强推 `main`（不用 `--force`）。
- 远程名统一用 `origin`，用 SSH 地址；推送新分支用 `git push -u origin <分支名>`。
- 共享文件（devlog.md、DEVELOPMENT.md 的数据表、`common/`、`crawler/http.py`、`crawler/crawl_log.py`）改动要小、尽早合并；改共用代码先说一声，单独一个小 PR。

## 健壮性

- 网络采集拿到的响应一律校验后再用，缺字段或异常值写入日志并跳过，不让整批任务崩掉。
- 本地固定文件（CSV、真值表）不逐行防御，只防真实会出的问题，格式出错让它直接报错。
- 网络请求必须有超时、重试与退避；任务可中断重跑，结果不变。
- 写数据库用事务，一批写完再提交；写其他文件先写临时文件再改名，避免中断留下半截数据。
- 不吞异常：捕获后要记录原因；关键假设用断言或测试守住。
