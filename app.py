"""Streamlit entry point for the AI Solution Copilot."""

from pathlib import Path

import streamlit as st

from src.ingest import IngestionError, parse_document
from src.reporting import append_feedback, build_markdown_report, count_feedback
from src.retrieve import load_markdown_chunks, search_chunks
from src.solution_card import build_solution_card


st.set_page_config(
    page_title="AI 企业研究与售前方案助手",
    page_icon="🧭",
    layout="wide",
)

st.title("AI 企业研究与售前方案助手")
st.caption("MVP 0.6 · 把客户需求、企业产品资料与可验证结论连接起来")

project_root = Path(__file__).parent
feedback_path = project_root / "data" / "feedback" / "feedback.csv"

with st.sidebar:
    st.header("项目状态")
    st.success("本地可运行 MVP")
    st.write("检索、风险判断、来源引用、报告下载与反馈记录已上线。")
    st.metric("已记录测试反馈", count_feedback(feedback_path))
    st.info("当前使用本地增强关键词检索，不调用大模型，API 费用为 0。")

st.subheader("这个产品服务谁？")
persona, scenario, value = st.columns(3)
with persona:
    st.markdown("**使用者**")
    st.write("B2B AI/SaaS 公司的售前、解决方案顾问和产品运营。")
with scenario:
    st.markdown("**使用场景**")
    st.write("客户提出价格、部署、安全或功能问题，需要快速查阅多份产品资料。")
with value:
    st.markdown("**产品价值**")
    st.write("生成可追溯的回复草稿；资料没有承诺时明确转人工，降低错误承诺风险。")

with st.expander("查看一个真实使用例子"):
    st.write(
        "售前收到客户问题“是否支持 BYOK？”，上传或选择公司产品资料后发起检索。"
        "系统找到安全 FAQ，发现资料没有承诺 BYOK，于是提示人工确认，而不是编造支持结论。"
    )

data_dir = project_root / "data" / "demo"
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
            st.session_state.pop("current_analysis", None)
            st.warning("当前资料中没有找到相关内容，请换一种问法或交给人工确认。")
        else:
            card = build_solution_card(query, results)
            st.session_state["current_analysis"] = {
                "query": query,
                "card": card,
                "results": results,
            }

analysis = st.session_state.get("current_analysis")
if analysis:
    current_query = analysis["query"]
    card = analysis["card"]
    results = analysis["results"]

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

    report = build_markdown_report(card, results)
    st.download_button(
        "下载 Markdown 分析报告",
        data=report.encode("utf-8"),
        file_name="presales-analysis.md",
        mime="text/markdown",
    )

    st.markdown("### 检索证据")
    for rank, result in enumerate(results, start=1):
        with st.container(border=True):
            st.markdown(f"**{rank}. {result.heading}**")
            st.caption(f"来源：{result.source} · 匹配分数：{result.score:.3f}")
            st.write(result.content)

    st.markdown("### 结果反馈")
    st.caption("反馈只保存在本机，不上传到外部服务，也不会提交到 Git。")
    with st.form("feedback_form", clear_on_submit=True):
        rating = st.radio(
            "这份分析是否有用？",
            options=["有用", "部分有用", "无用"],
            horizontal=True,
        )
        note = st.text_area(
            "补充说明（可选）",
            placeholder="例如：价格结论正确，但希望减少无关限制。",
        )
        feedback_submitted = st.form_submit_button("保存反馈")
    if feedback_submitted:
        append_feedback(
            feedback_path,
            query=current_query,
            confidence=card.confidence,
            rating=rating,
            note=note,
        )
        st.success("反馈已保存到本机，可用于后续迭代分析。")

    st.info("当前分析卡由本地规则生成，是后续 Embedding 或大模型版本的对照基线。")
