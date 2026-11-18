// 生成答辩 PPT：node slides/build_deck.js（在仓库根目录运行）
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.HOME + "/.claude/skills/pptx/scripts/apply_theme.js");

const FIG = "figures/";
const OUT = "slides/steamguess.pptx";
const FONT = "Microsoft YaHei";

const THEME = {
  name: "Steamguess",
  headFontFace: FONT,
  bodyFontFace: FONT,
  colors: {
    dk1: "1B2838", lt1: "FFFFFF", dk2: "2A475E", lt2: "EEF2F6",
    accent1: "E0782F", accent2: "3D8EB9", accent3: "5BA35B", accent4: "8A6FB8",
    accent5: "C0504D", accent6: "7F8C99", hlink: "3D8EB9", folHlink: "8A6FB8",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 英寸
pres.theme = { headFontFace: FONT, bodyFontFace: FONT };
pres.title = "Steam 销量估算";
const C = pres.SchemeColor;

// ---------- 版式 ----------
pres.defineSlideMaster({
  title: "DARK",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.5, w: 8.8, h: 1.2,
      fontSize: 40, bold: true, color: C.background1, valign: "middle", align: "left" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 2.8, w: 8.8, h: 1.4,
      fontSize: 18, color: C.background2, valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  margin: [0.4, 0.5, 0.4, 0.5],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9, h: 0.7,
      fontSize: 28, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 9.1, y: 5.2, w: 0.5, h: 0.3, fontSize: 10, color: C.accent6, align: "right" },
});

let section = "";
function slide(master, title, notes) {
  const s = pres.addSlide({ masterName: master, sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  if (notes) s.addNotes(notes);
  return s;
}
function sec(t) { section = t; pres.addSection({ title: t }); }

// 文字块：lines 是字符串数组，每行一个段落
function bullets(s, lines, x, y, w, h, size = 15) {
  s.addText(lines.map((t, i) => ({
    text: t, options: { bullet: true, breakLine: i < lines.length - 1 },
  })), { x, y, w, h, fontSize: size, color: C.text1, valign: "top",
    paraSpaceAfter: 8, isTextBox: true, objectName: "要点" });
}
// 大数字卡片
function stat(s, x, y, w, h, num, label, accent = C.accent1, size = 32) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08,
    fill: { color: C.background2 }, line: { color: C.background2 }, objectName: "卡片" });
  s.addText(num, { x, y: y + 0.12, w, h: h * 0.55, fontSize: size, bold: true, color: accent,
    align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addText(label, { x: x + 0.1, y: y + h * 0.6, w: w - 0.2, h: h * 0.36, fontSize: 12,
    color: C.text2, align: "center", valign: "top", margin: 0, isTextBox: true });
}
// 结论条
function takeaway(s, text, y = 4.75) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y, w: 9, h: 0.55, rectRadius: 0.08,
    fill: { color: C.text1 }, line: { color: C.text1 }, objectName: "结论底" });
  s.addText(text, { x: 0.7, y, w: 8.6, h: 0.55, fontSize: 15, bold: true, color: C.background1,
    valign: "middle", margin: 0, isTextBox: true, objectName: "结论" });
}
// 按宽高比放图
function fig(s, file, x, y, maxW, maxH, pxW, pxH) {
  let w = maxW, h = maxW * pxH / pxW;
  if (h > maxH) { h = maxH; w = maxH * pxW / pxH; }
  s.addImage({ path: FIG + file, x: x + (maxW - w) / 2, y, w, h, altText: file });
}
function table(s, rows, x, y, w, colW, size = 13) {
  const head = rows[0].map((t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text2 } } }));
  const body = rows.slice(1).map((r, i) => r.map((t) => ({ text: t,
    options: { color: C.text1, fill: { color: i % 2 ? C.background1 : C.background2 } } })));
  s.addTable([head, ...body], { x, y, w, colW, fontSize: size, valign: "middle",
    border: { type: "solid", pt: 0.5, color: "D5DCE3" }, margin: 0.06, objectName: "表" });
}
const chartText = { catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
  dataLabelFontFace: "+mn-lt", titleFontFace: "+mn-lt", catAxisLabelColor: HEX.dk2,
  valAxisLabelColor: HEX.accent6, catAxisLabelFontSize: 12, valAxisLabelFontSize: 10,
  dataLabelFontSize: 12, dataLabelColor: HEX.dk1 };

