"""Streamlit entry point for the AI Solution Copilot."""

from pathlib import Path

import streamlit as st

from src.retrieve import load_markdown_chunks, search_chunks


st.set_page_config(
    page_title="AI 企业研究与售前方案助手",
    page_icon="🧭",
    layout="wide",
)

st.title("AI 企业研究与售前方案助手")
st.caption("MVP 0.1 · 先把客户需求、产品资料与可验证结论连接起来")

with st.sidebar:
    st.header("项目状态")
    st.success("MVP 第 1 个功能：本地资料检索已上线")
    st.write("当前不调用大模型，不产生 API 费用。")

st.subheader("今天要解决的问题")
st.write(
    "上传企业产品资料，输入客户需求，生成带来源引用的需求分析、产品匹配、能力缺口和售前回复草稿。"
)

data_dir = Path(__file__).parent / "data" / "demo"
chunks = load_markdown_chunks(data_dir)

st.divider()
st.subheader("在演示产品资料中检索")
st.write(f"已加载 **{len(chunks)}** 个资料片段，来自 **3** 份产品文档。")

with st.form("search_form"):
    query = st.text_input(
        "输入客户问题",
        placeholder="例如：专业版是否支持审计日志？",
    )
    submitted = st.form_submit_button("检索资料", type="primary")

st.caption("可以尝试：私有化部署怎么收费？／最多支持多少用户？／是否支持 BYOK？")

if submitted:
    if not query.strip():
        st.warning("请先输入一个客户问题。")
    else:
        results = search_chunks(query, chunks, top_k=3)
        if not results:
            st.warning("当前资料中没有找到相关内容，请换一种问法或交给人工确认。")
        else:
            st.markdown("### 检索结果")
            for rank, result in enumerate(results, start=1):
                with st.container(border=True):
                    st.markdown(f"**{rank}. {result.heading}**")
                    st.caption(
                        f"来源：{result.source} · 匹配分数：{result.score:.3f}"
                    )
                    st.write(result.content)

            st.info(
                "现在系统只负责找资料，还不会自动生成售前方案。"
                "下一阶段才会把检索结果交给大模型，并要求每个结论引用来源。"
            )
