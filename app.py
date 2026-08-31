"""Streamlit entry point for the AI Solution Copilot."""

import streamlit as st


st.set_page_config(
    page_title="AI 企业研究与售前方案助手",
    page_icon="🧭",
    layout="wide",
)

st.title("AI 企业研究与售前方案助手")
st.caption("MVP 0.1 · 先把客户需求、产品资料与可验证结论连接起来")

with st.sidebar:
    st.header("项目状态")
    st.info("环境初始化完成后，我们将从文档上传和基础检索开始。")

st.subheader("今天要解决的问题")
st.write(
    "上传企业产品资料，输入客户需求，生成带来源引用的需求分析、产品匹配、能力缺口和售前回复草稿。"
)

st.warning("当前还是骨架页面：还没有接入模型、文档解析和检索。")