// ================= 封面 =================
sec("开场");
{
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: section });
  s.addText("Steam 销量估算", { placeholder: "title" });
  s.addText("销量不公开，用公开的评测数 × 一个会变的倍数 k 去估", { placeholder: "body" });
  s.addText("销量 = 评测数 × k", { x: 0.6, y: 4.2, w: 6, h: 0.6, fontSize: 22, bold: true,
    color: C.accent1, margin: 0, isTextBox: true });
}

// ================= 1 出发点 =================
{
  const s = slide("CONTENT", "出发点：估销量，就是估 k",
    "Steam 不公开销量，但评测数谁都能查。评测只有拥有游戏的人能写，所以评测越多买的人越多。k 是平均多少个玩家里出一条评测。");
  s.addText([
    { text: "销量 = 评测数 × k", options: { fontSize: 34, bold: true, color: C.accent1, breakLine: true } },
    { text: "k = 平均多少个玩家里出一条评测。例：k = 50，1000 条评测 ≈ 5 万份", options: { fontSize: 15, color: C.text2 } },
  ], { x: 0.5, y: 1.15, w: 9, h: 1.2, margin: 0, isTextBox: true });
  stat(s, 0.5, 2.6, 2.8, 1.6, "任意一天", "评测数：Steam 评测接口，能数到任何截止日");
  stat(s, 3.6, 2.6, 2.8, 1.6, "13275 款", "2018 年玩家数（Ars 表），两份一除得到一大批真实的 k", C.accent2);
  stat(s, 6.7, 2.6, 2.8, 1.6, "116 款", "近年公开的真实销量，最后用来校准", C.accent3);
  takeaway(s, "问题转成：每款游戏的 k 是多少");
}

// ================= 2 k 存在吗 =================
sec("k 的规律");
{
  const s = slide("CONTENT", "k 存在：评测数和玩家数大致成正比",
    "两个轴都是对数坐标，一大格是 10 倍。点云是一条 45 度的带子。评测 1000 处，玩家数在 4 万到 10 万之间，k 约 40 到 100。");
  fig(s, "reviews_vs_players.png", 0.4, 1.1, 5.0, 3.55, 1200, 900);
  bullets(s, [
    "11716 款，一个点一款游戏，双对数坐标",
    "整体是 45 度的带子：评测涨 10 倍，玩家也涨约 10 倍",
    "评测 1000 条处 k 约 40 到 100",
    "带子有厚度：同样评测数，玩家可差 10 倍",
    "评测越少，带子越厚",
  ], 5.6, 1.2, 4.0, 3.4, 14);
  takeaway(s, "k 存在，量级几十到一百；但同样的评测数下 k 可以差 10 倍");
}

// ================= 3 k 稳定吗 =================
{
  const s = slide("CONTENT", "k 不稳定：不能所有游戏共用一个",
    "评测数分 11 档，竖线是第 10 到第 90 百分位，顶上的数字是两者的倍数。评测多了也还有 4 到 6 倍。");
  fig(s, "k_by_reviews.png", 0.4, 1.1, 4.6, 3.55, 1350, 1050);
  stat(s, 5.3, 1.15, 2.05, 1.45, "39 倍", "评测 1–9 条时 k 的波动");
  stat(s, 7.5, 1.15, 2.05, 1.45, "4–6 倍", "评测 500 条以上仍有的波动", C.accent2);
  stat(s, 5.3, 2.8, 2.05, 1.45, "26.1%", "共用一个 k：±30% 命中率", C.accent6);
  stat(s, 7.5, 2.8, 2.05, 1.45, "46.2%", "按每款情况估 k（第 8 步）", C.accent3);
  takeaway(s, "每款游戏要按自己的情况估 k");
}

