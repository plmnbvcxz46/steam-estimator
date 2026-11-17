// 第三段：树模型、训练数据与检验（镜 10–12）
// 镜 10：第二段的画面推远淡出，树模型的公式飞到顶上；画出冻结模型真正的第 1 棵树，
//        再缩成 400 棵小树里的第一棵，右边一条曲线跟着树数涨：估对比例从固定 k 的 26.1% 涨到 46.3%。
// 镜 11：先画出空的样本表（8 组特征加一列答案），五个来源依次弹出在各自负责的列上方，
//        连线落进去，这几列填上；最后标出行数、列数。
// 镜 12：样本表横切成 5 份，考试的那一份轮流换一遍；合回去，右边亮出仍估错 3 倍以上的款数。
// 变量都带 3 结尾，不和前两段重名。

let B3 = null;
let layer3 = null;  // 第二段的画面先画在这一层，整层推远淡出

const TOP_Y = 150;      // 公式停在顶上的基线
const TOP_SIZE = 60;

// 镜 10 的大树（画面正中），节点位置是屏幕坐标
const TREE3 = {
  root: { x: 960, y: 360 },
  left: { x: 640, y: 560 },
  right: { x: 1280, y: 560 },
  leaves: [{ x: 500, y: 740 }, { x: 780, y: 740 }, { x: 1140, y: 740 }, { x: 1420, y: 740 }],
};
// 400 棵小树排成 20 × 20
const GRID3 = { x: 205, y: 300, cell: 30, cols: 20 };
// 右边的曲线：横轴树的棵数 0–400，纵轴估对比例 20%–50%
const CURVE3 = { x0: 1110, x1: 1770, yBottom: 830, yTop: 330, lo: 0.2, hi: 0.5 };


function preparePart3(data) {
  layer3 = document.createElement("canvas");
  layer3.width = W;
  layer3.height = H;
  B3 = buildBeats3();
  B2.handoff = B3.s10;
}

function buildBeats3() {
  const b = { s10: shot(10).start, s11: shot(11).start, s12: shot(12).start };
  // 镜 10
  b.tree = word(10, "单棵树");
  b.price = word(10, "价格");
  b.age = word(10, "上架时间");
  b.split = word(10, "逐层分叉");
  b.many = word(10, "四百棵树");
  b.grow = word(10, "一棵接一棵");
  b.fix = word(10, "修补");
  b.gridEnd = word(10, "前序误差", "end");  // 400 棵在念完“前序误差”时长齐
  // 镜 11
  b.groups = word(11, "八组特征");
  b.table = word(11, "样本表");
  // 镜 12
  b.cut = word(12, "分五份");
  b.rotate = word(12, "轮流");
  b.rejoin = word(12, "即便如此");
  b.off = word(12, "估错");
  return b;
}

// ---------- 镜 10：第二段推远淡出，公式飞到顶上 ----------

function drawHandoff3(ctx, t) {
  const p = ease.inOutCubic(ramp(t, B3.s10, B3.s10 + 0.7));
  if (p >= 1) return;
  const g = layer3.getContext("2d");
  g.clearRect(0, 0, W, H);
  chartCtx.clearRect(0, 0, W, H);
  drawPart2(g, chartCtx, t);
  // 镜头往公式那边推：以公式为中心放大，同时整层淡出
  const cx = COL + 250;
  const cy = HEADER_Y - 15;
  const s = 1 + 0.35 * p;
  ctx.save();
  ctx.globalAlpha = 1 - p;
  ctx.translate(cx, cy);
  ctx.scale(s, s);
  ctx.translate(-cx, -cy);
  ctx.drawImage(layer3, 0, 0);
  ctx.restore();
}

// 顶上的公式：“树₁”在画单棵树时变朱红，“树₄₀₀”在 400 棵长齐时变朱红
function topSegs3(t) {
  const S = HEAD_SIZE;
  const one = t >= B3.tree && t < B3.grow ? COLOR.acc : COLOR.ink;
  // 刚从第二段接过来时“树₄₀₀”还是朱红，开始画单棵树时才变黑
  const last = t < B3.tree || t >= B3.gridEnd - 0.1 ? COLOR.acc : COLOR.ink;
  const sub = (text, color) => ({ ...num(text, S * 0.6, color), dy: S * 0.18 });
  return [num("ln ", S), disp("k", S), num(" = ", S), disp("树", S, one), sub("1", one), num(" + ", S),
    disp("树", S), sub("2", COLOR.ink), num(" + … + ", S), disp("树", S, last), sub("400", last)];
}

