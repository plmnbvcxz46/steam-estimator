// 动效基础：缓动、弹簧、遮罩里升起的文字、生长的线、冲击。
// 每个函数只看传进来的时刻或进度，同一时刻画几遍结果都一样，逐帧录制不会抖。

// ---------- 配色和字体 ----------
// 颜色按“角色”取名，画面代码只用角色：
//   ink 主要的字和散点；dim 次要的字和坐标轴；line 网格、分档线；acc 当前这一步和核心结果
// 米白纸面配近黑的字，强调色是朱红：像印出来的图表，投影也亮。
// 强调色只用在“这一步”和核心结果上，一眼就能抓住
const COLOR = {
  bgTop: "#F6F2EA", bgBottom: "#ECE6DA", vignette: "rgba(90,70,40,0.10)",
  ink: "#1C1B19", dim: "#857E72", line: "#DDD5C7",
  acc: "#D9452B", accFill: "rgba(217,69,43,0.18)",
  subBg: "rgba(28,27,25,0.86)",     // 字幕的底板
  subInk: "#F6F2EA",
  pointAlpha: 0.22,                 // 散点平时的不透明度：纸面上点多了容易糊成一团
};
// body 小字和标签；display 标题、公式、单位；num 数字。中文用思源黑体，数字用 Inter
const FONT = { body: "NotoSC", display: "NotoSC", displayWeight: 700, num: "Inter", numWeight: 600 };
// 字体文件：family 名字 → 文件名和可用字重（文件放在构建目录的 fonts/ 里）
const FONT_FILES = {
  NotoSC: ["NotoSansSC.ttf", "100 900"],
  Inter: ["Inter.ttf", "100 900"],
};

// ---------- 时间和缓动 ----------

function clamp01(x) {
  return Math.max(0, Math.min(1, x));
}
// t 在 [a, b] 之间时从 0 走到 1，之前是 0，之后是 1
function ramp(t, a, b) {
  if (b <= a) return t >= a ? 1 : 0;
  return clamp01((t - a) / (b - a));
}
function lerp(a, b, p) {
  return a + (b - a) * p;
}