// ================= 4 去掉什么 =================
{
  const s = slide("CONTENT", "训练前只去掉两种学不了的数据",
    "只按输入条件筛，不按 k 筛。门槛比较时考题固定为 10 条以上的全部游戏，只改训练用的门槛。");
  const cards = [
    ["评测只有 1–9 条", "多一个人写评测 k 就减半，k 由碰巧决定，没有规律可学", C.accent1],
    ["不是游戏（42 款）", "软件的“玩家”是用户；Camtasia 361 条评测只有 152 个用户", C.accent2],
  ];
  cards.forEach(([h, b, col], i) => {
    const y = 1.2 + i * 1.6;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y, w: 4.3, h: 1.4, rectRadius: 0.08,
      fill: { color: C.background2 }, line: { color: C.background2 }, objectName: "卡片" });
    s.addText(h, { x: 0.7, y: y + 0.12, w: 3.9, h: 0.45, fontSize: 18, bold: true, color: col, margin: 0, isTextBox: true });
    s.addText(b, { x: 0.7, y: y + 0.6, w: 3.9, h: 0.7, fontSize: 13, color: C.text1, margin: 0, valign: "top", isTextBox: true });
  });
  s.addChart(pres.charts.BAR, [{ name: "均方根误差", labels: ["10 条", "50 条", "500 条"], values: [0.700, 0.727, 0.837] }], {
    x: 5.2, y: 1.1, w: 4.3, h: 3.4, barDir: "col", chartColors: [HEX.accent1],
    showTitle: true, title: "训练门槛越高，整体越不准", titleFontSize: 13, titleColor: HEX.dk1,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000",
    valAxisMinVal: 0.6, valAxisMaxVal: 0.9, valGridLine: { color: "E3E8ED", size: 0.5 },
    catGridLine: { style: "none" }, showLegend: false, ...chartText,
  });
  takeaway(s, "门槛定为 10 条：评测少的游戏也要估，训练时就得见过它们");
}

// ================= 5 k 受什么影响 =================
{
  const s = slide("CONTENT", "猜想：凡是影响“写不写评测”的，都影响 k",
    "8 组都是估一款新游戏时就能拿到的信息。因素互相纠缠，比如越老的游戏打折时间越长，所以要多变量一起看，用树模型。");
  table(s, [
    ["因素", "为什么可能影响 k"],
    ["游戏年龄", "2013 年 11 月才有评测，之前买的人没地方写"],
    ["Steam 内购买占比", "激活码、捆绑包、礼物入库的人更少写评测"],
    ["价格与折扣", "免费或打折白拿的人更少写评测"],
    ["评测语言占比", "不同地区写评测的习惯不同"],
    ["标签（446 种）", "不同类型的游戏，玩家群体不同"],
    ["评测者时长、评测数、好评率", "玩得久、口碑好坏都可能改变写评测的意愿"],
  ], 0.5, 1.15, 9, [2.9, 6.1], 13);
  takeaway(s, "答案等模型训练完，用特征重要性看（第 9 步）");
}

// ================= 6 数据 =================
sec("数据");
{
  const s = slide("CONTENT", "数据：一份真值，四类特征",
    "raw 表接口给什么存什么，清洗做错了从 raw 重算，不用重爬。cleaned 表只整理不取舍，取舍留给样本表。");
  table(s, [
    ["数据", "用途", "款数"],
    ["Ars 2018 玩家数", "真值、游戏名单", "13275"],
    ["Steam 商店信息", "是不是游戏、上架日、标签", "12319"],
    ["Steam 评测计数（每款 15 次请求）", "评测数、好评率、Steam 内购买占比、语言", "11768"],
    ["Steam 评测抽样（分 5 段）", "评测者写评测时的时长", "12446"],
    ["ITAD 历史价格", "截止日原价、折扣、平均实付价", "13131"],
  ], 0.5, 1.15, 9, [3.4, 4.4, 1.2], 13);
  const steps = ["数据源", "raw 表：只存不算", "cleaned 表：只整理", "样本表：一款一行"];
  steps.forEach((t, i) => {
    const x = 0.5 + i * 2.3;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 3.85, w: 2.0, h: 0.6, rectRadius: 0.08,
      fill: { color: i === 3 ? C.accent1 : C.background2 }, line: { color: i === 3 ? C.accent1 : C.background2 }, objectName: "流程" });
    s.addText(t, { x, y: 3.85, w: 2.0, h: 0.6, fontSize: 13, bold: true, align: "center", valign: "middle",
      color: i === 3 ? C.background1 : C.text1, margin: 0, isTextBox: true });
    if (i < 3) s.addText("→", { x: x + 2.0, y: 3.85, w: 0.3, h: 0.6, fontSize: 16, color: C.accent6,
      align: "center", valign: "middle", margin: 0, isTextBox: true });
  });
  takeaway(s, "raw 表原样保留：清洗做错了随时重算，不用重爬");
}

