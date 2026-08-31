"""Streamlit entry point for the AI Solution Copilot."""

from pathlib import Path

import streamlit as st

from src.ingest import IngestionError, parse_document
from src.retrieve import load_markdown_chunks, search_chunks
from src.solution_card import build_solution_card


st.set_page_config(
    page_title="AI 企业研究与售前方案助手",
    page_icon="🧭",
    layout="wide",
)

st.title("AI 企业研究与售前方案助手")
st.caption("MVP 0.1 · 先把客户需求、产品资料与可验证结论连接起来")

with st.sidebar:
    st.header("项目状态")
    st.success("MVP 第 3 个功能：本地售前分析卡已上线")
    st.write("当前不调用大模型，不产生 API 费用。")

st.subheader("今天要解决的问题")
st.write(
    "上传企业产品资料，输入客户需求，生成带来源引用的需求分析、产品匹配、能力缺口和售前回复草稿。"
)

data_dir = Path(__file__).parent / "data" / "demo"
demo_chunks = load_markdown_chunks(data_dir)

st.divider()
st.subheader("1. 准备知识资料")
uploaded_files = st.file_uploader(
    "上传补充产品资料",
    type=["md", "txt", "pdf"],
    accept_multiple_files=True,
    help="支持 Markdown、TXT、可提取文字的 PDF；每个文件不超过 10MB。文件只在当前会话中处理。",
)

uploaded_chunks = []
upload_errors = []
for uploaded_file in uploaded_files:
    try:
        uploaded_chunks.extend(
            parse_document(uploaded_file.name, uploaded_file.getvalue())
        )
    except IngestionError as exc:
        upload_errors.append(f"{uploaded_file.name}：{exc}")

if uploaded_files and not upload_errors:
    st.success(
        f"成功解析 {len(uploaded_files)} 个上传文件，得到 {len(uploaded_chunks)} 个资料片段。"
    )
for error in upload_errors:
    st.error(error)

chunks = [*demo_chunks, *uploaded_chunks]
source_count = len({chunk.source for chunk in chunks})

st.divider()
st.subheader("2. 检索知识资料")
st.write(
    f"当前共加载 **{len(chunks)}** 个资料片段，来自 **{source_count}** 份文档。"
)

with st.form("search_form"):
    query = st.text_input(
        "输入客户问题",
        placeholder="例如：专业版是否支持审计日志？",
    )
    submitted = st.form_submit_button("生成售前分析卡", type="primary")

st.caption("可以尝试：私有化部署怎么收费？／最多支持多少用户？／是否支持 BYOK？")

if submitted:
    if not query.strip():
        st.warning("请先输入一个客户问题。")
    else:
        results = search_chunks(query, chunks, top_k=3)
        if not results:
            st.warning("当前资料中没有找到相关内容，请换一种问法或交给人工确认。")
        else:
            card = build_solution_card(query, results)

            st.markdown("### 售前分析卡")
            with st.container(border=True):
                st.markdown("#### 客户需求摘要")
                st.write(card.request_summary)
                if card.confidence == "资料可支持初步回复":
                    st.success(card.confidence)
                else:
                    st.warning(card.confidence)

                st.markdown("#### 匹配能力")
                if card.matched_capabilities:
                    for item in card.matched_capabilities:
                        st.markdown(f"- {item.text}")
                        st.caption(f"来源：{item.source} · {item.heading}")
                else:
                    st.write("当前资料中没有可确认的产品能力。")

                st.markdown("#### 限制与风险")
                if card.constraints_and_risks:
                    for item in card.constraints_and_risks:
                        st.markdown(f"- {item.text}")
                        st.caption(f"来源：{item.source} · {item.heading}")
                else:
                    st.write("当前检索片段中没有明确写出的限制；这不代表不存在限制。")

                st.markdown("#### 建议继续询问客户")
                for index, question in enumerate(card.open_questions, start=1):
                    st.write(f"{index}. {question}")

                st.markdown("#### 售前回复草稿")
                st.write(card.reply_draft)

            st.markdown("### 检索证据")
            for rank, result in enumerate(results, start=1):
                with st.container(border=True):
                    st.markdown(f"**{rank}. {result.heading}**")
                    st.caption(
                        f"来源：{result.source} · 匹配分数：{result.score:.3f}"
                    )
                    st.write(result.content)

            st.info("当前分析卡由本地规则生成，是后续大模型版本的对照基线。")