// 缓动曲线：把匀速的进度变成有快有慢的进度。
// 进场用 out（先快后慢，落得稳），退场用 in（先慢后快，走得干脆），这就是“顿挫”的来源
const ease = {
  outQuint: (p) => 1 - Math.pow(1 - p, 5),
  outExpo: (p) => (p >= 1 ? 1 : 1 - Math.pow(2, -10 * p)),
  inExpo: (p) => (p <= 0 ? 0 : Math.pow(2, 10 * p - 10)),
  inCubic: (p) => p * p * p,
  inOutCubic: (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
};

// 弹簧：从 0 冲向 1，冲过头一点再落定。zeta 越小冲得越多，freq 越大越快。
// 用公式直接算任意时刻的位置，不靠逐帧累加，所以单独渲染哪一帧都对
function spring(t, freq = 2.4, zeta = 0.5) {
  if (t <= 0) return 0;
  const w = 2 * Math.PI * freq;
  const wd = w * Math.sqrt(1 - zeta * zeta);
  return 1 - Math.exp(-zeta * w * t) * (Math.cos(wd * t) + ((zeta * w) / wd) * Math.sin(wd * t));
}

// 冲击：在 at 时刻猛地一顶再迅速回落，返回 0 到 1。用来让镜头在关键结果落地时“震”一下
function kick(t, at) {
  const d = t - at;
  if (d < 0) return 0;
  if (d < 0.05) return d / 0.05;
  return Math.exp(-(d - 0.05) * 9);
}

// 固定种子的伪随机数：同一个种子永远给同一串数
function seededRandom(seed) {
  let s = seed >>> 0;
  return function () {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

// ---------- 字 ----------

function setFont(ctx, family, size, weight = 400) {
  ctx.font = `${weight} ${size}px ${family}`;
}

// 一段字由几小段拼成，每段可以换字体和颜色，比如大号数字“39”后面跟中文“倍”。
// seg = {text, family, size, weight, color}；返回总宽
function measureSegs(ctx, segs) {
  let w = 0;
  for (const s of segs) {
    setFont(ctx, s.family, s.size, s.weight);
    w += ctx.measureText(s.text).width + (s.gap || 0);
  }
  return w;
}
// halo 为 true 时，先用底色描一圈字的边，再填字：字压在散点上也清楚
function drawSegs(ctx, segs, x, y, halo = false) {
  ctx.textBaseline = "alphabetic";
  for (const s of segs) {
    setFont(ctx, s.family, s.size, s.weight);
    if (halo) {
      ctx.strokeStyle = COLOR.bgTop;
      ctx.lineWidth = s.size * 0.28;
      ctx.lineJoin = "round";
      ctx.strokeText(s.text, x, y);
    }
    ctx.fillStyle = s.color;
    ctx.fillText(s.text, x, y);
    x += ctx.measureText(s.text).width + (s.gap || 0);
  }
}

// 遮罩里升起的一行字：字被限制在自己那一行的框里，从框下沿升上来；退场时继续往上升出框。
// enter、exit 是 0 到 1 的线性进度，这里加缓动。不是整行淡入，读起来更利落
function riseSegs(ctx, segs, x, y, enter, exit = 0, align = "left") {
  if (enter <= 0 || exit >= 1) return 0;
  const width = measureSegs(ctx, segs);
  const size = Math.max(...segs.map((s) => s.size));
  if (align === "center") x -= width / 2;
  if (align === "right") x -= width;
  const travel = size * 1.3;
  const dy = (1 - ease.outQuint(enter)) * travel - ease.inCubic(exit) * travel;
  ctx.save();
  ctx.beginPath();
  ctx.rect(x - 20, y - size * 1.05, width + 40, size * 1.4);
  ctx.clip();
  drawSegs(ctx, segs, x, y + dy);
  ctx.restore();
  return width;
}

// 常用的一段字：小字、标签
function cjk(text, size, color = COLOR.ink, weight = 500) {
  return { text, family: FONT.body, size, weight, color };
}
// 常用的一段字：标题、公式、大号数字后面的单位
function disp(text, size, color = COLOR.ink) {
  return { text, family: FONT.display, size, weight: FONT.displayWeight, color };
}
// 常用的一段字：大号数字
function num(text, size, color = COLOR.ink, weight = FONT.numWeight) {
  return { text, family: FONT.num, size, weight, color };
}

// 圆角矩形（字的底板、字幕底）
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

// ---------- 线 ----------

// 折线的总长和每段的累计长度
function polyLengths(points) {
  const acc = [0];
  for (let i = 1; i < points.length; i++) {
    const [x0, y0] = points[i - 1];
    const [x1, y1] = points[i];
    acc.push(acc[i - 1] + Math.hypot(x1 - x0, y1 - y0));
  }
  return acc;
}

// 生长的线：progress 从 0 到 1，线从起点长到终点；from 不为 0 时线从尾巴开始收（退场用）。
// head 给半径时，生长中的线头画一个圆点，像笔尖
function growLine(ctx, points, progress, opts = {}) {
  const from = opts.from || 0;
  if (progress <= from) return;
  const acc = polyLengths(points);
  const total = acc[acc.length - 1];
  const a = total * from;
  const b = total * Math.min(1, progress);

  // 找到 a、b 两个长度落在哪一段上，插值出端点
  function pointAt(d) {
    let i = 1;
    while (i < acc.length - 1 && acc[i] < d) i++;
    const seg = acc[i] - acc[i - 1] || 1;
    const f = (d - acc[i - 1]) / seg;
    return [lerp(points[i - 1][0], points[i][0], f), lerp(points[i - 1][1], points[i][1], f), i];
  }
  const [ax, ay, ai] = pointAt(a);
  const [bx, by, bi] = pointAt(b);

  ctx.save();
  ctx.strokeStyle = opts.color || COLOR.ink;
  ctx.lineWidth = opts.width || 3;
  ctx.lineCap = opts.cap || "round";
  ctx.lineJoin = "round";
  if (opts.alpha !== undefined) ctx.globalAlpha *= opts.alpha;
  if (opts.dash) ctx.setLineDash(opts.dash);
  ctx.beginPath();
  ctx.moveTo(ax, ay);
  for (let i = ai; i < bi; i++) ctx.lineTo(points[i][0], points[i][1]);
  ctx.lineTo(bx, by);
  ctx.stroke();
  if (opts.head && progress < 1) {
    ctx.setLineDash([]);
    ctx.fillStyle = opts.color || COLOR.ink;
    ctx.beginPath();
    ctx.arc(bx, by, opts.head, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

// 过几个点的平滑曲线（Catmull-Rom 插值），返回密集的折线点
function smoothThrough(points, steps = 14) {
  const out = [];
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(points.length - 1, i + 2)];
    for (let j = 0; j < steps; j++) {
      const u = j / steps;
      const u2 = u * u;
      const u3 = u2 * u;
      const f = (a, b, c, d) =>
        0.5 * (2 * b + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u2 + (-a + 3 * b - 3 * c + d) * u3);
      out.push([f(p0[0], p1[0], p2[0], p3[0]), f(p0[1], p1[1], p2[1], p3[1])]);
    }
  }
  out.push(points[points.length - 1]);
  return out;
}
