/* 从面板里抽出纯逻辑函数，在 Node 下跑断言。
   重点是 parseUsage —— 它决定「官方用量」页能不能正确解析平台响应。 */
const fs = require("fs");
const src = fs.readFileSync("_panel_check.js", "utf8");

/* 顶层函数声明都以行首的 "function "（或 "async function "）开始，据此切块 */
const chunks = src.split(/\n(?=(?:async )?function )/).slice(1);
const bodies = {};
for (const c of chunks) {
  const m = /^(?:async )?function\s+([A-Za-z0-9_$]+)/.exec(c);
  if (!m) continue;
  const name = m[1];
  // 截到下一个顶层分节注释或启动 IIFE 为止。
  // 注意分节注释有两种风格：`/* ---- 标题 ---- */` 和 `/* ==== 标题 ==== */`，
  // 漏掉后者会让一个函数块一路吞掉后面整段代码（包括其中的 const 声明）。
  const cut = c.search(/\n\(async function|\n\/\* [-=]{3,}/);
  bodies[name] = cut > 0 ? c.slice(0, cut) : c;
}

/* 另外 3 个是单行箭头函数常量 */
for (const line of src.split("\n")) {
  const m = /^const (esc|num|uid)\s*=.*;\s*$/.exec(line);
  if (m) bodies[m[1]] = line.trim();
}

const WANT = ["esc", "num", "money", "maskKey", "parseText", "extractToken", "uid",
              "parseUsage", "breakdown", "sumCost", "computeSpend",
              "normKey", "warnHits", "allTags",
              "deriveKey", "encryptBlob", "decryptBlob"];
const missing = WANT.filter(n => !bodies[n]);
if (missing.length) { console.error("抽不到函数:", missing); process.exit(1); }

// parseUsage 依赖的全局常量；S 是面板的全局状态，测试里用桩替换
const MODEL_LABEL = { "deepseek-v4-flash": "V4 Flash", "deepseek-v4-pro": "V4 Pro" };
globalThis.__S = { settings: { warnThreshold: 0 }, keys: [] };
// PBKDF2 迭代次数在测试里调小，否则每次派生要几百毫秒
const ctx = eval("(function(){ var S = globalThis.__S; var PBKDF2_ITER = 2000;" +
  "var b64 = function(buf){ return btoa(String.fromCharCode.apply(null, new Uint8Array(buf))); };" +
  "var unb64 = function(s){ return Uint8Array.from(atob(s), function(c){ return c.charCodeAt(0); }); };" +
  WANT.map(n => bodies[n]).join("\n") +
  "\nreturn {" + WANT.join(",") + "};})()");

/* ---------------- 断言框架 ---------------- */
let pass = 0, fail = 0;
function eq(label, got, want) {
  const g = JSON.stringify(got), w = JSON.stringify(want);
  if (g === w) { pass++; console.log("  ✓ " + label); }
  else { fail++; console.log("  ✗ " + label + "\n      得到 " + g + "\n      期望 " + w); }
}
function ok(label, cond) { cond ? (pass++, console.log("  ✓ " + label)) : (fail++, console.log("  ✗ " + label)); }

console.log("\n[1] parseText —— 各种导入格式");
let r = ctx.parseText(
  "sk-00000000000000000000000000000001\n" +
  "主力号,sk-00000000000000000000000000000002\n" +
  "sk-00000000000000000000000000000003,备用备注\n" +
  "# 这是注释，应该被忽略\n" +
  "\n" +
  "Bearer sk-00000000000000000000000000000004\n" +
  "垫脚石\t sk-00000000000000000000000000000005");
eq("解析出 5 个 Key", r.length, 5);
eq("第1个自动命名", r[0].name, "Key-1");
eq("逗号分隔的名称被识别", r[1].name, "主力号");
eq("Key 正确", r[1].key, "sk-00000000000000000000000000000002");
eq("Key,备注 形式", r[2].name, "备用备注");
eq("Bearer 前缀被剥掉", r[3].key, "sk-00000000000000000000000000000004");
ok("制表符分隔生效", r[4].key === "sk-00000000000000000000000000000005");
eq("注释行被跳过", r.filter(x => /注释/.test(x.name)).length, 0);

console.log("\n[2] maskKey —— 打码");
eq("长 Key 前7后4", ctx.maskKey("sk-1234567890abcdefghij"), "sk-1234…ghij");
eq("短 Key 全遮", ctx.maskKey("sk-short"), "••••••");
eq("空值", ctx.maskKey(""), "—");

console.log("\n[3] extractToken —— 平台 Token 提取");
eq("纯 token", ctx.extractToken("abcdefghijklmnopqrstuvwxyz123456"), "abcdefghijklmnopqrstuvwxyz123456");
eq("JSON 包裹", ctx.extractToken('{"token":"abcdefghijklmnopqrstuvwxyz123456"}'), "abcdefghijklmnopqrstuvwxyz123456");
eq("value 字段", ctx.extractToken('{"value":"abcdefghijklmnopqrstuvwxyz123456"}'), "abcdefghijklmnopqrstuvwxyz123456");
eq("带引号", ctx.extractToken('"abcdefghijklmnopqrstuvwxyz123456"'), "abcdefghijklmnopqrstuvwxyz123456");
eq("Bearer 前缀", ctx.extractToken("Bearer abcdefghijklmnopqrstuvwxyz123456"), "abcdefghijklmnopqrstuvwxyz123456");
eq("空", ctx.extractToken(""), "");

console.log("\n[4] breakdown —— 单模型 token 拆分");
eq("标准五类", ctx.breakdown([
  { type: "REQUEST", amount: "12" },
  { type: "PROMPT_CACHE_HIT_TOKEN", amount: "100" },
  { type: "PROMPT_CACHE_MISS_TOKEN", amount: "50" },
  { type: "RESPONSE_TOKEN", amount: "30" },
  { type: "PROMPT_TOKEN", amount: "7" }]),
  { requests: 12, tokens: 187, hit: 100, miss: 50, resp: 30, prompt: 7 });

console.log("\n[5] parseUsage —— 真实平台响应结构");
// 结构取自 platform.deepseek.com/api/v0/usage/{amount,cost} 的实际返回
const amountJson = {
  code: 0, msg: "", data: { biz_data: {
    total: [
      { model: "deepseek-v4-flash", usage: [
        { type: "REQUEST", amount: "100" },
        { type: "PROMPT_CACHE_HIT_TOKEN", amount: "800000" },
        { type: "PROMPT_CACHE_MISS_TOKEN", amount: "200000" },
        { type: "RESPONSE_TOKEN", amount: "50000" }] },
      { model: "deepseek-v4-pro", usage: [
        { type: "REQUEST", amount: "5" },
        { type: "PROMPT_CACHE_MISS_TOKEN", amount: "3000" },
        { type: "RESPONSE_TOKEN", amount: "700" }] }
    ],
    days: [
      { date: "2026-10-01", data: [{ model: "deepseek-v4-flash", usage: [
        { type: "REQUEST", amount: "60" },
        { type: "PROMPT_CACHE_HIT_TOKEN", amount: "500000" },
        { type: "PROMPT_CACHE_MISS_TOKEN", amount: "100000" },
        { type: "RESPONSE_TOKEN", amount: "30000" }] }] },
      { date: "2026-10-02", data: [
        { model: "deepseek-v4-flash", usage: [
          { type: "REQUEST", amount: "40" },
          { type: "PROMPT_CACHE_HIT_TOKEN", amount: "300000" },
          { type: "PROMPT_CACHE_MISS_TOKEN", amount: "100000" },
          { type: "RESPONSE_TOKEN", amount: "20000" }] },
        { model: "deepseek-v4-pro", usage: [
          { type: "REQUEST", amount: "5" },
          { type: "PROMPT_CACHE_MISS_TOKEN", amount: "3000" },
          { type: "RESPONSE_TOKEN", amount: "700" }] }
      ] }
    ] } }
};
const costJson = {
  code: 0, msg: "", data: { biz_data: [ {   // 注意: cost 的 biz_data 是数组
    total: [
      { model: "deepseek-v4-flash", usage: [
        { type: "REQUEST", amount: "100" },
        { type: "PROMPT_CACHE_HIT_TOKEN", amount: "0.08" },
        { type: "PROMPT_CACHE_MISS_TOKEN", amount: "0.40" },
        { type: "RESPONSE_TOKEN", amount: "0.15" }] },
      { model: "deepseek-v4-pro", usage: [
        { type: "REQUEST", amount: "5" },
        { type: "PROMPT_CACHE_MISS_TOKEN", amount: "0.09" },
        { type: "RESPONSE_TOKEN", amount: "0.07" }] }
    ],
    days: [
      { date: "2026-10-01", data: [{ model: "deepseek-v4-flash", usage: [
        { type: "REQUEST", amount: "60" },
        { type: "PROMPT_CACHE_HIT_TOKEN", amount: "0.05" },
        { type: "PROMPT_CACHE_MISS_TOKEN", amount: "0.20" },
        { type: "RESPONSE_TOKEN", amount: "0.09" }] }] },
      { date: "2026-10-02", data: [{ model: "deepseek-v4-flash", usage: [
        { type: "REQUEST", amount: "40" },
        { type: "PROMPT_CACHE_HIT_TOKEN", amount: "0.03" },
        { type: "PROMPT_CACHE_MISS_TOKEN", amount: "0.20" },
        { type: "RESPONSE_TOKEN", amount: "0.06" }] },
        { model: "deepseek-v4-pro", usage: [
        { type: "REQUEST", amount: "5" },
        { type: "PROMPT_CACHE_MISS_TOKEN", amount: "0.09" },
        { type: "RESPONSE_TOKEN", amount: "0.07" }] }] }
    ] } ] }
};
const u = ctx.parseUsage(amountJson, costJson);
eq("总请求数", u.total.requests, 105);
eq("总 token（等于 models 之和）", u.total.tokens, u.models.reduce((a, m) => a + m.tokens, 0));
eq("总 token 数值", u.total.tokens, 1053700);
eq("缓存命中总量", u.total.hit, 800000);
eq("总费用（REQUEST 不计入）", Number(u.total.cost.toFixed(2)), 0.79);
eq("天数", u.days.length, 2);
eq("按日期升序", u.days.map(d => d.date), ["2026-10-01", "2026-10-02"]);
eq("10-01 token", u.days[0].tokens, 630000);
ok("10-01 费用已按日期匹配", Math.abs(u.days[0].cost - 0.34) < 1e-9);
eq("模型数", u.models.length, 2);
eq("flash 标签中文化", u.models[0].label, "V4 Flash");
eq("pro 标签中文化", u.models[1].label, "V4 Pro");
ok("pro 费用正确", Math.abs(u.models[1].cost - 0.16) < 1e-9);
eq("10-02 token（含 pro）", u.days[1].tokens, 423700);
ok("10-02 费用（含 pro）", Math.abs(u.days[1].cost - 0.45) < 1e-9);
ok("合计请求 = 各天请求之和", u.total.requests === u.days.reduce((a, d) => a + d.requests, 0));
ok("合计费用 = 各天费用之和", Math.abs(u.total.cost - u.days.reduce((a, d) => a + d.cost, 0)) < 1e-9);
ok("合计 token = 各模型 token 之和", u.total.tokens === u.models.reduce((a, m) => a + m.tokens, 0));

console.log("\n[5b] 回归：days 不全时，汇总必须仍以权威 total 为准（曾出现汇总与模型拆解对不上）");
const amountPartial = { code: 0, data: { biz_data: {
  total: [{ model: "m", usage: [{ type: "REQUEST", amount: "105" }, { type: "RESPONSE_TOKEN", amount: "1000" }] }],
  days: [{ date: "2026-10-01", data: [{ model: "m", usage: [{ type: "REQUEST", amount: "60" }, { type: "RESPONSE_TOKEN", amount: "600" }] }] }]
} } };
const costPartial = { code: 0, data: { biz_data: [{
  total: [{ model: "m", usage: [{ type: "RESPONSE_TOKEN", amount: "9.99" }] }],
  days: [{ date: "2026-10-01", data: [{ model: "m", usage: [{ type: "RESPONSE_TOKEN", amount: "1.11" }] }] }]
}] } };
const p = ctx.parseUsage(amountPartial, costPartial);
eq("请求数取权威 total（而非 days 之和 60）", p.total.requests, 105);
eq("token 取权威 total", p.total.tokens, 1000);
eq("费用取权威 total", p.total.cost, 9.99);
eq("按天明细仍按 days 展示", p.days[0].tokens, 600);
ok("无 total 时才回退到按天累加",
  ctx.parseUsage({ code: 0, data: { biz_data: { total: [], days: [{ date: "d", data: [{ model: "m",
    usage: [{ type: "REQUEST", amount: "3" }, { type: "RESPONSE_TOKEN", amount: "10" }] }] }] } } },
    { code: 0, data: { biz_data: [] } }).total.tokens === 10);

console.log("\n[6] parseUsage —— 空数据 / 缺字段不崩");
const empty = ctx.parseUsage({ code: 0, data: { biz_data: { total: [], days: [] } } },
                             { code: 0, data: { biz_data: [] } });
eq("空数据 total 全 0", empty.total, { requests: 0, tokens: 0, hit: 0, miss: 0, resp: 0, prompt: 0, cost: 0 });
eq("空数据 days", empty.days.length, 0);
let crash = false;
try { ctx.parseUsage({}, {}); ctx.parseUsage(null, null); } catch (e) { crash = true; }
ok("null / 空对象不抛异常", !crash);

console.log("\n[7] computeSpend —— 消耗与充值推算");
const now = Date.now();
const day = 86400000;
const hist = [
  { t: now - 10 * day, c: "CNY", v: 100 },
  { t: now - 8 * day,  c: "CNY", v: 90 },   // 消耗 10
  { t: now - 6 * day,  c: "CNY", v: 190 },  // 充值 100
  { t: now - 4 * day,  c: "CNY", v: 170 },  // 消耗 20
  { t: now - 1 * day,  c: "CNY", v: 165 }   // 消耗 5
];
const all = ctx.computeSpend(hist, 0);
eq("累计消耗", all.spent, 35);
eq("累计充值", all.recharge, 100);
eq("充值次数", all.recharges.length, 1);
const win = ctx.computeSpend(hist, 7);
eq("近7天消耗", win.spent, 25);
eq("近7天充值", win.recharge, 100);
eq("近7天末值=当前余额", win.last.v, 165);

console.log("\n[8] money / num 格式化");
eq("CNY", ctx.money("110.5", "CNY"), "¥110.50");
eq("USD", ctx.money("3.2", "USD"), "$3.20");
eq("千分位", ctx.num(1234567), "1,234,567");
eq("非法值", ctx.money("abc", "CNY"), "—");

console.log("\n[9] esc —— XSS 转义");
eq("尖括号", ctx.esc("<img src=x onerror=alert(1)>"), "&lt;img src=x onerror=alert(1)&gt;");
eq("引号", ctx.esc('a"b\'c'), "a&quot;b&#39;c");

console.log("\n[10] normKey —— 旧数据形状归一");
const nk = ctx.normKey({ name: "主力", key: "  sk-abc  " });
ok("缺少的 id 自动生成", typeof nk.id === "string" && nk.id.length > 0);
eq("key 去首尾空格", nk.key, "sk-abc");
eq("enabled 默认 true", nk.enabled, true);
eq("tags 默认空数组", nk.tags, []);
eq("note 默认空", nk.note, "");
eq("tags 是字符串时按逗号/空格拆分", ctx.normKey({ key: "k", tags: "生产, 客户A 测试" }).tags,
   ["生产", "客户A", "测试"]);
eq("tags 是数组时原样保留", ctx.normKey({ key: "k", tags: ["a", "b"] }).tags, ["a", "b"]);
eq("tags 数组里的空值被过滤", ctx.normKey({ key: "k", tags: ["a", "", null] }).tags, ["a"]);
eq("enabled=false 被保留", ctx.normKey({ key: "k", enabled: false }).enabled, false);

console.log("\n[11] warnHits —— 余额预警判定（阈值取自 S.settings）");
const ST = globalThis.__S;
ST.settings.warnThreshold = 0;
eq("阈值 0 = 关闭，不报警", ctx.warnHits({ infos: [{ currency: "CNY", total: "1" }] }), []);
ST.settings.warnThreshold = 10;
eq("余额低于阈值 → 命中", ctx.warnHits({ infos: [{ currency: "CNY", total: "5" }] }),
   [{ currency: "CNY", total: 5 }]);
eq("余额等于阈值 → 不命中（小于才算）", ctx.warnHits({ infos: [{ currency: "CNY", total: "10" }] }), []);
eq("余额高于阈值 → 不命中", ctx.warnHits({ infos: [{ currency: "CNY", total: "99" }] }), []);
eq("多币种只挑低于阈值的",
   ctx.warnHits({ infos: [{ currency: "CNY", total: "5" }, { currency: "USD", total: "50" }] }),
   [{ currency: "CNY", total: 5 }]);
eq("没有 infos → 不报", ctx.warnHits({ status: "invalid" }), []);
eq("null → 不报", ctx.warnHits(null), []);
eq("余额是字符串也能比较", ctx.warnHits({ infos: [{ currency: "CNY", total: "9.99" }] })[0].total, 9.99);
ST.settings.warnThreshold = 0;

console.log("\n[12] allTags —— 标签统计与排序");
ST.keys = [{ tags: ["生产", "客户A"] }, { tags: ["生产"] }, { tags: ["生产", "测试"] }, {}];
const tags = ctx.allTags();
eq("出现次数最多的排第一", tags[0], ["生产", 3]);
eq("计数按降序排列", tags.map(t => t[1]), [3, 1, 1]);
ok("三个标签都在", ["生产", "客户A", "测试"].every(n => tags.some(t => t[0] === n)));
// 计数相同时的先后由 localeCompare 决定（中文会走拼音序），所以不断言具体顺序
ST.keys = [];
eq("没有 Key 时返回空数组", ctx.allTags(), []);

console.log(`\n[13] 加密存储 —— AES-GCM 往返`);

(async () => {
  const iter = /const PBKDF2_ITER\s*=\s*(\d+)/.exec(src);
  ok("PBKDF2 迭代次数不少于 200000", iter && Number(iter[1]) >= 200000);

  const secret = { keys: [{ name: "主力号", key: "sk-super-secret-0001" }],
                   usage: { total: { tokens: 12345 } }, platformToken: "tok-abc" };
  const blob = await ctx.encryptBlob(secret, "hunter2");

  ok("产出的是密文（不含明文痕迹）", !JSON.stringify(blob).includes("sk-super-secret"));
  eq("算法标记", blob.alg, "AES-GCM-256");
  eq("KDF 标记", blob.kdf, "PBKDF2-SHA256");
  ok("有随机盐", typeof blob.salt === "string" && blob.salt.length >= 20);
  ok("有随机 IV", typeof blob.iv === "string" && blob.iv.length >= 12);
  ok("密文非空", typeof blob.ct === "string" && blob.ct.length > 40);

  const back = await ctx.decryptBlob(blob, "hunter2");
  eq("正确密码能完整解回原文", back, secret);

  let wrong = false;
  try { await ctx.decryptBlob(blob, "hunter3"); } catch (e) { wrong = true; }
  ok("错误密码解不开（GCM 认证失败）", wrong);

  let tampered = false;
  try {
    await ctx.decryptBlob(Object.assign({}, blob, { ct: blob.ct.slice(0, -4) + "AAAA" }), "hunter2");
  } catch (e) { tampered = true; }
  ok("密文被篡改会被检测出来", tampered);

  const blob2 = await ctx.encryptBlob(secret, "hunter2");
  ok("两次加密的盐不同（随机化生效）", blob2.salt !== blob.salt);
  ok("两次加密的密文不同", blob2.ct !== blob.ct);

  console.log(`\n${"=".repeat(46)}\n  通过 ${pass} 项，失败 ${fail} 项\n${"=".repeat(46)}`);
  process.exit(fail ? 1 : 0);
})();
