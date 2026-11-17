// 第四段：模型靠什么估 k（镜 13–16）
// 镜 13：第三段的样本表滑到左边当考题，右边画出空的成绩表，顶行是不打乱时的成绩；“年龄”一列的格子在游戏之间互换。
// 镜 14：顶行的数字滚成打乱年龄后的成绩，落进第 1 行，年龄列换回去；左边换成按上架年份的 k 中位数，标出 2013.11 评测上线。
// 镜 15：年龄图收起、考题表回来，其余 7 组按误差从大到小一组一组打乱、记分，前两组慢，后五组快。
// 镜 16：考题表退场，成绩表展开成左右两栏：每组一条线段从“不打乱”画到打乱后的成绩，两栏各有一条固定 k 的虚线。
// 数字都从 data.json 的 importance、cells、k_by_year 读。变量都带 4 结尾。

let B4 = null;
let CYC4 = null;   // 8 组各自打乱、记分的时刻
let PERM4 = null;  // 每列格子打乱后去哪一行

const ROWS4 = 20;
const LEFT4 = { x0: 100, x1: 1000, y0: 250, head: 64, y1: 850 };  // 考题表停在左边
// 成绩表（镜 13–15）
const SC4 = { nameX: 1100, errC: 1500, hitC: 1720, headY: 292, baseY: 356, noteY: 388, sepY: 414, slot0: 474, step: 54, x1: 1830 };
// 两栏图（镜 16）：误差、估对比例都是往右越差，从“不打乱”的竖线画到打乱后的值，到固定 k 的虚线为止
const CH4 = { nameX: 190, headY: 300, baseY: 388, row0: 484, step: 56, errB: 470, errF: 1000, hitB: 1240, hitF: 1770, lineTop: 432, lineBot: 900 };
// 镜 14 的年份图
const YEAR4 = { x0: 150, x1: 1000, yBase: 810, yTop: 310, kMax: 330 };
const LAUNCH4 = 2013 + 10 / 12;  // 2013 年 11 月评测上线
// 组的 id → 考题表的第几列（和 part3.js 的 GROUPS3 同一个顺序）、成绩表上的名字
const NUM_SIZE4 = 38;

function preparePart4(data) {
  B4 = buildBeats4();
  CYC4 = buildCycles4();
  PERM4 = [];
  for (let c = 0; c < 8; c++) PERM4.push(derangement4(c));
}

function buildBeats4() {
  const b = { s13: shot(13).start, s14: shot(14).start, s15: shot(15).start, s16: shot(16).start };
  b.check = word(13, "检验");
  b.base = word(13, "不重新训练");
  b.test = word(13, "考题");
  b.same = word(13, "同组特征");
  b.swap = word(13, "互换");
  b.retest = word(13, "重考");
  b.big = word(14, "影响最大");
  b.launch = word(14, "评测 2013");
  b.month = word(14, "11 月上线");
  b.before = word(14, "此前");
  b.older = word(14, "越老");
  b.steam = word(15, "Steam");
  b.price = word(15, "价格");
  b.keys = word(15, "激活码");
  b.up = word(16, "误差均增大");
  b.age = word(16, "游戏年龄");
  b.buy = word(16, "购买渠道");
  b.price16 = word(16, "价格");
  b.rest = word(16, "其余各组");
  return b;
}

// 一组从开始打乱到成绩落进表里：swap 格子互换，roll 顶行数字滚到打乱后的成绩，drop 落进自己那一行，back 格子换回去
function cycle4(a, d) {
  return { swap: a, sw: Math.min(0.5, 0.4 * d), roll: a + 0.3 * d, rd: Math.min(0.45, 0.3 * d),
    drop: a + 0.62 * d, dd: Math.min(0.45, 0.3 * d), back: a + 0.67 * d };
}

