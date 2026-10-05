# 项目简介 · Project Intro

中英双语的项目介绍，按长度分档，直接复制对应段落即可。

Bilingual project descriptions, organised by length. Copy whichever fits.

> 版本 v1.2 · 2026-10-06
> 覆盖的能力：批量查余额、可用性实测、余额预警、用量与消耗、标签分组、
> 备份恢复、**加密存储（DPAPI + 本地 INI 文件）**、**中英双语界面**、命令行版。

**目录 / Contents**

| 用途 / Use | 长度 / Length |
|---|---|
| [1. GitHub 仓库 About 字段](#1-github-仓库-about-字段) | 268 字符（上限 350） |
| [2. 一句话简介](#2-一句话简介--one-liner) | ~35 字 / ~18 words |
| [3. 短版](#3-短版--short) | ~110 字 / ~75 words |
| [4. 标准版](#4-标准版--standard) | ~320 字 / ~200 words |
| [5. 长版](#5-长版--long) | ~750 字 / ~480 words |
| [6. 社交平台短文案](#6-社交平台短文案--social-snippets) | — |

---

## 1. GitHub 仓库 About 字段

> 仓库首页右上角 **About** → **Description**。上限 350 字符，下面这段 268 字符，整段粘进去即可（GitHub 支持换行）。

```text
导入 DeepSeek API Key，批量查余额、验证可用性、追踪消耗。单文件网页面板 + 命令行工具，零依赖，数据用 Windows DPAPI 加密存在本机 INI 文件里，Key 不经过任何第三方。

Bulk-check DeepSeek API key balances, verify usability and track usage. Single-file web panel + CLI, zero dependencies. Data is DPAPI-encrypted into a local INI file; keys never leave your machine.
```

**Topics 建议**（About 里的标签）：

```text
deepseek, api-key, balance, usage-tracking, token-counter, cli, dashboard, python, zero-dependencies, encryption, dpapi, self-hosted
```

**Website 字段**留空即可，或填 Release 下载页。

---

## 2. 一句话简介 / One-liner

**中文**

> 导入 DeepSeek API Key，一次看全所有账号的余额、可用性和消耗 —— 数据加密存在本机。

**English**

> Import your DeepSeek API keys and see every account's balance, health and spend at a glance — encrypted locally.

---

## 3. 短版 / Short

**中文**

> 手里有好几个 DeepSeek 的 Key，想知道哪个还有钱、哪个已经被吊销、这个月烧了多少？
>
> 这个工具让你一次导入全部 Key，一屏看全余额、可用性和消耗。它还会真的去验证 Key 能不能调模型 —— 因为「余额接口能通」和「Key 真的能用」是两回事。
>
> 单文件网页版 + 命令行版，零第三方依赖，中英双语。数据用 Windows DPAPI 加密存在本机一个 INI 文件里，打开自动解密；Key 不经过任何第三方服务器。MIT 开源。

**English**

> Got several DeepSeek API keys and no idea which still have credit, which got revoked, or what this month cost?
>
> This tool imports them all and shows balances, health and spend on one screen. It also actually verifies each key can call a model — because "the balance endpoint responds" and "the key works" are two different things.
>
> Single-file web panel plus a CLI, zero third-party dependencies, bilingual UI. Data is encrypted with Windows DPAPI into a local INI file and decrypted automatically on open; your keys never touch a third-party server. MIT licensed.

---

## 4. 标准版 / Standard

**中文**

> **DeepSeek Key 面板** —— 批量管理 DeepSeek API Key 的本地工具。
>
> **为什么需要它。** 当你有多个 Key（主号、备用、客户专用、测试），官方控制台一次只能看一个账号。这个工具让你把它们一次性导入，一屏看全：余额、赠送额、充值额、状态分类（可用 / 余额不足 / 无效 / 限流）。
>
> **余额能查 ≠ Key 能用。** 所以它内置可用性实测：默认查 `GET /models` 验证鉴权并列出可用模型，**不消耗任何 token**；需要确定时再开深度实测，真实调用一次 `chat/completions`（`max_tokens=1`）。
>
> **数据怎么存。** 自动加密保存到 `我的文档\DeepSeekKeyPanel\dskp.ini`，用 Windows DPAPI 加密 —— 密钥由你的 Windows 账户派生，所以**打开面板自动解密，不用记密码**；而这个文件拷到别的电脑或别的账户下就是一堆废数据。每次改动自动写回，也可以另设主密码再加一道门。
>
> **用量。** 每次查询自动记录余额快照，推算消耗、充值和「还能用多少天」，零额外凭据；也可以接入平台官方用量接口，拿到真实 token 数、请求数、缓存命中率、费用和多月对比 —— 注意这需要网页登录 Token，因为官方**没有**开放用 API Key 查历史用量的接口。
>
> **形态与依赖。** 一个零依赖、可离线的单文件网页面板（可打包成免安装 exe，另附便携版），以及一个命令行工具，方便批量几百个 Key 或接进定时任务。界面中英双语可切换。所有请求都由你的电脑直接发往 `api.deepseek.com` 和 `platform.deepseek.com`。MIT 开源。

**English**

> **DeepSeek Key Panel** — a local tool for managing DeepSeek API keys in bulk.
>
> **Why.** When you hold several keys (main, backup, client-specific, testing), the official console only shows one account at a time. This tool imports them all and puts balances, granted credit, top-ups and status classification (usable / out of credit / invalid / rate limited) on a single screen.
>
> **A reachable balance endpoint is not a working key.** So usability testing is built in: by default `GET /models` verifies auth and lists available models at **zero token cost**; deep mode makes one real `chat/completions` call (`max_tokens=1`) when you need certainty.
>
> **Where the data lives.** It is encrypted automatically into `Documents\DeepSeekKeyPanel\dskp.ini` using Windows DPAPI — the key derives from your Windows account, so the panel **decrypts on open with no password to remember**, while the file is useless on another machine or account. Every change is written back automatically, and an optional master password adds a second gate.
>
> **Usage.** Every check records a balance snapshot, from which spend, top-ups and "days remaining at this burn rate" are derived — no extra credentials. Alternatively, the platform's official usage endpoints give real token counts, request counts, cache hit rate, cost and multi-month comparison. That route needs a web session token, because the platform does **not** expose historical usage behind an API key.
>
> **Shape and dependencies.** A zero-dependency, offline-capable single-file web panel (buildable into a portable exe, with a portable zip also published), plus a CLI for handling hundreds of keys or wiring into cron. The UI switches between Chinese and English. Every request goes from your machine straight to `api.deepseek.com` and `platform.deepseek.com`. MIT licensed.

---

## 5. 长版 / Long

> 适合发在博客、论坛、Reddit、V2EX，或提交到 awesome 类清单。

**中文**

> ### DeepSeek Key 面板：一次管好你所有的 DeepSeek Key
>
> **问题。** 用 DeepSeek 的人往往不止一个 Key —— 主力号、备用号、给客户开的、跑测试的。想知道「哪个还有钱、哪个被吊销了、这个月花了多少」，只能一个个登录官方控制台看。
>
> **做法。** 这是个本地工具，把 Key 一次性导入后一屏看全。批量粘贴、拖入 txt/csv/json 都行，自动去重、自动识别、自动剥掉 `Bearer ` 前缀。查询并发可调，状态分得很细：可用、余额不足、Key 无效、被限流、网络受阻、官方异常 —— 而不是笼统地报个"失败"。
>
> **一个容易被忽略的点：余额能查 ≠ Key 能用。** 所以它内置了可用性实测：默认查 `GET /models`，验证鉴权并列出可用模型，**不消耗任何 token**；需要确定时再开深度实测，真实调用一次 `chat/completions`（`max_tokens=1`）。
>
> **数据落盘与加密。** 数据自动保存到 `我的文档\DeepSeekKeyPanel\dskp.ini`，内容用 **Windows DPAPI** 加密。密钥由你的 Windows 账户派生，带来两个直接好处：打开面板**自动解密，不用输密码**；文件被别人拷走也解不开。每次改动自动写回。可选再设一个主密码，防「别人趁你没锁屏用你电脑」。在面板里能直接看到文件路径、大小和最后更新时间。
>
> **用量怎么来？** 这里有个坑值得说明：**DeepSeek 没有开放「用 API Key 查历史调用量」的接口**，官方文档里只有余额。所以工具给了两条路 —— 一是每次查询自动记录余额快照，推算消耗、充值和"按当前速度还能用多少天"，零额外凭据；二是接入平台官方用量接口，拿到真实 token 数、请求数、缓存命中率、按天与按模型拆解、费用，以及多月对比。后者需要网页登录 Token（面板里有 30 秒拿到它的脚本），因为那个接口不接受 API Key，也没有任何 CORS 响应头。
>
> **还有什么。** 余额预警（设阈值，跌破高亮并可发浏览器通知）、标签分组、余额曲线、完整备份与恢复、一键清理无效 Key、导出 CSV/JSON/纯 Key 列表、自动刷新、亮暗主题、连接自检。
>
> **中英双语。** 右上角一个分段开关就能切换，也可以 `?lang=en` 直接指定。漏翻由 CI 校验，不靠肉眼。
>
> **两种形态。** 一个单文件网页面板 —— 零框架、零 CDN、可离线，能直接双击打开，也能用 PyInstaller 打包成免安装 exe（额外提供便携版 zip）；以及一个命令行工具，支持 `table/json/csv/txt` 四种输出、按状态过滤、余额阈值报警和分级退出码，方便接监控。
>
> **安全。** 所有请求都由你的电脑直接发往 `api.deepseek.com` 和 `platform.deepseek.com`，没有任何第三方服务器参与。本地服务只监听 `127.0.0.1`，只放行这两个域名，不转发 Cookie。导出的备份文件是明文，会二次确认并明确警告。
>
> **质量。** 项目自带 14 项自检：Python 语法编译、前端结构检查、JS 语法检查、**ID 交叉引用检查**（网页里 `$("#xxx")` 拼错只会静默失效，肉眼极难发现）、**中英词条覆盖检查**、89 项纯逻辑断言、加密往返、INI 存储 37 项、HTTP 接口 27 项、真起服务打接口的冒烟测试、CLI 冒烟测试。GitHub Actions 跑 CI，打 tag 自动构建 exe 并发布 Release。
>
> MIT 开源，Python 3.8+，无第三方运行时依赖。

**English**

> ### DeepSeek Key Panel: manage all your DeepSeek keys in one place
>
> **The problem.** Anyone using DeepSeek tends to accumulate keys — a main one, a backup, one for a client, one for testing. Finding out which still has credit, which got revoked and what this month cost means logging into the console once per account.
>
> **The approach.** A local tool: import your keys once and see everything on one screen. Paste in bulk, drag in a txt/csv/json file — it de-duplicates, detects keys and strips `Bearer ` prefixes automatically. Concurrency is configurable and statuses are granular: usable, out of credit, invalid, rate limited, network blocked, upstream error — not a vague "failed".
>
> **The easily-missed part: a working balance endpoint does not mean the key works.** So usability testing is built in. By default it calls `GET /models`, verifying auth and listing available models at **zero token cost**. Deep mode makes one real `chat/completions` call (`max_tokens=1`) when you need certainty.
>
> **Storage and encryption.** Data is saved automatically to `Documents\DeepSeekKeyPanel\dskp.ini`, encrypted with **Windows DPAPI**. The key derives from your Windows account, which buys two things: the panel **decrypts on open with no password to type**, and the file is useless if someone copies it elsewhere. Every change is written back immediately. An optional master password adds a second gate against someone using your unlocked session. The panel shows the exact file path, size and last-updated time.
>
> **Where does usage data come from?** Here's a gotcha worth spelling out: **DeepSeek does not expose historical usage behind an API key.** The official docs cover balance only. So the tool offers two routes. First, every check records a balance snapshot, from which spend, top-ups and "days remaining at this burn rate" are derived — no extra credentials. Second, the platform's official usage endpoints give real token counts, request counts, cache hit rate, daily and per-model breakdowns, cost, and multi-month comparison. The second route needs a web session token (the panel includes a 30-second snippet to grab it), because that endpoint accepts no API key and sends no CORS headers at all.
>
> **What else.** Low-balance thresholds with highlighting and optional browser notifications, tag grouping, balance curves, full backup and restore, one-click cleanup of invalid keys, CSV/JSON/plain-key-list export, auto-refresh, light/dark themes, connection self-diagnosis.
>
> **Bilingual.** One segmented toggle in the header switches between Chinese and English, or use `?lang=en`. Translation coverage is enforced by CI, not eyeballed.
>
> **Two forms.** A single-file web panel — no framework, no CDN, works offline, opens by double-click, and packages into a portable exe via PyInstaller (a portable zip is published too). Plus a CLI supporting `table/json/csv/txt` output, status filtering, balance-threshold alerts and graded exit codes for monitoring.
>
> **Security.** Every request goes from your machine straight to `api.deepseek.com` and `platform.deepseek.com`; no third-party server is involved. The local server binds to `127.0.0.1` only and forwards to just those two hosts. Exported backups are cleartext and require explicit confirmation.
>
> **Quality.** The repo ships a 14-part self-check: Python compilation, frontend structural checks, JS syntax, **ID cross-referencing** (a typo in `$("#xxx")` fails silently in a browser and is nearly impossible to spot by eye), **translation-coverage checks**, 89 pure-logic assertions, encryption round-trips, 37 INI-store assertions, 27 HTTP-API assertions, a real server smoke test hitting live endpoints, and CLI smoke tests. GitHub Actions runs CI; pushing a tag builds the exe and publishes a release.
>
> MIT licensed, Python 3.8+, no third-party runtime dependencies.

---

## 6. 社交平台短文案 / Social snippets

**X / Twitter（英文，280 字符内）**

```text
Managing several DeepSeek API keys is annoying — the console shows one account at a time.

So I built a local tool: import them all, see balances + health + spend on one screen.

It verifies keys can actually call a model, not just hit the balance endpoint.

Data is DPAPI-encrypted on disk and decrypts on open. MIT, zero deps.
```

**微博 / 朋友圈（中文，140 字内）**

```text
手上有好几个 DeepSeek 的 Key，官方控制台一次只能看一个。

做了个本地小工具：一次性导入，一屏看全余额、状态、消耗。还会真的验证 Key 能不能调模型——毕竟「余额接口能通」和「Key 真的能用」是两回事。

数据用 Windows DPAPI 加密存在本机，打开自动解密、不用记密码。单文件网页版 + 命令行版，零依赖，中英双语，MIT 开源。
```

**V2EX / 少数派（中文，标题 + 一句话）**

```text
标题：做了个本地工具，一次管好所有 DeepSeek API Key
副题：批量查余额、实测可用性、看用量消耗；数据加密存本机，打开自动解密
```

**Hacker News（英文，标题）**

```text
Show HN: DeepSeek Key Panel – bulk-check API key balances and usage, encrypted locally
```
