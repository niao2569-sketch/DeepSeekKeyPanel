# 参与贡献

感谢你有兴趣改进这个项目。下面是最少必要的信息。

## 环境

只需要 **Python 3.8+**，运行时零第三方依赖。

```bash
git clone https://github.com/xiaoniao/deepseek-key-panel.git
cd deepseek-key-panel

python run_panel.py        # 起服务 + 开应用窗口
# 或
python 启动面板.cmd         # Windows 双击
# 或，装了包之后
python -m deepseek_key_panel
```

想跑 JS 相关的自检还需要 **Node.js 18+**（用于 `node --check` 和逻辑断言）。
没有 Node 也能用，只是那几项会被跳过。

## 改完必须跑自检

```bash
python tests/run_all.py
```

它会依次做：Python 语法编译 → 抽面板内联 JS + 结构检查 → `node --check` →
**id 交叉检查** → 77 项纯逻辑断言 → CLI 冒烟测试。

> `tests/check_ids.py` 这项别跳过。面板里 `$("#xxx")` 拼错不会报错，
> 只会静默失效，肉眼极难发现 —— 这个脚本就是专门抓它的。

## 代码结构

```
src/deepseek_key_panel/
├─ app.py        桌面入口：起服务、开无边框窗口、生命周期
├─ server.py     本地 HTTP 服务 + 代理（零依赖，只用标准库）
├─ cli.py        命令行版
└─ web/index.html  整个前端（单文件，无框架、无 CDN、可离线）
```

改前端时记住一条：**`web/index.html` 必须保持自包含**。
不引入任何框架、CDN 或构建步骤 —— 双击就能用是这个项目的核心卖点。
需要新依赖请先开 issue 讨论。

## 提交规范

用 [约定式提交](https://www.conventionalcommits.org/zh-hans/)：

```
feat: 支持按标签批量查询
fix: 修复停止时误标失败的问题
docs: 补充平台 Token 的获取步骤
refactor: 把平台请求抽成 platformGet
test: 补充余额预警的边界用例
```

一个提交只做一件事。涉及行为变化请同步更新 `CHANGELOG.md` 的「未发布」段。

## 提交前请确认

- [ ] `python tests/run_all.py` 全绿
- [ ] 没有把任何真实 API Key / 平台 Token 写进代码、测试或文档
- [ ] `web/index.html` 依然是单文件、零外部依赖
- [ ] 新增的 `$("#id")` 引用都能在面板里找到对应元素（自检会查）
- [ ] 行为变化已写进 `CHANGELOG.md`

## 报告问题

- Bug 请用 [Bug 反馈模板](https://github.com/xiaoniao/deepseek-key-panel/issues/new?template=bug_report.yml)
- 功能建议请用 [功能请求模板](https://github.com/xiaoniao/deepseek-key-panel/issues/new?template=feature_request.yml)
- **安全问题请走 [SECURITY.md](SECURITY.md) 里的私下渠道，不要开公开 issue**

> ⚠️ 贴日志、截图、配置时，务必先把 `sk-` 开头的 Key 和平台 Token 打码。
> 一旦泄露请立刻去 DeepSeek 控制台吊销该 Key。

## 许可

提交贡献即表示你同意以 [MIT 许可](LICENSE) 发布你的代码。