function drawTopFormula3(ctx, t) {
  const fly = ease.inOutCubic(ramp(t, B3.s10 + 0.1, B3.s10 + 0.9));
  const segs = topSegs3(t);
  const width = measureSegs(ctx, segs);
  const scale = lerp(1, TOP_SIZE / HEAD_SIZE, fly);
  const x = lerp(COL, W / 2 - (width * TOP_SIZE) / HEAD_SIZE / 2, fly);
  const y = lerp(HEADER_Y, TOP_Y, fly);
  // 镜 11 开头升出去
  const exit = ramp(t, B3.s11, B3.s11 + 0.3);
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(scale, scale);
  // “树₁”“树₄₀₀”变色的那一刻顶一下
  const pop = 1 + 0.05 * (kick(t, B3.tree) + kick(t, B3.gridEnd - 0.1));
  ctx.translate(width / 2, -S_HALF3);
  ctx.scale(pop, pop);
  ctx.translate(-width / 2, S_HALF3);
  riseSegs(ctx, segs, 0, 0, 1, exit);
  ctx.restore();
}
const S_HALF3 = 15;

// ---------- 镜 10：单棵树 ----------

// 节点上的字：按冻结模型第 1 棵树的真实分叉写
function nodeLabels3() {
  const tr = DATA.tree;
  return {
    root: `上架满 ${tr.root.threshold.toFixed(1)} 年？`,
    // 价格在 0.495 美元处切开：一边是免费游戏，一边是付费的
    left: "免费？",
    right: `Steam 内购买 > ${Math.round(tr.right.threshold * 100)}%？`,
  };
}

function nodeBox3(ctx, text, x, y, at, hiAt) {
  const age = t_now - at;
  if (age <= 0) return;
  const segs = [disp(text, 34, COLOR.ink)];
  const w = measureSegs(ctx, segs) + 52;
  const h = 72;
  const s = 0.6 + 0.4 * spring(age, 3, 0.55);
  const hi = hiAt === undefined ? 0 : kick(t_now, hiAt);
  ctx.save();
  ctx.globalAlpha *= ramp(t_now, at, at + 0.08);
  ctx.translate(x, y);
  ctx.scale(s * (1 + 0.08 * hi), s * (1 + 0.08 * hi));
  ctx.fillStyle = COLOR.bgTop;
  ctx.strokeStyle = hi > 0.05 ? COLOR.acc : COLOR.ink;
  ctx.lineWidth = 2.5;
  roundRect(ctx, -w / 2, -h / 2, w, h, 12);
  ctx.fill();
  ctx.stroke();
  drawSegs(ctx, [disp(text, 34, hi > 0.05 ? COLOR.acc : COLOR.ink)], -w / 2 + 26, 12);
  ctx.restore();
}