// ================= 7 样本表 =================
{
  const s = slide("CONTENT", "样本表：一款游戏一行，约 211 列进模型",
    "答案是 ln k，学 ln k 是因为我们在乎差几倍。标签 192 列占了大头。缺的数据留空不编，交给模型处理。");
  const parts = [["192", "标签"], ["9", "语言占比"], ["5", "价格与折扣"], ["5", "年龄、评测数、好评率等 5 项"]];
  parts.forEach(([n, t], i) => stat(s, 0.5 + i * 2.3, 1.2, 2.1, 1.5, n, t, [C.accent1, C.accent2, C.accent3, C.accent4][i]));
  bullets(s, [
    "答案是 ln k = ln(玩家数 ÷ 评测数)：在乎的是差几倍，k 从 1.8 到 12927",
    "评测 10 条以上的 9623 款进训练",
    "缺的数据留空不编，交给模型处理",
  ], 0.5, 3.0, 9, 1.6, 15);
  takeaway(s, "特征和答案都只用截止日（2018-07-01）之前的信息");
}

// ================= 8 信号 A =================
sec("模型");
{
  const s = slide("CONTENT", "信号 A：树模型比两个对照都准",
    "五折交叉验证：每款游戏都在模型没见过它的那一轮当考题。树模型是 scikit-learn 的 HistGradientBoostingRegressor。");
  s.addChart(pres.charts.BAR, [{ name: "±30% 命中率", labels: ["固定倍数", "线性回归", "树模型"], values: [26.1, 36.3, 46.2] }], {
    x: 0.5, y: 1.1, w: 4.6, h: 3.5, barDir: "col", chartColors: [HEX.accent6, HEX.accent2, HEX.accent1],
    showTitle: true, title: "±30% 命中率（%），9623 款五折", titleFontSize: 13, titleColor: HEX.dk1,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisMinVal: 0, valAxisMaxVal: 60,
    valGridLine: { color: "E3E8ED", size: 0.5 }, catGridLine: { style: "none" }, showLegend: false, ...chartText,
  });
  table(s, [
    ["方法", "误差", "命中率"],
    ["固定倍数", "1.018", "26.1%"],
    ["线性回归", "0.824", "36.3%"],
    ["树模型", "0.699", "46.2%"],
  ], 5.4, 1.3, 4.1, [1.7, 1.2, 1.2], 14);
  bullets(s, [
    "看特征：+10 个百分点",
    "学会条件组合：再 +10 个百分点",
    "调参只让误差从 0.704 降到 0.699",
  ], 5.4, 3.1, 4.1, 1.5, 14);
  takeaway(s, "特征有用，特征之间的组合也有用");
}

// ================= 9 特征重要性 =================
{
  const s = slide("CONTENT", "k 主要看三件事：多老、在哪买、多少钱",
    "把一组特征在考题上随机打乱再考一次，成绩掉得越多越重要。按组打乱，5 种分折各做一遍。");
  fig(s, "feature_importance.png", 0.4, 1.3, 6.0, 3.3, 1650, 720);
  stat(s, 6.6, 1.15, 2.9, 1.05, "0.700→0.924", "打乱游戏年龄后的误差", C.accent1, 24);
  stat(s, 6.6, 2.35, 2.9, 1.05, "≈ 0.82", "打乱 Steam 内购买占比或价格", C.accent2, 24);
  stat(s, 6.6, 3.55, 2.9, 1.05, "8 组都变差", "5 次都变差，没有可删的", C.accent3, 24);
  takeaway(s, "年龄最重要：评测系统上线前买的人没留下评测，老游戏 k 大");
}

// ================= 10 信号 B =================
{
  const s = slide("CONTENT", "信号 B：在线人数 ÷ 人均时长，另一条路",
    "健身房的比方：不知道会员数，但知道每月平均同时有多少人在练。总小时来自 SteamCharts 月均在线人数。");
  s.addText([
    { text: "玩家数 = 总小时 H ÷ 人均小时 h", options: { fontSize: 22, bold: true, color: C.accent2, breakLine: true } },
    { text: "H：月均在线人数 × 当月小时数，累加到截止月", options: { fontSize: 14, color: C.text1, breakLine: true } },
    { text: "h：由评测者时长中位数换算，ln h = 0.23 + 0.86 · ln t", options: { fontSize: 14, color: C.text1 } },
  ], { x: 0.5, y: 1.15, w: 5.1, h: 1.6, margin: 0, valign: "top", paraSpaceAfter: 6, isTextBox: true });
  table(s, [
    ["3722 款", "误差", "命中率"],
    ["信号 A", "0.602", "53.1%"],
    ["信号 B", "0.578", "49.4%"],
  ], 0.5, 3.0, 5.1, [2.1, 1.5, 1.5], 14);
  stat(s, 6.0, 1.15, 3.5, 1.6, "0.15", "A、B 误差的相关系数：很少往同一边错", C.accent1);
  stat(s, 6.0, 2.95, 3.5, 1.6, "约 4 成", "训练集里能算 B 的比例，多是大游戏", C.accent6);
  takeaway(s, "B 和评测数无关，单独用就和 A 差不多准");
}