function buildCycles4() {
  const c = [];
  // 年龄：镜 13 念到“互换”时换，镜 14 开头滚出成绩，念到“影响最大”时落下
  c.push({ swap: B4.swap, sw: 0.55, roll: B4.s14 + 0.15, rd: 0.5, drop: B4.big, dd: 0.45, back: B4.big + 0.1 });
  c.push(cycle4(B4.steam, B4.price - B4.steam));
  c.push(cycle4(B4.price, 1.3));
  const step = 0.72;
  for (let i = 3; i < 8; i++) c.push(cycle4(B4.keys + 0.45 + (i - 3) * step, step));
  return c;
}

// 第 c 列的打乱顺序：每一格都换到别的行（没有原地不动的），固定种子
function derangement4(c) {
  const rand = seededRandom(100 + c);
  for (;;) {
    const p = [...Array(ROWS4).keys()];
    for (let i = ROWS4 - 1; i > 0; i--) {
      const j = Math.floor(rand() * (i + 1));
      [p[i], p[j]] = [p[j], p[i]];
    }
    if (p.every((v, i) => v !== i)) return p;
  }
}

// 第 i 行（按误差排的第 i 组）是哪一组、在考题表的第几列
function group4(i) {
  const g = DATA.importance.groups[i];
  const col = DATA.table_groups.indexOf(g.key);
  return { ...g, col, name: GROUPS3[col] };
}

// 两个颜色之间插值（p = 0 是 a，1 是 b）
function mix4(a, b, p) {
  const ca = [1, 3, 5].map((k) => parseInt(a.slice(k, k + 2), 16));
  const cb = [1, 3, 5].map((k) => parseInt(b.slice(k, k + 2), 16));
  return `rgb(${ca.map((v, k) => Math.round(lerp(v, cb[k], p))).join(",")})`;
}

// ---------- 考题表 ----------

// 表的位置：镜 13 开头从第三段停下的位置（NARROW3）滑到左边；列宽算法和 part3.js 的 table3 一样
function geom4(t) {
  const k = ease.inOutCubic(ramp(t, B4.s13, B4.s13 + 0.8));
  const g = {};
  for (const key of ["x0", "x1", "y0", "head", "y1"]) g[key] = lerp(NARROW3[key], LEFT4[key], k);
  const gap = 18 * (g.x1 - g.x0) / (WIDE3.x1 - WIDE3.x0);
  const fw = (g.x1 - g.x0 - gap) / 9.2;
  g.cols = [];
  for (let i = 0; i < 8; i++) g.cols.push({ l: g.x0 + i * fw, r: g.x0 + (i + 1) * fw });
  g.cols.push({ l: g.x0 + 8 * fw + gap, r: g.x1 });
  g.bodyTop = g.y0 + g.head;
  g.rowH = (g.y1 - g.bodyTop) / ROWS4;
  g.slide = k;
  return g;
}

// 第 c 列此刻打乱了多少：0 是原样，1 是换好了
function shuffled4(c, t) {
  const i = DATA.importance.groups.findIndex((g) => DATA.table_groups.indexOf(g.key) === c);
  if (i < 0) return 0;
  const cy = CYC4[i];
  return ease.inOutCubic(ramp(t, cy.swap, cy.swap + cy.sw)) - ease.inOutCubic(ramp(t, cy.back, cy.back + cy.sw));
}

// 考题表此刻让位了多少：镜 14 让给年份图，镜 15 回来，镜 16 退场
function tableAway4(t) {
  const chart = ease.inOutCubic(ramp(t, B4.launch - 0.35, B4.launch)) * (1 - ease.inOutCubic(ramp(t, B4.s15 + 0.25, B4.s15 + 0.65)));
  const end = ease.inOutCubic(ramp(t, B4.s16, B4.s16 + 0.45));
  return Math.max(chart, end);
}