function drawBigTree3(ctx, t) {
  if (t < B3.tree) return;
  // 念到“四百棵树”时整棵树缩成小格子里的第一棵
  const shrink = ease.inOutCubic(ramp(t, B3.many, B3.many + 0.55));
  if (shrink >= 1) return;
  const cell0 = { x: GRID3.x + GRID3.cell / 2, y: GRID3.y + GRID3.cell / 2 };
  const R = TREE3.root;
  const s = lerp(1, 0.025, shrink);
  ctx.save();
  ctx.translate(lerp(R.x, cell0.x, shrink), lerp(R.y + 150, cell0.y, shrink));
  ctx.scale(s, s);
  ctx.translate(-R.x, -(R.y + 150));
  ctx.globalAlpha = 1 - ease.inExpo(ramp(t, B3.many + 0.3, B3.many + 0.55));

  const L = nodeLabels3();
  const edge = (a, b, at) => growLine(ctx, [[a.x, a.y + 36], [b.x, b.y - 36]], ease.outQuint(ramp(t, at, at + 0.35)),
    { color: COLOR.ink, width: 2.5 });
  edge(R, TREE3.left, B3.tree + 0.25);
  edge(R, TREE3.right, B3.tree + 0.3);
  TREE3.leaves.forEach((leaf, i) => {
    const parent = i < 2 ? TREE3.left : TREE3.right;
    const at = B3.split + 0.1 + i * 0.07;
    growLine(ctx, [[parent.x, parent.y + 36], [leaf.x, leaf.y - 10]], ease.outQuint(ramp(t, at, at + 0.35)), { color: COLOR.ink, width: 2.5 });
    // 下面还在接着分：每个点下面再伸出两根渐淡的短线
    const p = ease.outQuint(ramp(t, at + 0.25, at + 0.6));
    if (p > 0) {
      ctx.save();
      ctx.fillStyle = COLOR.ink;
      ctx.beginPath();
      ctx.arc(leaf.x, leaf.y, 8 * spring(t - at - 0.25, 3, 0.55), 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
      for (const dx of [-36, 36]) {
        growLine(ctx, [[leaf.x, leaf.y + 10], [leaf.x + dx, leaf.y + 70]], p, { color: COLOR.dim, width: 2, dash: [5, 6], alpha: 0.7 });
      }
    }
  });
  nodeBox3(ctx, L.root, R.x, R.y, B3.tree, B3.age);
  nodeBox3(ctx, L.left, TREE3.left.x, TREE3.left.y, B3.split - 0.15, B3.price);
  nodeBox3(ctx, L.right, TREE3.right.x, TREE3.right.y, B3.split - 0.05);
  ctx.restore();
}

// ---------- 镜 10：400 棵小树和估对比例曲线 ----------

// 第 i 棵小树长出来的时刻：开头一棵一棵看得清，越往后越快
function treeTime3(i) {
  return lerp(B3.grow, B3.gridEnd, Math.pow(i / 399, 0.6));
}

function treesShown3(t) {
  if (t < B3.grow) return t >= B3.many + 0.5 ? 1 : 0;
  // treeTime3 的反函数
  return Math.min(400, 1 + Math.floor(399 * Math.pow(ramp(t, B3.grow, B3.gridEnd), 1 / 0.6)));
}

// 一棵小树：根节点分两叉，每叉再分两叉，和上面的大树同一个形状
function smallTree3(ctx, x, y, color) {
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 1.8;
  ctx.beginPath();
  ctx.moveTo(x, y - 9);
  ctx.lineTo(x - 6, y);
  ctx.lineTo(x - 9, y + 9);
  ctx.moveTo(x - 6, y);
  ctx.lineTo(x - 3, y + 9);
  ctx.moveTo(x, y - 9);
  ctx.lineTo(x + 6, y);
  ctx.lineTo(x + 3, y + 9);
  ctx.moveTo(x + 6, y);
  ctx.lineTo(x + 9, y + 9);
  ctx.stroke();
  for (const [dx, dy, r] of [[0, -9, 3], [-6, 0, 2.4], [6, 0, 2.4]]) {
    ctx.beginPath();
    ctx.arc(x + dx, y + dy, r, 0, Math.PI * 2);
    ctx.fill();
  }
}

function sceneExit3(t) {
  return ease.inExpo(ramp(t, B3.s11, B3.s11 + 0.35));
}

function drawGrid3(ctx, t) {
  const shown = treesShown3(t);
  if (shown <= 0) return;
  const exit = sceneExit3(t);
  if (exit >= 1) return;
  ctx.save();
  ctx.globalAlpha = 1 - exit;
  for (let i = 0; i < shown; i++) {
    const x = GRID3.x + (i % GRID3.cols) * GRID3.cell + GRID3.cell / 2;
    const y = GRID3.y + Math.floor(i / GRID3.cols) * GRID3.cell + GRID3.cell / 2;
    // 刚长出来的是朱红，随后落成黑
    const at = i === 0 ? B3.many + 0.5 : treeTime3(i);
    const fresh = Math.exp(-Math.max(0, t - at) / 0.25);
    ctx.globalAlpha = (1 - exit) * (0.55 + 0.45 * fresh);
    smallTree3(ctx, x, y, fresh > 0.5 ? COLOR.acc : COLOR.ink);
  }
  ctx.restore();
}

function curveXY3(n, rate) {
  return [lerp(CURVE3.x0, CURVE3.x1, n / 400), lerp(CURVE3.yBottom, CURVE3.yTop, (rate - CURVE3.lo) / (CURVE3.hi - CURVE3.lo))];
}

function drawCurve3(ctx, t) {
  const axis = ease.outQuint(ramp(t, B3.many, B3.many + 0.5));
  if (axis <= 0) return;
  const exit = sceneExit3(t);
  if (exit >= 1) return;
  ctx.save();
  ctx.globalAlpha = 1 - exit;
  // 横轴：树的棵数
  growLine(ctx, [[CURVE3.x0, CURVE3.yBottom + 40], [CURVE3.x1, CURVE3.yBottom + 40]], axis, { color: COLOR.dim, width: 2, cap: "butt" });
  const labels = ramp(t, B3.many + 0.2, B3.many + 0.6);
  riseSegs(ctx, [num("0", 26, COLOR.dim)], CURVE3.x0, CURVE3.yBottom + 80, labels, 0, "center");
  riseSegs(ctx, [num("400", 26, COLOR.dim), disp(" 棵", 22, COLOR.dim)], CURVE3.x1, CURVE3.yBottom + 80, labels, 0, "center");

  // 曲线跟着小树一起长：长到第几棵树，就画到第几棵
  const n = treesShown3(t) - 1;
  const pts = DATA.curve.filter(([k]) => k <= n).map(([k, r]) => curveXY3(k, r));
  if (t >= B3.many + 0.5 && pts.length > 0) {
    if (pts.length > 1) growLine(ctx, pts, 1, { color: COLOR.acc, width: 4.5 });
    const [hx, hy] = pts[pts.length - 1];
    ctx.fillStyle = COLOR.acc;
    ctx.beginPath();
    ctx.arc(hx, hy, 7, 0, Math.PI * 2);
    ctx.fill();
  }
  // 起点就是固定 k（0 棵树时人人都估成平均值），终点是树模型的成绩
  const [sx, sy] = curveXY3(0, DATA.curve[0][1]);
  const startLabel = [num((DATA.methods.fixed.hit_rate * 100).toFixed(1), 40, COLOR.dim), num("%", 24, COLOR.dim)];
  pill(ctx, startLabel, sx + 70, sy + 50, B3.many + 0.55, B3.s11 + 1);
  const last = DATA.curve[DATA.curve.length - 1];
  const [ex, ey] = curveXY3(last[0], last[1]);
  const endLabel = [num((DATA.methods.tree.hit_rate * 100).toFixed(1), 52, COLOR.acc), num("%", 30, COLOR.acc)];
  pill(ctx, endLabel, ex - 50, ey - 50, B3.gridEnd, B3.s11 + 1);
  ctx.restore();
}

// ---------- 镜 11：五个来源拼成样本表 ----------

// 镜 11 的表铺满画面，五个来源的框正好盖在各自负责的列上面；镜 12 缩回中间，给“考试”和款数让位
const WIDE3 = { x0: 160, x1: 1760, y0: 340, head: 70, y1: 860 };
const NARROW3 = { x0: 700, x1: 1440, y0: 300, head: 64, y1: 820 };
const GROUPS3 = ["年龄", "标签", "评测数", "好评率", "购买占比", "语言", "时长", "价格", "玩家数"];
const ANSWER3 = 8;  // 第 9 列是答案，和前面 8 组特征隔开
// 每个来源：念到哪个词出来、负责哪几组、爬回多少（export_data.py 的 sources）、单位
const SOURCES3 = [
  { name: "商店页", word: "商店页", groups: [0, 1], key: "store", unit: "款" },
  { name: "评测计数", word: "评测", groups: [2, 3, 4, 5], key: "review_queries", unit: "次" },
  { name: "评测抽样", word: "评测", delay: 0.18, groups: [6], key: "reviews", unit: "条" },
  { name: "价格历史", word: "价格历史", groups: [7], key: "price_changes", unit: "条" },
  { name: "玩家数表", word: "玩家数表", groups: [ANSWER3], key: "players", unit: "款" },
];

// 表此刻的位置和 9 列的左右边：答案列比特征列宽一点，中间隔一道缝
function table3(t) {
  const k = ease.inOutCubic(ramp(t, B3.s12, B3.s12 + 0.6));
  const g = {};
  for (const key of ["x0", "x1", "y0", "head", "y1"]) g[key] = lerp(WIDE3[key], NARROW3[key], k);
  const gap = 18 * (g.x1 - g.x0) / (WIDE3.x1 - WIDE3.x0);
  const fw = (g.x1 - g.x0 - gap) / 9.2;
  g.cols = [];
  for (let i = 0; i < 8; i++) g.cols.push({ l: g.x0 + i * fw, r: g.x0 + (i + 1) * fw });
  g.cols.push({ l: g.x0 + 8 * fw + gap, r: g.x1 });
  g.narrow = k;
  return g;
}

// 爬回来的数量：上万的按“万”写
function bigCount3(n) {
  if (n < 1e5) return String(Math.round(n));
  const w = n / 1e4;
  return (w < 100 ? w.toFixed(1) : String(Math.round(w))) + " 万";
}

function sourceAt3(src) {
  return word(11, src.word) + (src.delay || 0);
}

function drawSources3(ctx, t, g) {
  const exit = ease.inExpo(ramp(t, B3.s12, B3.s12 + 0.35));
  if (exit >= 1) return;
  for (const src of SOURCES3) {
    const at = sourceAt3(src);
    const age = t - at;
    if (age <= 0) continue;
    const l = g.cols[src.groups[0]].l + 6;
    const r = g.cols[src.groups[src.groups.length - 1]].r - 6;
    const cx = (l + r) / 2;
    const isAnswer = src.groups[0] === ANSWER3;
    const color = isAnswer ? COLOR.acc : COLOR.ink;
    const s = (0.6 + 0.4 * spring(age, 3, 0.55)) * (1 - 0.3 * exit);
    ctx.save();
    ctx.globalAlpha = ramp(t, at, at + 0.08) * (1 - exit);
    ctx.translate(cx, 205);
    ctx.scale(s, s);
    ctx.fillStyle = COLOR.bgTop;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    roundRect(ctx, l - cx, -55, r - l, 110, 12);
    ctx.fill();
    ctx.stroke();
    const name = [disp(src.name, 28, color)];
    drawSegs(ctx, name, -measureSegs(ctx, name) / 2, -10);
    // 数量从 0 滚上去
    const n = DATA.sources[src.key] * ease.outExpo(ramp(t, at + 0.1, at + 0.8));
    const amount = [num(bigCount3(n).replace(" 万", ""), 30, color)];
    if (n >= 1e5) amount.push(disp(" 万", 22, color));
    amount.push(disp(" " + src.unit, 22, color));
    drawSegs(ctx, amount, -measureSegs(ctx, amount) / 2, 34);
    ctx.restore();

    // 框下伸出线，落进它负责的每一组
    src.groups.forEach((gi, j) => {
      const p = ease.outQuint(ramp(t, at + 0.25 + j * 0.05, at + 0.6 + j * 0.05));
      const gx = (g.cols[gi].l + g.cols[gi].r) / 2;
      growLine(ctx, [[cx, 262], [gx, g.y0 - 8]], p, { color, width: 2.2, head: 5, from: exit, alpha: (1 - exit) * 0.8 });
    });
  }
}

// 第 gi 组什么时候被它的来源“填上”
function fedAt3(gi) {
  for (const src of SOURCES3) {
    const j = src.groups.indexOf(gi);
    if (j >= 0) return sourceAt3(src) + 0.55 + j * 0.05;
  }
  return Infinity;
}

// 表的第 i 份（镜 12 横切成 5 份）此刻上下挪了多少
function sliceShift3(i, t) {
  const open = ease.outQuint(ramp(t, B3.cut, B3.cut + 0.45)) * (1 - ease.inOutCubic(ramp(t, B3.rejoin, B3.rejoin + 0.45)));
  // 第一份不动，免得挤进表头；往下每份多挪一点
  return i * 14 * open;
}

// 镜 12：考试的是第几份，轮流换一遍
function testSlice3(t) {
  if (t < B3.rotate) return 0;
  const step = (B3.rejoin - B3.rotate) / 5;
  return Math.min(4, Math.floor((t - B3.rotate) / step));
}

function drawTable3(ctx, t, g) {
  const outline = ease.outQuint(ramp(t, B3.s11 + 0.2, B3.s11 + 0.9));
  if (outline <= 0) return;
  const { x0, x1, y0, y1, head } = g;
  const bodyTop = y0 + head;
  const sliceH = (y1 - bodyTop) / 5;
  const colFade = 1 - ramp(t, B3.s12, B3.s12 + 0.4);  // 镜 12 起各列的底色退掉，只看横切的 5 份

  // 每组被来源填上：表头一格填色，整列从上往下刷一道底色
  g.cols.forEach((c, gi) => {
    const at = fedAt3(gi);
    const p = ease.outQuint(ramp(t, at, at + 0.45));
    if (p <= 0) return;
    const isAnswer = gi === ANSWER3;
    ctx.save();
    ctx.fillStyle = isAnswer ? COLOR.accFill : "rgba(28,27,25,0.06)";
    ctx.globalAlpha = colFade;
    ctx.fillRect(c.l, bodyTop, c.r - c.l, (y1 - bodyTop) * p);
    // 表头：答案是朱红实心，特征是浅黑；念到“八组特征”时 8 格从左到右闪一下
    const flash = gi < 8 ? kick(t, B3.groups + gi * 0.07) : 0;
    ctx.globalAlpha = 1;
    ctx.fillStyle = isAnswer ? COLOR.acc : `rgba(28,27,25,${0.12 + 0.75 * flash})`;
    ctx.fillRect(c.l + 3, y0 + 3, c.r - c.l - 6, (head - 6) * p);
    ctx.restore();
    // 组名：缩到镜 12 的小表时退掉
    const nameColor = isAnswer || flash > 0.5 ? COLOR.bgTop : COLOR.ink;
    ctx.save();
    ctx.globalAlpha = 1 - g.narrow;
    riseSegs(ctx, [disp(GROUPS3[gi], 24, nameColor)], (c.l + c.r) / 2, y0 + head / 2 + 9, ramp(t, at + 0.1, at + 0.45), 0, "center");
    ctx.restore();
  });

  // 镜 12：5 份的底色。训练的淡黑，考试的朱红
  const split = ramp(t, B3.cut, B3.cut + 0.3) * (1 - ramp(t, B3.rejoin, B3.rejoin + 0.3));
  if (split > 0) {
    const test = testSlice3(t);
    for (let i = 0; i < 5; i++) {
      const top = bodyTop + i * sliceH + sliceShift3(i, t);
      const isTest = i === test && t >= B3.rotate;
      ctx.save();
      ctx.globalAlpha = split;
      ctx.fillStyle = isTest ? COLOR.accFill : "rgba(28,27,25,0.07)";
      for (const [a, b] of [[x0, g.cols[7].r], [g.cols[ANSWER3].l, x1]]) {
        ctx.fillRect(a, top, b - a, sliceH);
        if (isTest) {
          ctx.strokeStyle = COLOR.acc;
          ctx.lineWidth = 3;
          ctx.strokeRect(a, top, b - a, sliceH);
        }
      }
      ctx.restore();
    }
    // “考试”跟着朱红的那一份走，“训练”标在表的左边
    if (t >= B3.rotate) {
      const top = bodyTop + test * sliceH + sliceShift3(test, t);
      ctx.save();
      ctx.globalAlpha = split;
      riseSegs(ctx, [disp("考试", 30, COLOR.acc)], x1 + 24, top + sliceH / 2 + 11, ramp(t, B3.rotate, B3.rotate + 0.3));
      riseSegs(ctx, [disp("训练", 30, COLOR.dim)], x0 - 24, bodyTop + (y1 - bodyTop) / 2 + 11, ramp(t, B3.rotate + 0.1, B3.rotate + 0.4), 0, "right");
      ctx.restore();
    }
  }

  // 列线：从表头往下长；答案列和特征之间的缝不画线
  g.cols.forEach((c, gi) => {
    if (gi === 0) return;
    const p = ease.outQuint(ramp(t, B3.s11 + 0.35 + gi * 0.03, B3.s11 + 0.9 + gi * 0.03));
    if (gi !== ANSWER3) growLine(ctx, [[c.l, y0], [c.l, y1 + sliceShift3(4, t)]], p, { color: COLOR.line, width: 1.5, cap: "butt", alpha: colFade });
  });
  // 行线：念到“样本表”时从左往右扫出来，切开时跟着各自那一份走
  for (let r = 1; r < 20; r++) {
    if (r % 4 === 0) continue;
    const i = Math.floor(r / 4);
    const y = bodyTop + r * (sliceH / 4) + sliceShift3(i, t);
    const p = ease.outQuint(ramp(t, B3.table + r * 0.02, B3.table + 0.5 + r * 0.02));
    for (const [a, b] of [[x0, g.cols[7].r], [g.cols[ANSWER3].l, x1]]) {
      growLine(ctx, [[a, y], [b, y]], p, { color: COLOR.line, width: 1.5, cap: "butt" });
    }
  }
  // 横线分两段画：特征表一段、答案列一段，不穿过中间的缝
  const across = (y, p, style) => {
    growLine(ctx, [[x0, y], [g.cols[7].r, y]], p, style);
    growLine(ctx, [[g.cols[ANSWER3].l, y], [x1, y]], p, style);
  };
  for (let i = 0; i < 5; i++) {
    const top = bodyTop + i * sliceH + sliceShift3(i, t);
    if (i > 0) across(top, ramp(t, B3.table, B3.table + 0.5), { color: COLOR.ink, width: 2, cap: "butt", alpha: 0.35 + 0.25 * split });
    if (i < 4 && split > 0) across(top + sliceH, 1, { color: COLOR.ink, width: 2, cap: "butt", alpha: 0.6 * split });
  }

  // 外框：特征 8 组一个框，答案列单独一个框
  const last = y1 + sliceShift3(4, t);
  const box = (a, b, color) => growLine(ctx, [[a, y0], [b, y0], [b, last], [a, last], [a, y0]], outline, { color, width: 3 });
  box(x0, g.cols[7].r, COLOR.ink);
  box(g.cols[ANSWER3].l, x1, COLOR.acc);
  across(bodyTop + sliceShift3(0, t), outline, { color: COLOR.ink, width: 2.5, cap: "butt" });

  // 念到“样本表”：表下方标出行数和列数，镜 12 切开前收起
  const size = [num(String(dotsM.length), 34), disp(" 行 × ", 26), num(String(DATA.features), 34), disp(" 列", 26)];
  pill(ctx, size, (x0 + x1) / 2, y1 + 50, B3.table + 0.2, B3.s12);
}

// 镜 12 最后：仍估错 3 倍以上的款数
function drawOff3(ctx, t) {
  const segs = [num(String(DATA.off3), BIG, COLOR.acc), disp(" 款", 40, COLOR.acc)];
  const x = NARROW3.x1 + 50;
  const y = (NARROW3.y0 + NARROW3.y1) / 2 + 40;
  let s = 1;
  if (t >= B3.off) s = 1 + 0.12 * (1 - spring(t - B3.off, 3.4, 0.45));
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(s, s);
  riseSegs(ctx, segs, 0, 0, ramp(t, B3.off, B3.off + 0.45));
  ctx.restore();
}

// ---------- 整段 ----------

function drawPart3(ctx, chart, t) {
  t_now = t;
  drawHandoff3(ctx, t);
  // 关键时刻整幅画面顶一下
  const punch = kick(t, B3.gridEnd) + kick(t, B3.off);
  ctx.save();
  ctx.translate(W / 2, H / 2);
  ctx.scale(1 + 0.012 * punch, 1 + 0.012 * punch);
  ctx.translate(-W / 2, -H / 2);
  drawBigTree3(ctx, t);
  drawGrid3(ctx, t);
  drawCurve3(ctx, t);
  const table = table3(t);
  drawSources3(ctx, t, table);
  drawTable3(ctx, t, table);
  drawOff3(ctx, t);
  ctx.restore();
  drawTopFormula3(ctx, t);
}

PARTS.push({ first: 10, last: 12, prepare: preparePart3, draw: drawPart3 });
