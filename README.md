<div align="center">

<img src="assets/logo.png" width="112" alt="DeepSeek Key 面板">

# DeepSeek Key 面板

**导入 DeepSeek API Key，批量查余额、验证可用性、看用量和消耗。**

一个单文件网页面板 + 一个命令行工具。**零第三方依赖**，Key 不经过任何第三方服务器。

[![CI](https://github.com/xiaoniao/deepseek-key-panel/actions/workflows/ci.yml/badge.svg)](https://github.com/xiaoniao/deepseek-key-panel/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/xiaoniao/deepseek-key-panel?display_name=tag&sort=semver)](https://github.com/xiaoniao/deepseek-key-panel/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-2f855a.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776ab.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#)

[English](README.en.md) · [更新日志](CHANGELOG.md) · [参与贡献](CONTRIBUTING.md) · [安全说明](SECURITY.md)

</div>

---

## 它解决什么问题

手里有好几个 DeepSeek 的 Key —— 主号、备用号、客户的、测试的。想知道：

- 哪个还有钱？哪个已经被吊销了？
- 余额接口能通，但**这个 Key 真的能调模型吗**？
- 这个月到底烧了多少 token、多少钱？

官方控制台一次只能看一个账号。这个工具让你**一次导入一堆 Key，一屏看全**。

<div align="center">
  <img src="docs/screenshots/panel.png" width="880" alt="Key 管理与余额">
  <br>
  <sub><b>Key 管理与余额</b> —— 一屏看全所有 Key 的状态、余额、预警和实测结果</sub>
  <br><br>
  <img src="docs/screenshots/usage.png" width="880" alt="用量与消耗">
  <br>
  <sub><b>用量与消耗</b> —— 余额快照曲线（自动推算消耗）+ 平台官方 token/费用报表</sub>
</div>

---

## 快速开始

### 方式一：免安装 exe（推荐给不想装环境的人）

去 [Releases](https://github.com/xiaoniao/deepseek-key-panel/releases/latest) 下载
`DeepSeekKeyPanel.exe`，**双击即可**。不需要装 Python，不写注册表，删掉文件就等于卸载。

会以无边框应用窗口打开，关掉窗口程序自动退出。

> 首次运行如果 SmartScreen 弹警告，点「更多信息」→「仍要运行」——
> 这是没做代码签名的单文件 exe 的常见情况。介意的话用下面的源码方式。

### 方式二：源码运行

需要 Python 3.8+，**不需要装任何第三方包**。

```bash
git clone https://github.com/xiaoniao/deepseek-key-panel.git
cd deepseek-key-panel
python run_panel.py
```

Windows 上也可以直接双击 `启动面板.cmd`。

### 方式三：命令行

```bash
python -m deepseek_key_panel.cli -f keys.txt
```

或者装成命令：

```bash
pip install .
deepseek-key-panel          # 图形界面
dskp -f keys.txt            # 命令行
```

---

## 功能

### 余额与状态

- 批量导入：粘贴、`.txt` / `.csv` / `.json` 文件、或**直接把文件拖到页面上**
- 自动去重、自动识别 `sk-` 串、自动剥掉 `Bearer ` 前缀、`#` 开头当注释
- 状态区分：✅ 可用 · ⚠️ 余额不足 · ⛔ Key 无效 · 🚦 被限流 · 🌐 网络受阻 · 🔧 官方异常
- 按币种汇总余额（总额 / 赠送 / 充值），可搜索、筛选、排序
- **退出码分级**（CLI）：`0` 全部成功 / `1` 有失败 / `2` 参数错 / `3` 余额低于阈值

### 🔬 可用性实测

余额能查 ≠ Key 能用。两种实测模式：

| 模式 | 做什么 | 花不花钱 |
|---|---|---|
| **快速**（默认） | `GET /models`，验证鉴权并列出可用模型 | **不消耗任何 token** |
| **深度** | 额外真实调用一次 `chat/completions`（`max_tokens=1`） | 产生极少量费用 |

结果直接显示在表格里：`✔ 实测 3 个模型 · 210ms`。

### 🔻 余额预警

设定阈值，跌破的 Key 整行高亮、余额标红、汇总卡计数；可选**浏览器通知**，
余额回升后自动复位（不会反复轰炸）。

### 📊 用量与消耗

- **余额消耗曲线**：每次查询自动记录「时间 + 余额」快照，
  推算近 7/30/90 天的消耗、充值、日均消耗和可用天数 —— 不需要任何额外凭据
- **官方用量**：真实 token 数、请求数、缓存命中率、按天分布、按模型拆解、费用
- **多月对比**：一次拉最近 3 个月，条形图看费用走势
- 导出 CSV（按天明细 + 按模型拆解）

### 🏷 分组与整理

标签分组、按标签筛选、按状态批量选择（一键选可用/无效/预警）、
正经的编辑弹窗（Esc 关闭 / Enter 保存）。

### 💾 备份与恢复

- **完整备份**：Key、标签、备注、设置、快照历史、用量结果，一个 JSON 全带走
- **导出纯 Key 列表**：当前筛选结果一行一个，方便喂给别的工具
- **一键清理无效**：只删返回 401 的，余额不足 / 限流 / 网络失败的不动

### 🔐 加密存储（主密码）

Key、余额快照、用量记录、平台 Token **全部加密后才写入本机**：

- `AES-GCM-256` 加密，密钥由主密码经 `PBKDF2-SHA256`（25 万次迭代）派生
- 每条记录使用随机盐与随机 IV；同一个密码每次都产生不同密文
- 密码**不写入任何地方**。可选只在 `sessionStorage` 保留，刷新免重复输入，关掉标签页即失效
- 支持立即锁定（清空内存明文）、修改密码、关闭加密
- 忘记密码 = 数据永久丢失，没有后门

### 🌐 中英双语

右上角切换，也可用 `?lang=en` / `?lang=zh` 直接指定。
`tests/check_i18n.py` 会校验两种语言的词条键集合一致、映射表无失效、标记里的中文无遗漏 —— 漏翻是 CI 能拦住的错误，不靠肉眼。

### 其他

自动刷新（1 分钟 ~ 1 小时）、亮/暗主题、连接自检、并发/超时/重试可调、
支持中途停止（不会把在飞的 Key 误标为失败）。

---

## 命令行用法

零依赖，Python 直连 DeepSeek，**不需要起本地服务**（那是给浏览器用的）。

```bash
# 查 keys.txt 里所有 Key（默认读同目录 keys.txt）
python -m deepseek_key_panel.cli

# 从文件读 + 做 /models 可用性验证 + 输出 CSV
python -m deepseek_key_panel.cli -f keys.txt --models --format csv --out result.csv

# 只输出能用的 Key，喂给别的工具
python -m deepseek_key_panel.cli -f all.txt --quiet --format txt --only ok > usable.txt

# 余额低于 10 就报警（退出码 3），接监控
python -m deepseek_key_panel.cli -f keys.txt --threshold 10 || echo "有 Key 余额不足"

# 拉官方用量
python -m deepseek_key_panel.cli --usage-token "xxx" --usage-month 2026-10

# 从管道读
cat keys.txt | python -m deepseek_key_panel.cli --stdin --format json
```

| 参数 | 说明 |
|---|---|
| `-f, --file PATH` | 从文件读 Key（可多次，支持 txt/csv/json） |
| `-k, --key SK-XXX` | 直接指定 Key（可多次） |
| `--stdin` | 从标准输入读 |
| `-c, --concurrency N` | 并发数，默认 5 |
| `-t, --timeout S` | 单次超时秒数，默认 20 |
| `--retries N` | 失败重试次数，默认 1 |
| `--models` | 额外做 `GET /models` 可用性验证（不花 token） |
| `--chat` | 额外真实调用一次（花钱，谨慎） |
| `--threshold N` | 余额低于此值标红 + 退出码 3 |
| `--format` | `table`（默认）/ `json` / `csv` / `txt` |
| `--only` | `ok` / `low` / `failed` / `all`，只输出某一类 |
| `--out PATH` | 写入文件 |
| `--show-key` | 表格里显示完整 Key（默认打码） |

---

## 关于接口的实话

先说结论：**DeepSeek 没有开放「用 API Key 查历史调用量」的接口**，官方文档里只有余额。
所以任何声称"纯 API Key 就能出用量"的工具，底层要么在爬网页登录态，要么在本地自己记账。

实测确认（2026-10）：

| 接口 | 用 API Key? | 浏览器跨域 | 能拿到什么 |
|---|---|---|---|
| `GET api.deepseek.com/user/balance` | ✅ | ✅ 回显任意 Origin | 余额、赠送额、充值额、`is_available` |
| `GET api.deepseek.com/models` | ✅ | ✅ 预检放行 | 可用模型列表 → 用于可用性实测 |
| `POST api.deepseek.com/chat/completions` | ✅ | ✅ 预检放行 | 真实调用 → 用于深度实测 |
| `GET platform.deepseek.com/api/v0/usage/amount` | ❌ 需网页登录 Token | ❌ **无任何 CORS 头**，OPTIONS 直接 405 | Token 用量、请求数、缓存命中 |
| `GET platform.deepseek.com/api/v0/usage/cost` | ❌ 同上 | ❌ 同上 | 费用 |

由此决定了两条技术路线：

- 余额 / 可用性 / 真实调用 → **浏览器直连**就能做（面板默认这么做，不需要任何后端）
- 真实用量 → 要么用网页登录 Token 调平台内部接口（面板走本地服务转发），
  要么本地记账（面板的余额快照功能）

> **踩坑记录**：平台用量接口 **HTTP 200 也可能是失败**，
> 返回体是 `{"code":40003,"msg":"Authorization Failed (invalid token)"}` 这种信封格式。
> 本工具按 `code` 字段判断，不是按 HTTP 状态码。

---

## 怎么拿「平台登录 Token」

**只有查官方用量才需要，查余额不需要。**

在浏览器登录 [platform.deepseek.com](https://platform.deepseek.com)，
按 `F12` 打开控制台，粘贴这段回车，Token 会自动进剪贴板：

```js
(function(){
  var KEYS = ["userToken","token","access_token"];
  function grab(v){
    if(!v) return null;
    try { var o = JSON.parse(v); if(o && typeof o === "object")
      return o.token || o.value || o.access_token || o.userToken || null; } catch(e){}
    return (typeof v === "string" && v.length > 20) ? v : null;
  }
  for (var i=0;i<KEYS.length;i++){
    var t = grab(localStorage.getItem(KEYS[i]));
    if (t) { copy(t); console.log("已复制用量 Token"); return; }
  }
  for (var k in localStorage){
    var t2 = grab(localStorage.getItem(k));
    if (t2) { copy(t2); console.log("已复制用量 Token（来自 "+k+"）"); return; }
  }
  console.log("没找到 Token，请在 Application → Local Storage 里手动查看");
})();
```

手动方式：`F12` → **Application / 应用** → **Local Storage** →
`https://platform.deepseek.com` → 找 `userToken`，把整个值粘进面板即可，
面板会自动把里面的 Token 抠出来。

> 这个 Token 是**登录态**，权限等同于你的账号，且会过期。别发给任何人。

---

## 安全

- 所有请求都由**你的浏览器**、**本机 Python** 直接发往 `api.deepseek.com` /
  `platform.deepseek.com`。**没有任何第三方服务器参与**，不存在"把 Key 送去代查"。
- 本地服务只监听 `127.0.0.1`，局域网和公网都访问不到；
  只允许转发到上述两个白名单域名，不转发 Cookie，不落盘任何 Key。
- Key 默认**不保存**在浏览器里（刷新即消失），勾选后才写入 localStorage。
- 导出 CSV/JSON 默认对 Key 打码；「导出纯 Key」和「完整备份」是明文，
  会二次确认并明确警告。
- 详细的边界与取舍见 [SECURITY.md](SECURITY.md)。

> ⚠️ 截图或贴日志前请把 Key 打码。一旦泄露，第一优先级是去 DeepSeek 控制台吊销。

---

## 常见问题

**Q：不启动本地服务，能查余额吗？**
能。`api.deepseek.com` 的接口都支持跨域（实测会回显任意 Origin，包括 `file://` 的 `null`），
直接双击 `src/deepseek_key_panel/web/index.html` 也能用。

**Q：为什么官方用量必须走本地服务？**
`platform.deepseek.com` 的接口不带任何 `Access-Control-Allow-*` 响应头，
`OPTIONS` 预检直接返回 405。浏览器按同源策略会拦死，只能由本机进程代发。

**Q：快速实测和深度实测怎么选？**
平时用快速（`/models`）就够 —— 它能区分"Key 被吊销了"和"Key 能用"，且一分钱不花。
只有在排查"Key 能查到余额但一调模型就报错"时才需要深度实测。

**Q：端口被占用怎么办？**
默认 8787，会自动往后试到 8798；面板也会自动扫这个范围。也可以 `--port 9000` 指定。

**Q：用量页提示 Token 无效？**
网页登录态会过期。重新登录 platform.deepseek.com，用上面的脚本再取一次。

**Q：快照数据会同步到别的设备吗？**
不会，只存在当前浏览器的 localStorage。要用「导出完整备份」再导入来迁移。

**Q：exe 会不会被杀毒软件报毒？**
PyInstaller 单文件 exe 被启发式误报是常见现象。介意的话用源码方式运行，
或者自己 `python build.py` 构建一份。

---

## 开发

```bash
git clone https://github.com/xiaoniao/deepseek-key-panel.git
cd deepseek-key-panel

python tests/run_all.py      # 一把梭跑完所有自检
```

自检包含：Python 语法编译 → 抽前端内联 JS + 结构检查 → `node --check` →
**id 交叉检查** → 77 项纯逻辑断言 → CLI 冒烟测试。

> `tests/check_ids.py` 这项别跳过。面板里 `$("#xxx")` 拼错不会报错，
> 只会静默失效，肉眼极难发现 —— 这个脚本就是专门抓它的。

打包成免安装 exe：

```bash
python -m pip install pyinstaller
python build.py                 # 默认无控制台窗口
python build.py --console       # 保留控制台，方便排错
```

### 代码结构

```
src/deepseek_key_panel/
├─ app.py            桌面入口：起服务、开无边框窗口、生命周期
├─ server.py         本地 HTTP 服务 + 代理（零依赖，纯标准库）
├─ cli.py            命令行版
└─ web/index.html    整个前端（单文件，无框架、无 CDN、可离线）
```

改前端时请守住一条底线：**`web/index.html` 必须保持自包含**。
不引入任何框架、CDN 或构建步骤 —— "双击就能用"是这个项目的核心卖点。

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---
## 许可

[MIT](LICENSE) © 2026 xiaoniao

本项目与 DeepSeek 官方无关，未获其背书。DeepSeek 平台页面结构与接口可能随时变动，
本项目不保证长期可用。
问题漏洞请加入群组https://t.me/qianghuntaolun