// ================= 11 融合 =================
{
  const s = slide("CONTENT", "融合：谁平时准，多听谁的",
    "票数 = 1 ÷ 误差平方，在 ln k 上按占比混合；按评测数分 5 档，各定一个占比。没有 B 的直接用 A。");
  s.addChart(pres.charts.BAR, [
    { name: "只用 A", labels: ["全部 9623 款", "有 B 的 3722 款"], values: [46.2, 53.1] },
    { name: "融合", labels: ["全部 9623 款", "有 B 的 3722 款"], values: [50.2, 63.5] },
  ], {
    x: 0.5, y: 1.1, w: 5.2, h: 3.5, barDir: "col", chartColors: [HEX.accent6, HEX.accent1],
    showTitle: true, title: "±30% 命中率（%）", titleFontSize: 13, titleColor: HEX.dk1,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisMinVal: 0, valAxisMaxVal: 70,
    valGridLine: { color: "E3E8ED", size: 0.5 }, catGridLine: { style: "none" },
    showLegend: true, legendPos: "b", legendFontFace: "+mn-lt", legendFontSize: 12, legendColor: HEX.dk2, ...chartText,
  });
  s.addText([
    { text: "ln k = p · ln k_A + (1 − p) · ln k_B", options: { fontSize: 15, bold: true, color: C.text1, breakLine: true } },
    { text: "p 按两路平时的误差定", options: { fontSize: 13, color: C.text2 } },
  ], { x: 6.0, y: 1.2, w: 3.5, h: 0.9, margin: 0, valign: "top", isTextBox: true });
  bullets(s, [
    "有 B 的游戏：+10 个百分点",
    "整体只 +4：最难估的小游戏最少有 B",
    "按档加权只比简单平均好一点",
  ], 6.0, 2.3, 3.5, 2.2, 14);
  takeaway(s, "两路合起来明显更准");
}

// ================= 12 校准 =================
sec("校准与输出");
{
  const s = slide("CONTENT", "校准：2018 年的规律搬到近年要对正",
    "校准集是 116 款近年公布了真实销量的游戏，来自 Gamalytic 的公开对照表。2018 年每条评测约 80 份，近年约 45 份。");
  fig(s, "calibration_age.png", 0.4, 1.1, 5.2, 3.5, 1350, 825);
  bullets(s, [
    "直接套用整体高估约 76%",
    "树学到“越老 k 越大”，近年游戏基本持平",
    "A：真值 = 0.107 + 0.929 × 树的估计 − 0.238 × ln 年龄",
    "B：整体减 0.096",
    "留一法：每次拿 1 款当考题",
  ], 5.8, 1.2, 3.8, 3.4, 14);
  takeaway(s, "校准把整体偏高和过时的年龄规律两处对正");
}

// ================= 13 校准结果 =================
{
  const s = slide("CONTENT", "校准后：融合误差最小，大错明显减少",
    "B 在近年游戏上命中率最高，但有 15% 差两倍以上；掺进 A 把这些大错砍掉近一半，所以保留融合。");
  table(s, [
    ["116 款留一法", "误差", "±30% 命中率"],
    ["固定倍数", "0.730", "34.5%"],
    ["信号 A", "0.641", "37.9%"],
    ["融合", "0.586", "38.8%"],
  ], 0.5, 1.15, 4.5, [1.9, 1.0, 1.6], 14);
  s.addChart(pres.charts.BAR, [{ name: "差两倍以上的比例", labels: ["A", "B", "融合"], values: [20.5, 15.4, 9.0] }], {
    x: 5.3, y: 1.1, w: 4.2, h: 3.5, barDir: "col", chartColors: [HEX.accent2, HEX.accent3, HEX.accent1],
    showTitle: true, title: "两路都有的 78 款：差两倍以上（%）", titleFontSize: 13, titleColor: HEX.dk1,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisMinVal: 0, valAxisMaxVal: 25,
    valGridLine: { color: "E3E8ED", size: 0.5 }, catGridLine: { style: "none" }, showLegend: false, ...chartText,
  });
  bullets(s, [
    "近年游戏比训练集难估",
    "信号 B 搬到近年依然最稳",
  ], 0.5, 3.2, 4.5, 1.3, 14);
  takeaway(s, "保留融合：估销量能落在两倍以内就算可用");
}

