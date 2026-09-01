"""Streamlit entry point for the AI Solution Copilot."""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.ingest import IngestionError, parse_document
from src.llm_analysis import ChatAnalysisService, LLMAnalysisError
from src.reporting import append_feedback, build_markdown_report, count_feedback
from src.retrieve import load_markdown_chunks, search_chunks
from src.solution_card import build_solution_card
from src.web_search import WebSearchError, search_web


load_dotenv()


def runtime_setting(name: str) -> str:
    """Read deployment secrets first, then local environment variables."""

    try:
        secret = st.secrets.get(name, "")
    except (FileNotFoundError, AttributeError):
        secret = ""
    return str(secret or os.environ.get(name, "")).strip()


st.set_page_config(
    page_title="AI 企业研究与售前方案助手",
    page_icon="🧭",
    layout="wide",
)

st.title("AI 企业研究与售前方案助手")
st.caption("把客户问题变成：有来源的产品结论、风险提示和售前回复草稿")

st.info(
    "第一次使用不用上传文件，系统已经准备了 3 份演示资料。\n\n"
    "**只需 3 步：** ① 输入客户问题 → ② 点击“生成售前分析卡” → ③ 查看结论、来源和回复草稿。"
)

project_root = Path(__file__).parent
feedback_path = project_root / "data" / "feedback" / "feedback.csv"
chat_api_key = runtime_setting("OPENAI_API_KEY")
chat_base_url = runtime_setting("OPENAI_BASE_URL")
chat_model = runtime_setting("CHAT_MODEL") or runtime_setting("OPENAI_MODEL")
chat_ready = bool(chat_api_key and chat_model)

with st.sidebar:
    st.header("项目状态")
    st.success("公开可运行 MVP 1.0")
    st.write("本地检索和风险判断始终可用，外部能力失败时会安全降级。")
    st.metric("已记录测试反馈", count_feedback(feedback_path))
    st.write("OCR：自动识别扫描 PDF")
    st.write("联网搜索：按次由用户开启")
    if chat_ready:
        st.write(f"聊天模型：已配置 `{chat_model}`")
    else:
        st.warning("聊天模型尚未配置；当前使用本地规则分析。")

data_dir = project_root / "data" / "demo"
demo_chunks = load_markdown_chunks(data_dir)

st.divider()
st.subheader("1. 输入客户问题")
st.caption("可直接使用内置演示资料；如果要测试自己的产品，再补充上传资料。")

with st.form("search_form"):
    query = st.text_input(
        "客户问题",
        placeholder="例如：专业版是否支持审计日志？",
        help="把客户原话直接粘贴进来即可，例如价格、部署、安全或功能问题。",
    )
    web_enabled = st.checkbox(
        "联网搜索公开资料",
        value=False,
        help="只把当前问题发送给公开搜索服务，不上传企业文档。互联网资料不会被用来证明本产品能力。",
    )
    ai_enabled = st.checkbox(
        "使用聊天模型增强分析",
        value=False,
        disabled=not chat_ready,
        help="会把客户问题和命中的内部资料片段发送给部署者配置的模型服务商。",
    )
    submitted = st.form_submit_button("生成售前分析卡", type="primary")

st.caption("推荐先试：私有化部署怎么收费？／最多支持多少用户？／是否支持 BYOK？")
st.caption("提交后，结果会显示在本页下方：先看结论，再看来源、风险和回复草稿。")

with st.expander("2. 可选：补充企业资料（第一次使用可以跳过）"):
    st.caption(
        "上传后会与内置演示资料一起检索。支持 Markdown、TXT、普通或扫描版 PDF；"
        "每个文件不超过 10MB，扫描 PDF 最多识别 20 页。文件只在当前会话中处理。"
    )
    uploaded_files = st.file_uploader(
        "上传产品说明、价格表或安全 FAQ",
        type=["md", "txt", "pdf"],
        accept_multiple_files=True,
        help="上传资料不会写入 Git，也不会自动发送给联网搜索服务。",
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
    ocr_count = sum("· OCR" in chunk.heading for chunk in uploaded_chunks)
    st.success(
        f"成功解析 {len(uploaded_files)} 个上传文件，得到 {len(uploaded_chunks)} 个资料片段。"
    )
    if ocr_count:
        st.info(f"其中 {ocr_count} 个资料片段来自扫描页 OCR。")
for error in upload_errors:
    st.error(error)

chunks = [*demo_chunks, *uploaded_chunks]
source_count = len({chunk.source for chunk in chunks})

st.divider()
st.subheader("当前资料状态")
st.write(
    f"当前共加载 **{len(chunks)}** 个资料片段，来自 **{source_count}** 份文档。"
)

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
            web_results = []
            web_error = ""
            if web_enabled:
                try:
                    with st.spinner("正在检索互联网公开资料..."):
                        web_results = search_web(query, max_results=4)
                except WebSearchError as exc:
                    web_error = str(exc)

            ai_analysis = None
            ai_error = ""
            if ai_enabled:
                try:
                    with st.spinner("正在生成证据约束的 AI 分析..."):
                        ai_analysis = ChatAnalysisService(
                            api_key=chat_api_key,
                            base_url=chat_base_url or None,
                            model=chat_model,
                        ).generate(
                            query,
                            card,
                            results,
                            web_results=web_results,
                        )
                except LLMAnalysisError as exc:
                    ai_error = str(exc)
            st.session_state["current_analysis"] = {
                "query": query,
                "card": card,
                "results": results,
                "web_results": web_results,
                "web_error": web_error,
                "ai_analysis": ai_analysis,
                "ai_error": ai_error,
            }

analysis = st.session_state.get("current_analysis")
if analysis:
    current_query = analysis["query"]
    card = analysis["card"]
    results = analysis["results"]
    web_results = analysis.get("web_results", [])
    web_error = analysis.get("web_error", "")
    ai_analysis = analysis.get("ai_analysis")
    ai_error = analysis.get("ai_error", "")

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

    if ai_error:
        st.warning(f"AI 增强未启用：{ai_error} 已保留本地规则结果。")
    if ai_analysis is not None:
        st.markdown("### AI 增强分析")
        with st.container(border=True):
            st.markdown("#### 分析摘要")
            st.write(ai_analysis.analysis_summary)
            st.markdown("#### AI 售前回复草稿")
            st.write(ai_analysis.customer_reply_draft)
            if ai_analysis.risks:
                st.markdown("#### 补充风险")
                for item in ai_analysis.risks:
                    st.write(f"- {item}")
            if ai_analysis.follow_up_questions:
                st.markdown("#### 补充追问")
                for index, item in enumerate(ai_analysis.follow_up_questions, start=1):
                    st.write(f"{index}. {item}")
            st.caption(
                f"模型：{ai_analysis.model} · 输入 Token：{ai_analysis.prompt_tokens} · "
                f"输出 Token：{ai_analysis.completion_tokens}"
            )

    report = build_markdown_report(
        card,
        results,
        ai_analysis=ai_analysis,
        web_results=web_results,
    )
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

    if web_error:
        st.warning(f"联网搜索未完成：{web_error} 本地资料分析不受影响。")
    if web_results:
        st.markdown("### 互联网公开资料")
        st.caption("只用于行业背景和公开信息补充，不能作为本产品能力承诺依据。")
        for index, item in enumerate(web_results, start=1):
            with st.container(border=True):
                st.markdown(f"**W{index}. {item.title}**")
                st.write(item.snippet)
                st.link_button("打开来源网页", item.url)

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

    st.info("本地规则分析是安全基线；AI 和联网能力失败时不会影响内部资料检索结果。")
