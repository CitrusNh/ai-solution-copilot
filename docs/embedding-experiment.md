# Embedding 检索实验设计

## 假设

字符级 TF-IDF 在“专业版价格和用户上限”问题上把审计 FAQ 排在价格资料之前。语义Embedding应更好地区分“价格/人数”与“审计”，混合检索则同时保留精确关键词能力。

## 候选方案

- 模型：`text-embedding-3-small`
- 向量维度：512
- 语义检索：余弦相似度
- 混合检索：关键词排名与语义排名的加权倒数排名融合
- 缓存：按模型、维度和原文哈希保存本地向量
- 预算：本轮最多1元人民币

## 官方依据

- [OpenAI Embeddings指南](https://developers.openai.com/api/docs/guides/embeddings)
- [`text-embedding-3-small`模型页](https://developers.openai.com/api/docs/models/text-embedding-3-small)

官方文档说明Embedding可用于按查询相关性排序搜索结果；模型页在本次实验日期显示输入价格为每100万Token 0.02美元。

## 决策规则

- 关键风险题必须继续3/3通过。
- Top-1准确率目标从90%提升到100%。
- Top-3命中率不得低于100%的现有基线。
- 实际费用不得超过1元人民币。
- 如果准确率没有提升，则不因“使用了Embedding”而默认采用。

## 当前状态

2026-09-01 使用用户认可的 APINebula OpenAI 兼容地址重新验证：`/v1/models` 可以连接，但当前 token 只返回 `gpt-image-2`，没有返回 Embedding 模型。随后用极小输入探测 `text-embedding-3-small`，服务端返回 HTTP 403，明确说明当前 token 没有该模型权限。

探测没有成功生成向量，已知 Token 用量和已知费用均为 0。充值只解决账户余额，不能自动增加模型权限；在服务商为该 token 开通 Embedding 模型并能从 `/v1/models` 查到之前，不运行完整 10 题付费对比。当前网页继续使用已通过 10/10 开发评测的本地检索，不受影响。

Embedding 客户端、缓存、1 元预算保护、语义/混合检索和模拟 API 测试均已完成。获得可用模型权限后，再运行：

```powershell
$env:OPENAI_BASE_URL="https://apinebula.ai/v1"
$env:EMBEDDING_MODEL="服务商明确提供的 Embedding 模型名"
.\.venv\Scripts\python.exe eval\evaluate_embeddings.py --mode hybrid --budget-cny 1
```