// ================= 14 区间与标签 =================
{
  const s = slide("CONTENT", "输出：估计值 + 80% 区间 + 置信标签",
    "区间取留一法里“真值 ÷ 估计值”的 10% 到 90% 分位，是预测区间，不是参数的置信区间。标签阈值是看结果之前定的。");
  table(s, [
    ["80% 区间", "倍数"],
    ["有 B（78 款）", "0.59 ～ 1.73"],
    ["没 B（38 款）", "0.42 ～ 3.32"],
  ], 0.5, 1.15, 4.3, [2.3, 2.0], 14);
  s.addText("例：估 10 万份、有 B → 5.9 万～17.3 万份", { x: 0.5, y: 2.55, w: 4.3, h: 0.5,
    fontSize: 14, italic: true, color: C.text2, margin: 0, isTextBox: true });
  table(s, [
    ["标签", "条件", "命中率"],
    ["高", "有 B、两路差 < 1.65 倍、评测 ≥ 500", "66%"],
    ["中", "其余介于两者之间", "20%"],
    ["低（分歧大）", "有 B、两路差 > 1.65 倍", "34%"],
    ["低（外推）", "没 B、评测 < 500", "23%"],
  ], 5.1, 1.15, 4.4, [1.2, 2.3, 0.9], 12);
  takeaway(s, "两路说法一致时更可信；只有 A 又评测少时最不可信");
}

// ================= 15 查询 =================
{
  const s = slide("CONTENT", "单款查询：python -m query <appid>",
    "冻结文件存的是树、校准系数、占比和区间倍数；文件不换，同一款游戏查出来的结果就不变。");
  const steps = ["记一行（这款, 今天）", "现场采这一款", "重跑清洗，样本表多一行", "读冻结文件，套公式"];
  steps.forEach((t, i) => {
    const y = 1.2 + i * 0.82;
    s.addShape(pres.shapes.OVAL, { x: 0.5, y, w: 0.6, h: 0.6, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: "序号" });
    s.addText(String(i + 1), { x: 0.5, y, w: 0.6, h: 0.6, fontSize: 16, bold: true, color: C.background1,
      align: "center", valign: "middle", margin: 0, isTextBox: true });
    s.addText(t, { x: 1.3, y, w: 3.4, h: 0.6, fontSize: 15, color: C.text1, valign: "middle", margin: 0, isTextBox: true });
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.0, y: 1.2, w: 4.5, h: 3.25, rectRadius: 0.08,
    fill: { color: C.background2 }, line: { color: C.background2 }, objectName: "例子" });
  s.addText([
    { text: "Vampire Survivors", options: { fontSize: 18, bold: true, color: C.text1, breakLine: true } },
    { text: "评测 26.7 万条", options: { fontSize: 13, color: C.text2, breakLine: true } },
    { text: "约 1121 万份", options: { fontSize: 34, bold: true, color: C.accent1, breakLine: true } },
    { text: "80% 区间 667 万 ～ 1936 万", options: { fontSize: 15, color: C.text1, breakLine: true } },
    { text: "标签：低（两路估计分歧大）", options: { fontSize: 15, color: C.text1 } },
  ], { x: 5.25, y: 1.35, w: 4.0, h: 3.0, margin: 0, valign: "top", paraSpaceAfter: 6, isTextBox: true });
  takeaway(s, "一次约 1 分钟；特征和训练时是同一段代码算的");
}

// ================= 结尾 =================
{
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: section });
  s.addText("总结", { placeholder: "title" });
  const nums = [["26% → 46%", "树模型比共用一个 k 的命中率"], ["50.2%", "融合后 9623 款的命中率"], ["0.586", "近年 116 款校准后的误差"]];
  nums.forEach(([n, t], i) => {
    const x = 0.6 + i * 3.0;
    s.addText(n, { x, y: 2.9, w: 2.8, h: 0.8, fontSize: 30, bold: true, color: C.accent1, margin: 0, isTextBox: true });
    s.addText(t, { x, y: 3.7, w: 2.8, h: 0.6, fontSize: 14, color: C.background2, margin: 0, valign: "top", isTextBox: true });
  });
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote " + OUT);
})();