function drawTable4(ctx, t) {
  const away = tableAway4(t);
  if (away >= 1) return;
  const g = geom4(t);
  const { x0, x1, y0, y1, bodyTop, rowH } = g;
  ctx.save();
  ctx.globalAlpha = 1 - away;
  ctx.translate(-80 * ease.inCubic(away), 0);

  // 表头：特征浅黑、答案朱红；正在打乱的那一组变朱红
  g.cols.forEach((c, gi) => {
    const isAnswer = gi === ANSWER3;
    const q = gi < 8 ? shuffled4(gi, t) : 0;
    ctx.fillStyle = isAnswer ? COLOR.acc : `rgba(28,27,25,${0.12 * (1 - q)})`;
    ctx.fillRect(c.l + 3, y0 + 3, c.r - c.l - 6, g.head - 6);
    if (q > 0) {
      ctx.fillStyle = COLOR.accFill.replace("0.18", String(0.9 * q));
      ctx.fillRect(c.l + 3, y0 + 3, c.r - c.l - 6, g.head - 6);
    }
    const nameColor = isAnswer || q > 0.5 ? COLOR.bgTop : COLOR.ink;
    riseSegs(ctx, [disp(GROUPS3[gi], 22, nameColor)], (c.l + c.r) / 2, y0 + g.head / 2 + 8,
      ramp(t, B4.s13 + 0.5 + gi * 0.03, B4.s13 + 0.9 + gi * 0.03), 0, "center");
  });

  // 格子里的小条：这款游戏这一列在 9623 款里排第几（越长越大）。打乱时这一列的小条换到别的行去
  g.cols.forEach((c, gi) => {
    const grow = ease.outQuint(ramp(t, B4.s13 + 0.6 + gi * 0.05, B4.s13 + 1.05 + gi * 0.05));
    if (grow <= 0) return;
    const q = gi < 8 ? shuffled4(gi, t) : 0;
    const cw = c.r - c.l;
    // 小条只在自己那一列里动，换的路上不跑出表格
    ctx.save();
    ctx.beginPath();
    ctx.rect(c.l + 2, bodyTop, cw - 4, g.y1 - bodyTop);
    ctx.clip();
    for (let r = 0; r < ROWS4; r++) {
      const v = DATA.cells[r][gi];
      const to = gi < 8 ? PERM4[gi][r] : r;
      const y = bodyTop + (lerp(r, to, q) + 0.5) * rowH;
      // 换的路上左右错开一点，看得出是交错着换过去的
      const len = (cw - 20) * (0.12 + 0.88 * v) * grow;
      const dx = Math.sin(Math.PI * q) * (r % 2 ? 1 : 0) * Math.min(cw * 0.25, cw - 20 - len);
      ctx.fillStyle = gi === ANSWER3 ? COLOR.acc : q > 0.02 ? COLOR.acc : COLOR.ink;
      ctx.globalAlpha = (1 - away) * (gi === ANSWER3 ? 0.55 : q > 0.02 ? 0.85 : 0.45);
      roundRect(ctx, c.l + 10 + dx, y - 4.5, len, 9, 4.5);
      ctx.fill();
    }
    ctx.restore();
    ctx.globalAlpha = 1 - away;
  });

  // 行线；第三段切 5 份时留下的深色线在滑过来的路上淡成普通行线
  for (let r = 1; r < ROWS4; r++) {
    const y = bodyTop + r * rowH;
    for (const [a, b] of [[x0, g.cols[7].r], [g.cols[ANSWER3].l, x1]]) {
      growLine(ctx, [[a, y], [b, y]], 1, { color: COLOR.line, width: 1.5, cap: "butt" });
      if (r % 4 === 0) growLine(ctx, [[a, y], [b, y]], 1, { color: COLOR.ink, width: 2, cap: "butt", alpha: 0.35 * (1 - g.slide) });
    }
  }
  // 列线：第三段收起了，滑到左边时重新长出来
  g.cols.forEach((c, gi) => {
    if (gi === 0 || gi === ANSWER3) return;
    const p = ease.outQuint(ramp(t, B4.s13 + 0.4 + gi * 0.03, B4.s13 + 0.9 + gi * 0.03));
    growLine(ctx, [[c.l, y0], [c.l, y1]], p, { color: COLOR.line, width: 1.5, cap: "butt" });
  });
  // 外框：特征一个框，答案列一个框，和第三段一样
  const box = (a, b, color) => growLine(ctx, [[a, y0], [b, y0], [b, y1], [a, y1], [a, y0]], 1, { color, width: 3 });
  box(x0, g.cols[7].r, COLOR.ink);
  box(g.cols[ANSWER3].l, x1, COLOR.acc);
  for (const [a, b] of [[x0, g.cols[7].r], [g.cols[ANSWER3].l, x1]]) {
    growLine(ctx, [[a, bodyTop], [b, bodyTop]], 1, { color: COLOR.ink, width: 2.5, cap: "butt" });
  }
  // 念到“考题”：表上方标一下，这张表是拿来考的那一份
  riseSegs(ctx, [disp("考题", 30, COLOR.acc)], x0, y0 - 26, ramp(t, B4.test, B4.test + 0.35));
  ctx.restore();
}

