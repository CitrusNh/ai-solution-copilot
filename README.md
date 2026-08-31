# AI 企业研究与售前方案助手

这是一个面向 B2B AI/SaaS 售前、解决方案顾问和产品运营的可运行作品集项目。它把客户问题与企业产品资料连接起来，输出带来源的能力匹配、限制风险、追问清单和售前回复草稿。

## 业务场景

售前人员经常需要同时查阅产品说明、价格、部署和安全文档。如果资料没有明确承诺 BYOK、等保或数据驻留，直接回答“支持”会形成商业与合规风险。本项目要求结论必须来自检索证据，并在资料不足时转人工确认。

典型流程：

1. 上传 Markdown、TXT 或可提取文字的 PDF 产品资料。
2. 输入客户问题，例如“是否支持 BYOK？”或“私有化部署怎么收费？”。
3. 查看匹配能力、限制风险、来源引用和售前回复草稿。
4. 下载 Markdown 报告，或提交本地有用性反馈用于迭代。

## 当前状态

当前 MVP 已实现：

- 加载 Markdown 产品资料
- 按章节切分并保留来源
- 使用字符级 TF-IDF 与可解释的业务意图加权进行中文检索
- 展示前三条结果、来源和匹配分数
- 上传 Markdown、TXT 和可提取文字的 PDF
- 上传文件只在当前会话中处理，不写入 Git
- 基于检索证据生成本地规则版售前分析卡
- 输出需求摘要、匹配能力、限制风险、追问清单和回复草稿
- 下载包含完整来源证据的 Markdown 分析报告
- 本地记录“有用／部分有用／无用”和文字反馈
- 不调用大模型，不产生 API 费用
- 10 道冻结评测题严格通过率 100%，关键风险题 3/3
- 23 项自动化测试通过

## 本地运行

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

浏览器打开 `http://localhost:8501`。

## 部署公网 Demo

项目已经按 Streamlit Community Cloud 的入口结构准备好。完整步骤见 [DEPLOY.md](DEPLOY.md)。部署后会得到一个朋友可以直接打开的 `https://*.streamlit.app` 地址。

公网版本目前只适合演示资料，不要上传企业机密；项目没有登录、权限和云端数据库。

可以上传 `examples/upload_demo.txt`，然后查询“深圳现场培训多少钱？”。

## 运行本地基线评测

```powershell
.\.venv\Scripts\python.exe eval\evaluate.py
```

评测覆盖来源命中、Top-1、置信状态、关键事实和未知安全需求拒绝承诺。

## 运行Embedding对比评测

配置环境变量后运行：

```powershell
.\.venv\Scripts\python.exe eval\evaluate_embeddings.py --mode hybrid --budget-cny 1
```

文档向量和查询向量缓存在 `data/cache/`，不会提交到Git。程序会记录Token、API调用次数和费用，并在预计超过预算前停止。

Embedding 是可选实验，不是运行当前网页的前置条件。只有 API 服务商明确提供 `/v1/embeddings` 和对应 Embedding 模型时才需要配置。

## 安全说明

- API Key 只放在本地 `.env` 文件中。
- `.env`、Embedding 缓存、用户反馈、用户上传文件和输出文件不会提交到 Git。
