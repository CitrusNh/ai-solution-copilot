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

2026-08-31首次连通性请求在TLS握手阶段超时。公共DNS交叉验证显示Cloudflare与Google均返回`162.159.140.245`和`172.66.0.243`，本机系统DNS则返回不同地址；使用公共DNS地址并保留正确域名与TLS证书校验时，连接仍被网络重置。因此当前网络无法连接OpenAI API。

请求没有成功到达Embedding接口，已知Token用量为0、已知费用为0。Embedding客户端、缓存、1元预算保护、语义/混合检索和模拟API测试均已完成，18项自动化测试通过。待切换到可访问OpenAI API的可信网络，或配置用户认可的OpenAI兼容`OPENAI_BASE_URL`后运行真实对比。
