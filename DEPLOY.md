# 公网部署说明（Streamlit Community Cloud）

本项目是一个不依赖付费 API 的 Streamlit Demo，适合部署到 Streamlit Community Cloud，生成一个朋友可以直接打开的 `https://*.streamlit.app` 地址。

## 部署前检查

- 仓库中只保留演示资料，不上传企业机密文件。
- 不要上传 `.env`、API Key、Embedding 缓存或本地反馈文件。
- `requirements.txt` 已列出运行依赖。
- 应用入口是根目录下的 `app.py`。

## 发布步骤

1. 在 GitHub 创建一个 **Public** 仓库，例如 `ai-solution-copilot`。
2. 将本项目的 `main` 分支推送到该仓库。
3. 登录 [Streamlit Community Cloud](https://share.streamlit.io/)，选择 **Deploy an app**。
4. 选择 GitHub 仓库、分支 `main` 和入口文件 `app.py`。
5. 点击部署，等待构建完成。
6. 用无痕窗口打开生成的公网地址，验证上传、检索、报告下载和反馈记录功能。

## 公网版本的边界

当前版本没有登录、权限和云端数据库。它适合公开展示和使用演示资料，不适合上传真实客户资料或企业机密文件。

反馈会写入运行实例的本地文件，云端重启后可能丢失；这正是后续版本需要接入数据库的产品迭代点。

## 更新方式

修改代码并推送到 GitHub 后，Streamlit Community Cloud 通常会自动重新部署。部署失败时，先查看 **Manage app → Logs**，重点检查依赖安装和 Python 版本错误。
