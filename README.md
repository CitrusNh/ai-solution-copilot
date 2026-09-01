# AI 企业研究与售前方案助手

这是一个面向 B2B AI/SaaS 售前、解决方案顾问和产品运营的可运行作品集项目。它把客户问题与企业产品资料连接起来，输出带来源的能力匹配、限制风险、追问清单和售前回复草稿。

**在线 Demo：** [ai-solution-copilot.streamlit.app](https://ai-solution-copilot-fn445bidjzbyu35ars4k6q.streamlit.app/)

**作品集材料：** [系统架构](docs/architecture.md) · [项目经历与简历描述](docs/portfolio-package.md) · [演示脚本](docs/demo-script.md) · [HR 话术](docs/hr-pitch.md) · [面试讲解](docs/interview-guide.md) · [最终验证报告](eval/final-report.md)

## 业务场景

售前人员经常需要同时查阅产品说明、价格、部署和安全文档。如果资料没有明确承诺 BYOK、等保或数据驻留，直接回答“支持”会形成商业与合规风险。本项目要求产品能力结论必须来自内部资料，并在资料不足时转人工确认。

典型流程：

1. 上传 Markdown、TXT、普通 PDF 或扫描版 PDF 产品资料。
2. 输入客户问题，例如“是否支持 BYOK？”或“私有化部署怎么收费？”。
3. 按需开启联网搜索和聊天模型增强。
4. 查看本地规则基线、来源证据、风险边界和 AI 增强草稿。
5. 下载 Markdown 报告，或提交本地有用性反馈用于迭代。

## MVP 1.0 能力

- 解析 Markdown、TXT、普通 PDF，并通过本地 RapidOCR 识别扫描版 PDF。
- 按章节或页切分资料，保留文件名、章节、页码和 OCR 标记。
- 使用字符级 TF-IDF 与业务意图加权进行可解释中文检索。
- 基于检索证据生成本地规则版售前分析卡，外部服务失败时仍可工作。
- 对 BYOK、等保、数据驻留等未承诺需求阻断无依据承诺并转人工确认。
- 用户按次开启公开网络搜索；客户问题会发送给搜索服务，企业文档不会上传。
- 支持 OpenAI 兼容聊天接口，返回固定 JSON 结构并校验证据编号和人工确认边界。
- 内部证据使用 `[D1]`，互联网资料使用 `[W1]`，互联网资料不能证明本产品能力。
- 下载包含本地结论、AI 分析和来源的 Markdown 报告，并记录本地反馈。
- 10 道冻结开发评测题 10/10 通过，39 项自动化测试通过。

聊天增强是可选能力，只有部署者在 Secrets 中配置有聊天模型权限的 Key 和模型名后，页面开关才会启用。2026-09-01 已在公网 Demo 使用 `deepseek-v4-flash` 完成真实调用冒烟测试：价格题生成带内部引用的回复，BYOK 题保留“不能承诺、人工确认”边界。模型服务仍可能受额度、延迟和输出格式影响，失败时会保留本地规则结果。

这不是生产系统：没有登录、权限、云端持久化、多租户隔离或安全审计。公网 Demo 只应使用演示资料或非敏感文件；真实企业用户反馈尚未收集，不把开发者自测当作市场验证。

## 本地运行

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

浏览器打开 `http://localhost:8501`。终端进程需要保持运行；关闭终端会停止本地网页服务。公网 Demo 不需要用户电脑保持终端运行。

## 可选聊天模型配置

在本地项目根目录创建 `.env`，或在 Streamlit Community Cloud 的 Secrets 中配置：

```toml
OPENAI_API_KEY = "你的聊天模型 API Key"
OPENAI_BASE_URL = "https://服务商提供的兼容接口地址/v1"
CHAT_MODEL = "服务商明确支持的聊天模型名"
```

不要把真实 Key 写进 `.env.example`、代码、截图或 Git。`CHAT_MODEL` 必须是聊天模型，不是 `gpt-image-2` 或 Embedding 模型。

## 部署公网 Demo

项目已经按 Streamlit Community Cloud 的入口结构准备好。完整步骤见 [DEPLOY.md](DEPLOY.md)。修改推送到 `main` 后，云端通常会自动重新部署。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe eval\evaluate.py
```

评测覆盖来源命中、Top-1、置信状态、关键事实和未知安全需求拒绝承诺。Embedding 对比仍是可选实验，说明见 [docs/embedding-experiment.md](docs/embedding-experiment.md)。

## 安全说明

- API Key 只放在本地 `.env` 或部署平台 Secrets。
- `.env`、Embedding 缓存、用户反馈、用户上传文件和输出文件不会提交到 Git。
- 开启聊天增强会把客户问题和命中的 Top-3 内部片段发送给所配置的模型服务商。
- 开启联网搜索只发送客户问题；公开网页结果与内部产品证据分区展示。