// 第三段最后的“852 款”：镜 13 开头升出去
function drawOffExit4(ctx, t) {
  const exit = ramp(t, B4.s13, B4.s13 + 0.3);
  if (exit >= 1) return;
  const segs = [num(String(DATA.off3), BIG, COLOR.acc), disp(" 款", 40, COLOR.acc)];
  riseSegs(ctx, segs, NARROW3.x1 + 50, (NARROW3.y0 + NARROW3.y1) / 2 + 40, 1, exit);
}

// ---------- 成绩表 → 两栏图 ----------

function errX4(v) {
  const I = DATA.importance;
  return lerp(CH4.errB, CH4.errF, (v - I.baseline.rmse) / (I.fixed.rmse - I.baseline.rmse));
}
function hitX4(v) {
  const I = DATA.importance;
  return lerp(CH4.hitB, CH4.hitF, (I.baseline.hit - v) / (I.baseline.hit - I.fixed.hit));
}

function errSegs4(v, color, size = NUM_SIZE4) {
  return [num(v.toFixed(3), size, color)];
}
function hitSegs4(v, color, size = NUM_SIZE4) {
  return [num((v * 100).toFixed(1), size, color), num("%", size * 0.62, color)];
}

// 镜 16 两栏图展开到哪了
function morph4(t) {
  return ease.inOutCubic(ramp(t, B4.s16 + 0.15, B4.s16 + 0.85));
}

// 一行：名字、误差、估对比例。errX / hitX 是数字的中心
function drawRow4(ctx, name, nameColor, err, hit, numColor, y, x, enter = 1, exit = 0, pulse = 0) {
  // pulse：名字顶一下（只放大名字，数字不动）
  ctx.save();
  ctx.translate(x.name, y);
  ctx.scale(1 + 0.1 * pulse, 1 + 0.1 * pulse);
  riseSegs(ctx, [disp(name, 30, nameColor)], 0, 0, enter, exit);
  ctx.restore();
  const e = errSegs4(err, numColor);
  const h = hitSegs4(hit, numColor);
  riseSegs(ctx, e, x.err, y, enter, exit, "center");
  riseSegs(ctx, h, x.hit, y, enter, exit, "center");
}

// 第 i 组的那一行此刻是什么颜色：刚落下时朱红，下一组落下后变黑；镜 16 念到前三组时重新变朱红
function rowColor4(i, t) {
  if (t >= B4.s16) {
    const hiAt = [B4.age, B4.buy, B4.price16][i];
    return hiAt !== undefined && t >= hiAt ? COLOR.acc : COLOR.ink;
  }
  const next = i < 7 ? CYC4[i + 1].drop : B4.s16;
  return mix4(COLOR.acc, COLOR.ink, ramp(t, next, next + 0.4));
}

