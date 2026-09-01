# 公网部署说明（Streamlit Community Cloud）

本项目可以部署到 Streamlit Community Cloud，生成朋友或面试官可直接打开的 `https://*.streamlit.app` 地址。本地检索、规则分析、联网搜索和 OCR 不依赖聊天模型 API；聊天增强需要单独配置 Secrets。

## 部署前检查

- 仓库中只保留虚构演示资料，不上传企业机密文件。
- 不要上传 `.env`、API Key、Embedding 缓存或本地反馈文件。
- `requirements.txt` 已列出运行依赖，应用入口为根目录 `app.py`。
- OCR 首次加载模型会比普通文本解析慢，单个扫描 PDF 最多处理 20 个扫描页。

## 发布步骤

1. 将项目 `main` 分支推送到公开 GitHub 仓库。
2. 登录 [Streamlit Community Cloud](https://share.streamlit.io/)，选择 **Deploy an app**。
3. 选择仓库、分支 `main` 和入口文件 `app.py`。
4. 点击部署并等待依赖安装完成。
5. 用无痕窗口打开公网地址，验证普通检索、联网搜索、扫描 PDF、报告下载和失败降级。

## 配置可选聊天模型

只有 API 服务商明确给该 Key 开通聊天模型权限时才配置。在 **Manage app → Settings → Secrets** 中填写：

```toml
OPENAI_API_KEY = "你的聊天模型 API Key"
OPENAI_BASE_URL = "https://服务商提供的兼容接口地址/v1"
CHAT_MODEL = "服务商提供的聊天模型名"
```

保存后应用会重新启动。侧栏显示“聊天模型：已配置”且表单中的“使用聊天模型增强分析”可勾选，才算配置成功。不要使用只开放 `gpt-image-2` 的 Key，也不要把 Key 提交到 GitHub。

## 公网版本边界

- 没有登录、权限、云端数据库、多租户隔离或安全审计。
- 上传资料在当前会话中解析，但公共 Demo 仍不适合处理真实客户资料。
- 反馈写入运行实例本地文件，云端重启后可能丢失。
- 联网搜索服务可能因网络或限流失败；失败时本地分析仍可使用。
- 未配置聊天 Secrets 时自动使用本地规则分析，不影响核心演示。

## 更新与排错

推送到 GitHub `main` 后，Streamlit Community Cloud 通常会自动重新部署。部署失败时进入 **Manage app → Logs**：

1. 依赖安装失败：检查 `requirements.txt` 中的包名和构建日志。
2. 聊天开关不可用：检查三个 Secrets 是否存在，模型名是否有权限。
3. OCR 初始化失败：确认 `PyMuPDF`、`rapidocr_onnxruntime` 已安装，并查看内存相关日志。
4. 联网搜索失败：稍后重试；这不影响本地资料检索。