function drawScores4(ctx, t) {
  const I = DATA.importance;
  const m = morph4(t);
  const frame = ramp(t, B4.check, B4.check + 0.5);
  if (frame <= 0) return;

  // 栏名：表头的小灰字，展开成两栏图的标题
  const heads = [["误差", SC4.errC, (CH4.errB + CH4.errF) / 2], ["估对比例", SC4.hitC, (CH4.hitB + CH4.hitF) / 2]];
  for (const [text, a, b] of heads) {
    const size = lerp(26, 32, m);
    riseSegs(ctx, [disp(text, size, mix4(COLOR.dim, COLOR.ink, m))], lerp(a, b, m), lerp(SC4.headY, CH4.headY, m), frame, 0, "center");
  }
  // 顶行下的分隔线、8 个空位的底线：展开时淡掉
  ctx.save();
  ctx.globalAlpha = 1 - m;
  growLine(ctx, [[SC4.nameX - 10, SC4.sepY], [SC4.x1, SC4.sepY]], ease.outQuint(frame), { color: COLOR.ink, width: 2, cap: "butt", alpha: 0.6 });
  for (let i = 0; i < 8; i++) {
    const y = SC4.slot0 + i * SC4.step + 18;
    const p = ease.outQuint(ramp(t, B4.check + 0.2 + i * 0.05, B4.check + 0.6 + i * 0.05));
    growLine(ctx, [[SC4.nameX - 10, y], [SC4.x1, y]], p, { color: COLOR.line, width: 1.5, cap: "butt" });
  }
  ctx.restore();

  // 两栏图的竖线：实线是不打乱，虚线是固定 k
  const lines = ease.outQuint(ramp(t, B4.s16 + 0.6, B4.s16 + 1.0));
  const fixed = ease.outQuint(ramp(t, B4.up + 0.7, B4.up + 1.1));
  for (const x of [CH4.errB, CH4.hitB]) growLine(ctx, [[x, CH4.lineTop], [x, CH4.lineBot]], lines, { color: COLOR.ink, width: 2.5, cap: "butt" });
  for (const x of [CH4.errF, CH4.hitF]) growLine(ctx, [[x, CH4.lineTop], [x, CH4.lineBot]], fixed, { color: COLOR.dim, width: 2.5, cap: "butt", dash: [10, 8] });
  if (fixed > 0) {
    riseSegs(ctx, [disp("固定 k", 24, COLOR.dim)], CH4.errF, CH4.baseY - 38, fixed, 0, "center");
    riseSegs(ctx, [disp("固定 k", 24, COLOR.dim)], CH4.hitF, CH4.baseY - 38, fixed, 0, "center");
    riseSegs(ctx, errSegs4(I.fixed.rmse, COLOR.dim, 32), CH4.errF, CH4.baseY, fixed, 0, "center");
    riseSegs(ctx, hitSegs4(I.fixed.hit, COLOR.dim, 32), CH4.hitF, CH4.baseY, fixed, 0, "center");
  }

  // 顶行：不打乱的成绩。某一组正在出成绩时让位，落下后回来
  // 先升出去，给打乱后的成绩腾地方；成绩落下后再从下面升回来
  let baseEnter = ramp(t, B4.base, B4.base + 0.4);
  let baseExit = 0;
  for (const cy of CYC4) {
    const leave = ramp(t, cy.roll, cy.roll + 0.15);
    const back = ramp(t, cy.drop + 0.05, cy.drop + 0.3);
    if (leave <= 0 || back >= 1) continue;
    if (back > 0) baseEnter = back;
    else baseExit = leave;
  }
  if (baseEnter > 0 && baseExit < 1) {
    ctx.save();
    const y = lerp(SC4.baseY, CH4.baseY, m);
    const x = { name: lerp(SC4.nameX, CH4.nameX, m), err: lerp(SC4.errC, CH4.errB, m), hit: lerp(SC4.hitC, CH4.hitB, m) };
    drawRow4(ctx, "不打乱", COLOR.ink, I.baseline.rmse, I.baseline.hit, COLOR.ink, y, x, baseEnter, baseExit);
    // 45.6% 是 5 种分折的平均，和镜 9 的 46.2%（平时那一种分折）不同，小字注明
    riseSegs(ctx, [cjk("5 种分折平均", 20, COLOR.dim)], x.name, lerp(SC4.noteY, CH4.baseY + 30, m), Math.min(baseEnter, ramp(t, B4.base + 0.2, B4.base + 0.6)), baseExit);
    ctx.restore();
  }

  // 8 组：在顶行滚出成绩，落进自己那一行；镜 16 展开成线段
  const grow = (i) => ease.outQuint(ramp(t, B4.up + i * 0.06, B4.up + 0.6 + i * 0.06));
  for (let i = 0; i < 8; i++) {
    const g = group4(i);
    const cy = CYC4[i];
    if (t < cy.roll) continue;
    const roll = ease.outExpo(ramp(t, cy.roll, cy.roll + cy.rd));
    const err = lerp(I.baseline.rmse, g.rmse, roll);
    const hit = lerp(I.baseline.hit, g.hit, roll);
    const fall = ease.outQuint(ramp(t, cy.drop, cy.drop + cy.dd));
    const slotY = SC4.slot0 + i * SC4.step;
    const tableY = lerp(SC4.baseY, slotY, fall);
    const y = lerp(tableY, CH4.row0 + i * CH4.step, m);
    const color = t < cy.drop ? COLOR.acc : rowColor4(i, t);

    // 镜 16：线段从不打乱的竖线长到打乱后的值，数字骑在线头上
    const p = grow(i);
    const eEnd = errX4(lerp(I.baseline.rmse, g.rmse, p));
    const hEnd = hitX4(lerp(I.baseline.hit, g.hit, p));
    if (m > 0 && p > 0) {
      for (const [a, b] of [[CH4.errB, eEnd], [CH4.hitB, hEnd]]) {
        growLine(ctx, [[a, y - 13], [b, y - 13]], 1, { color, width: 8, alpha: 0.85 });
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(b, y - 13, 9, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    const ew = measureSegs(ctx, errSegs4(g.rmse, color));
    const hw = measureSegs(ctx, hitSegs4(g.hit, color));
    const x = {
      name: lerp(SC4.nameX, CH4.nameX, m),
      err: lerp(SC4.errC, eEnd + 22 + ew / 2, m),
      hit: lerp(SC4.hitC, hEnd + 22 + hw / 2, m),
    };
    // 其余五组在念到“其余各组”时依次顶一下
    const pulse = i >= 3 ? kick(t, B4.rest + (i - 3) * 0.1) : kick(t, [B4.age, B4.buy, B4.price16][i]);
    drawRow4(ctx, g.name, color, err, hit, color, y, x, ramp(t, cy.roll + 0.08, cy.roll + 0.28), 0, pulse);
  }
}

// ---------- 镜 14：按上架年份的 k 中位数 ----------

function yearX4(year) {
  const first = DATA.k_by_year[0][0];
  const n = DATA.k_by_year.length;
  return lerp(YEAR4.x0, YEAR4.x1, (year - first) / n);
}
function kY4(k) {
  return lerp(YEAR4.yBase, YEAR4.yTop, k / YEAR4.kMax);
}

function drawYears4(ctx, t) {
  const enter = B4.launch + 0.05;
  if (t < enter) return;
  const exit = ease.inCubic(ramp(t, B4.s15, B4.s15 + 0.25));
  if (exit >= 1) return;
  ctx.save();
  ctx.globalAlpha = 1 - exit;
  const years = DATA.k_by_year;
  const step = (YEAR4.x1 - YEAR4.x0) / years.length;
  const bw = step * 0.6;

  growLine(ctx, [[YEAR4.x0, YEAR4.yBase], [YEAR4.x1, YEAR4.yBase]], ease.outQuint(ramp(t, enter, enter + 0.4)), { color: COLOR.dim, width: 2, cap: "butt" });
  riseSegs(ctx, [disp("k", 26, COLOR.dim), cjk(" 中位数", 22, COLOR.dim)], YEAR4.x0, YEAR4.yTop - 44, ramp(t, enter + 0.1, enter + 0.4));

  // 柱子：从左往右依次长；念到“此前”时评测上线以前的几年变朱红
  const before = ramp(t, B4.before, B4.before + 0.3);
  years.forEach(([year, k], i) => {
    const p = spring(t - (enter + 0.15 + i * 0.05), 2.6, 0.6);
    if (p <= 0) return;
    const cx = yearX4(year) + step / 2;
    const top = lerp(YEAR4.yBase, kY4(k), p);
    const old = year < LAUNCH4;  // 2013 年上架的大多在 11 月以前，也算评测上线以前
    ctx.fillStyle = old ? mix4(COLOR.ink, COLOR.acc, before) : COLOR.ink;
    ctx.globalAlpha = (1 - exit) * (old ? lerp(0.35, 0.8, before) : 0.35);
    ctx.fillRect(cx - bw / 2, top, bw, YEAR4.yBase - top);
    ctx.globalAlpha = 1 - exit;
  });
  // 年份只标头、尾和 2013
  for (const [year] of years) {
    if (![years[0][0], 2013, years[years.length - 1][0]].includes(year)) continue;
    riseSegs(ctx, [num(String(year), 24, COLOR.dim)], yearX4(year) + step / 2, YEAR4.yBase + 40, ramp(t, enter + 0.3, enter + 0.6), 0, "center");
  }

  // 2013.11 评测上线：一道竖线落下来
  // 柱子是整年的，竖线画在 2013 和 2014 两根柱子中间
  const lx = yearX4(Math.ceil(LAUNCH4));
  growLine(ctx, [[lx, YEAR4.yTop - 10], [lx, YEAR4.yBase]], ease.outQuint(ramp(t, B4.month, B4.month + 0.4)), { color: COLOR.acc, width: 3, cap: "butt" });
  riseSegs(ctx, [num("2013.11", 26, COLOR.acc), disp(" 评测上线", 24, COLOR.acc)], lx, YEAR4.yTop - 44, ramp(t, B4.month + 0.1, B4.month + 0.45), 0, "center");

  // 念到“越老”：头尾两年的 k 弹出来
  const [y0, k0] = years[0];
  const [y1, k1] = years[years.length - 1];
  pill(ctx, [num(String(Math.round(k0)), 40, COLOR.acc)], yearX4(y0) + step / 2, kY4(k0) - 30, B4.older, B4.s15);
  pill(ctx, [num(String(Math.round(k1)), 40, COLOR.ink)], yearX4(y1) + step / 2, kY4(k1) - 30, B4.older + 0.15, B4.s15);
  ctx.restore();
}

// ---------- 整段 ----------

function drawPart4(ctx, chart, t) {
  t_now = t;
  // 年龄的成绩落下、线段长齐时整幅画面顶一下
  const punch = kick(t, CYC4[0].drop) + kick(t, B4.up + 0.6 + 7 * 0.06);
  ctx.save();
  ctx.translate(W / 2, H / 2);
  ctx.scale(1 + 0.012 * punch, 1 + 0.012 * punch);
  ctx.translate(-W / 2, -H / 2);
  drawOffExit4(ctx, t);
  drawTable4(ctx, t);
  drawYears4(ctx, t);
  drawScores4(ctx, t);
  ctx.restore();
}

PARTS.push({ first: 13, last: 16, prepare: preparePart4, draw: drawPart4 });
