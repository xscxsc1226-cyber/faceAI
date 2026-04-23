import time
import io
import json
import hashlib
import queue
import re
import wave
import tempfile
import os
from datetime import datetime
from typing import List, Tuple
from urllib.parse import urlparse

import numpy as np
import requests
import streamlit as st
import streamlit.components.v1 as components
from requests.exceptions import RequestException
from settings import load_settings
from privacy_ops import can_encrypt, encrypt_bytes, get_privacy_notice
from faster_whisper import WhisperModel
from storage import (
    count_recent_api_calls,
    delete_user_all_data,
    get_cost_summary,
    get_report,
    init_db,
    list_reports,
    purge_reports_older_than,
    record_api_usage,
    save_report,
)
from supabase_ops import (
    SUPABASE_AVAILABLE,
    delete_user_cloud_data,
    get_cloud_report,
    is_supabase_configured,
    list_cloud_reports,
    purge_cloud_reports_older_than,
    save_cloud_report,
    sign_in_with_password,
    sign_up_with_password,
    upload_audio_blob,
)

try:
    from pypdf import PdfReader

    PDF_READER_AVAILABLE = True
except ImportError:
    PDF_READER_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

APP_SETTINGS = load_settings()
init_db(APP_SETTINGS.sqlite_path)

try:
    from streamlit_autorefresh import st_autorefresh

    AUTOREFRESH_AVAILABLE = True
except ImportError:
    AUTOREFRESH_AVAILABLE = False

try:
    from streamlit_webrtc import WebRtcMode, webrtc_streamer

    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False


st.set_page_config(
    page_title="AI 面试官",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_base_style() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: #050506;
            color: #f3f3f4;
        }
        html, body, [class*="css"] {
            color-scheme: dark;
        }
        [data-testid="stAppViewContainer"] {
            background: #050506;
        }
        [data-testid="stHeader"] {
            background: transparent;
        }
        [data-testid="stSidebar"],
        section[data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid rgba(0,0,0,0.08);
        }
        [data-testid="stSidebar"] > div,
        [data-testid="stSidebarContent"],
        section[data-testid="stSidebar"] > div {
            background: #ffffff !important;
        }
        [data-testid="stSidebar"] *,
        [data-testid="stSidebarContent"] * {
            color: #0f1012 !important;
        }
        [data-testid="stSidebar"] .stTextInput input,
        [data-testid="stSidebar"] .stTextArea textarea,
        [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div,
        [data-testid="stSidebar"] .stNumberInput input,
        [data-testid="stSidebar"] .stRadio label,
        [data-testid="stSidebar"] .stSelectbox label {
            background: #ffffff !important;
            color: #111111 !important;
            border: 1px solid #d9d9de !important;
        }
        [data-testid="stSidebar"] .stButton > button {
            background: #ffffff !important;
            color: #111111 !important;
            border: 1px solid #cfcfd6 !important;
        }

        .main-title {
            font-size: 2.2rem;
            font-weight: 700;
            letter-spacing: 0.4px;
            margin-bottom: 0.3rem;
            color: #fcfcfd;
        }

        .sub-title {
            color: #b2b2b8;
            margin-bottom: 1.2rem;
            font-size: 0.95rem;
        }

        .glass-card {
            background: #0f1011;
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 16px;
            padding: 1rem 1.2rem;
            margin-bottom: 1rem;
            box-shadow: 0 8px 30px rgba(0,0,0,0.35);
        }

        .section-title {
            font-size: 1.05rem;
            font-weight: 600;
            margin-bottom: 0.8rem;
        }

        .result-block {
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.12);
            padding: 0.9rem;
            background: #151617;
            margin-bottom: 0.6rem;
        }

        [data-testid="stMain"] h1,
        [data-testid="stMain"] h2,
        [data-testid="stMain"] h3,
        [data-testid="stMain"] h4,
        [data-testid="stMain"] p,
        [data-testid="stMain"] label,
        [data-testid="stMain"] li,
        [data-testid="stMain"] span,
        [data-testid="stMain"] div,
        [data-testid="stMain"] strong {
            color: #f2f2f5 !important;
        }
        [data-testid="stMain"] .stCaption {
            color: #c8c8ce !important;
        }
        [data-testid="stMain"] .stTextInput input,
        [data-testid="stMain"] .stTextArea textarea {
            background: #111214 !important;
            color: #f4f4f6 !important;
            border: 1px solid rgba(255,255,255,0.16) !important;
        }

        .stButton > button,
        .stDownloadButton > button {
            background: #ffffff !important;
            color: #0c8f3e !important;
            border: 1px solid #dedee3 !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
        }
        .stButton > button[kind="primary"],
        .stDownloadButton > button[kind="primary"] {
            background: #ffffff !important;
            color: #0c8f3e !important;
            border: 1px solid #d6d6dc !important;
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover {
            background: #f3f3f5 !important;
            color: #087534 !important;
            border-color: #c8c8cf !important;
        }
        .stButton > button:active,
        .stDownloadButton > button:active {
            color: #06682d !important;
        }
        .stButton > button:focus,
        .stDownloadButton > button:focus {
            box-shadow: 0 0 0 1px #d0d0d6 !important;
        }
        [data-testid="stFileUploader"] button {
            background: #ffffff !important;
            color: #0c8f3e !important;
            border: 1px solid #d6d6dc !important;
            font-weight: 600 !important;
        }
        [data-testid="stFileUploader"] button:hover {
            background: #f3f3f5 !important;
            color: #087534 !important;
            border-color: #c8c8cf !important;
        }
        [data-testid="stFileUploader"] button:disabled {
            background: #f8f8fa !important;
            color: #0c8f3e !important;
            opacity: 0.9 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    defaults = {
        "api_key": APP_SETTINGS.default_api_key,
        "base_url": APP_SETTINGS.default_base_url,
        "interview_mode": "技术面",
        "resume_file": None,
        "jd_text": "",
        "experience_text": "",
        "question_bank": [],
        "in_interview_room": False,
        "subtitle_lines": [],
        "last_transcript": "",
        "last_audio_digest": "",
        "transcribe_error": "",
        "vad_chunks": [],
        "vad_is_recording": False,
        "vad_silence_ms": 0,
        "vad_sample_rate": 16000,
        "auto_listen_enabled": False,
        "interview_history": [],
        "current_question": "",
        "question_error": "",
        "last_spoken_question_key": "",
        "interview_report": None,
        "report_error": "",
        "interview_bootstrapped": False,
        "resume_text_cache": "",
        "resume_file_digest": "",
        "question_model": APP_SETTINGS.default_question_model,
        "evaluation_model": APP_SETTINGS.default_evaluation_model,
        "whisper_model": APP_SETTINGS.default_whisper_model,
        "api_test_status": "",
        "interview_started_at": "",
        "interview_ended_at": "",
        "history_selected_id": 0,
        "auth_email": "",
        "auth_password": "",
        "auth_user_id": "local",
        "auth_logged_in": False,
        "auth_access_token": "",
        "auth_refresh_token": "",
        "auth_status": "",
        "audio_objects": [],
        "retention_checked": False,
        "privacy_notice": "",
        "use_cloud_storage": APP_SETTINGS.enable_cloud_sync,
        "asr_mode": "本地 faster-whisper",
        "local_whisper_size": "base",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # 当已有会话状态为空值时，回填 .env 默认配置，避免“看起来未生效”。
    if not st.session_state.get("api_key"):
        st.session_state.api_key = APP_SETTINGS.default_api_key
    if not st.session_state.get("base_url"):
        st.session_state.base_url = APP_SETTINGS.default_base_url
    if not st.session_state.get("question_model"):
        st.session_state.question_model = APP_SETTINGS.default_question_model
    if not st.session_state.get("evaluation_model"):
        st.session_state.evaluation_model = APP_SETTINGS.default_evaluation_model
    if not st.session_state.get("whisper_model"):
        st.session_state.whisper_model = APP_SETTINGS.default_whisper_model


def reload_defaults_from_env() -> None:
    latest = load_settings()
    st.session_state.api_key = latest.default_api_key
    st.session_state.base_url = latest.default_base_url
    st.session_state.question_model = latest.default_question_model
    st.session_state.evaluation_model = latest.default_evaluation_model
    st.session_state.whisper_model = latest.default_whisper_model
    st.session_state.api_test_status = "已从 .env 重新加载默认配置。"


def read_txt_upload(uploaded_file) -> str:
    if not uploaded_file:
        return ""
    return uploaded_file.getvalue().decode("utf-8", errors="ignore")


def extract_resume_text(uploaded_pdf) -> str:
    if not uploaded_pdf:
        return ""
    if not PDF_READER_AVAILABLE:
        return ""
    try:
        pdf_bytes = uploaded_pdf.getvalue()
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(part.strip() for part in pages if part.strip())
    except Exception:
        return ""


def get_resume_context_text() -> str:
    parts = []
    if st.session_state.get("resume_text_cache"):
        parts.append(f"【简历文本】\n{st.session_state.resume_text_cache}")
    if st.session_state.get("jd_text"):
        parts.append(f"【目标岗位JD】\n{st.session_state.jd_text}")
    if st.session_state.get("experience_text"):
        parts.append(f"【过往面经】\n{st.session_state.experience_text}")
    return "\n\n".join(parts).strip()


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ts_short(ts: str) -> str:
    if not ts:
        return "--:--:--"
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").strftime("%H:%M:%S")
    except ValueError:
        return ts


def is_cloud_enabled() -> bool:
    return is_supabase_configured(
        APP_SETTINGS.supabase_url, APP_SETTINGS.supabase_anon_key, st.session_state.use_cloud_storage
    )


def current_user_id() -> str:
    if st.session_state.get("auth_logged_in") and st.session_state.get("auth_user_id"):
        return st.session_state.auth_user_id
    return "local"


def ensure_retention_policy_once() -> None:
    if st.session_state.retention_checked:
        return
    purged_local = purge_reports_older_than(APP_SETTINGS.sqlite_path, APP_SETTINGS.retention_days)
    st.session_state.privacy_notice = get_privacy_notice(
        APP_SETTINGS.retention_days, can_encrypt(APP_SETTINGS.encryption_key)
    )
    if is_cloud_enabled() and st.session_state.get("auth_access_token") and current_user_id() != "local":
        try:
            purge_cloud_reports_older_than(
                APP_SETTINGS.supabase_url,
                APP_SETTINGS.supabase_anon_key,
                st.session_state.auth_access_token,
                current_user_id(),
                APP_SETTINGS.retention_days,
            )
        except Exception:
            pass
    st.session_state.retention_checked = True
    if purged_local > 0:
        st.session_state.auth_status = f"已清理本地过期记录：{purged_local} 条。"


def estimate_cost_usd(endpoint: str, req_chars: int, res_chars: int) -> float:
    # 仅用于成本趋势观察，非精确计费。
    total_tokens = max((req_chars + res_chars) / 4.0, 1)
    if endpoint == "whisper":
        return total_tokens * 0.0000008
    return total_tokens * 0.000002


def enforce_rate_limit_or_raise(endpoint: str) -> None:
    user_id = current_user_id()
    recent = count_recent_api_calls(APP_SETTINGS.sqlite_path, user_id, seconds=60)
    if recent >= APP_SETTINGS.max_api_requests_per_minute:
        raise RuntimeError(
            f"触发 API 限流：最近 1 分钟已调用 {recent} 次。"
            f"上限为 {APP_SETTINGS.max_api_requests_per_minute} 次/分钟。"
        )


def record_usage(endpoint: str, request_chars: int, response_chars: int) -> None:
    record_api_usage(
        APP_SETTINGS.sqlite_path,
        current_user_id(),
        endpoint,
        request_chars,
        response_chars,
        estimate_cost_usd(endpoint, request_chars, response_chars),
    )


def clear_all_user_data() -> None:
    uid = current_user_id()
    deleted_local = delete_user_all_data(APP_SETTINGS.sqlite_path, uid)
    if is_cloud_enabled() and st.session_state.get("auth_access_token") and uid != "local":
        try:
            delete_user_cloud_data(
                APP_SETTINGS.supabase_url,
                APP_SETTINGS.supabase_anon_key,
                st.session_state.auth_access_token,
                uid,
                APP_SETTINGS.supabase_bucket,
            )
        except Exception as exc:
            st.session_state.auth_status = f"云端删除失败：{exc}"
            return
    st.session_state.interview_report = None
    st.session_state.history_selected_id = 0
    st.session_state.auth_status = f"已删除你的历史数据（本地 {deleted_local} 条）。"


def append_dialogue(role: str, content: str) -> None:
    line = (content or "").strip()
    if not line:
        return
    speaker = "候选人" if role == "user" else "面试官"
    timestamp = now_ts()
    st.session_state.interview_history.append(
        {"role": role, "content": line, "timestamp": timestamp}
    )
    st.session_state.subtitle_lines.append(f"[{ts_short(timestamp)}] {speaker}：{line}")


def reset_interview_runtime_state(keep_report: bool = True) -> None:
    st.session_state.auto_listen_enabled = False
    st.session_state.subtitle_lines = []
    st.session_state.interview_history = []
    st.session_state.current_question = ""
    st.session_state.question_error = ""
    st.session_state.last_spoken_question_key = ""
    st.session_state.interview_bootstrapped = False
    st.session_state.report_error = ""
    st.session_state.transcribe_error = ""
    st.session_state.interview_started_at = ""
    st.session_state.interview_ended_at = ""
    st.session_state.audio_objects = []
    reset_vad_state()
    if not keep_report:
        st.session_state.interview_report = None


def get_launch_readiness_items() -> List[Tuple[str, bool, str]]:
    has_api = bool(st.session_state.get("api_key", "").strip())
    has_base = bool(st.session_state.get("base_url", "").strip())
    has_question_model = bool(st.session_state.get("question_model", "").strip())
    has_evaluation_model = bool(st.session_state.get("evaluation_model", "").strip())
    asr_cloud_ok = (
        st.session_state.get("asr_mode") != "云端兼容 Whisper API"
        or bool(st.session_state.get("whisper_model", "").strip())
    )
    has_resume_context = bool(get_resume_context_text())
    deps_ready = WEBRTC_AVAILABLE and AUTOREFRESH_AVAILABLE and PDF_READER_AVAILABLE
    cloud_ok = (not st.session_state.use_cloud_storage) or is_cloud_enabled()
    auth_ok = (not st.session_state.use_cloud_storage) or st.session_state.auth_logged_in
    return [
        ("API Key 已配置", has_api, "未填写将无法进行转写、追问与评分。"),
        ("Base URL 已配置", has_base, "未填写将无法调用 OpenAI 兼容接口。"),
        ("追问模型已配置", has_question_model, "请填写 question model（如 ep-xxx）。"),
        ("评分模型已配置", has_evaluation_model, "请填写 evaluation model（如 ep-xxx）。"),
        ("语音识别模型已配置", asr_cloud_ok, "云端 ASR 模式需要填写 whisper model。"),
        ("Supabase 配置可用", cloud_ok, "云端模式请在 .env 配置 SUPABASE_URL 与 SUPABASE_ANON_KEY。"),
        ("用户鉴权已通过", auth_ok, "云端模式下需先注册/登录，RLS 才能生效。"),
        ("面试资料已准备", has_resume_context, "建议上传简历并补充 JD/面经以提升提问质量。"),
        ("核心依赖已安装", deps_ready, "建议安装 streamlit-webrtc / streamlit-autorefresh / pypdf。"),
    ]


def fake_ai_generate_questions() -> List[str]:
    # 后续接入真实 AI 调用时，必须继续从 session_state 读取配置
    api_key = st.session_state.get("api_key", "").strip()
    base_url = st.session_state.get("base_url", "").strip()
    _ = (api_key, base_url)  # 占位，确保后续调用路径已绑定配置变量

    mode = st.session_state.get("interview_mode", "技术面")
    question_map = {
        "技术面": [
            "问题1：请你用 2 分钟介绍一个最能体现技术深度的项目，并说明核心架构。",
            "问题2：你如何解释 Python GIL 对并发性能的影响？在什么场景会选择多进程？",
            "问题3：如果线上接口 RT 突然升高 3 倍，你会如何定位并给出优化方案？",
            "问题4：请手写一个 LRU 缓存的核心思路，并分析时间复杂度。",
        ],
        "行为面 (BQ)": [
            "问题1：描述一次你与团队成员意见冲突的经历，你如何推进达成一致？",
            "问题2：遇到跨团队协作延期时，你如何沟通风险并推动结果？",
            "问题3：你做过最有影响力的决策是什么？结果如何衡量？",
            "问题4：当任务优先级频繁变化时，你如何管理预期并保持交付质量？",
        ],
        "压力面": [
            "问题1：你说你优化过性能，但为什么数据提升并不显著？是不是方案有问题？",
            "问题2：如果你的架构选择导致线上事故，你凭什么证明不是你判断失误？",
            "问题3：为什么我应该相信你在高压下能稳定交付？给我具体证据。",
            "问题4：如果现在让我指出你项目最大的短板，你认为是什么？为什么一直没解决？",
        ],
        "HR面": [
            "问题1：你未来 3 年的职业规划是什么？为什么选择这个方向？",
            "问题2：你如何看待加班文化和工作生活平衡？",
            "问题3：你离开上一份工作的核心原因是什么？",
            "问题4：你的薪资预期区间是多少？可以接受的边界是什么？",
        ],
    }
    return question_map.get(mode, question_map["技术面"])


def build_style_system_prompt(interview_mode: str, resume_text: str) -> str:
    resume_snippet = (resume_text or "").strip()
    if not resume_snippet:
        resume_snippet = "未提供可解析简历文本。你必须先提出1个澄清问题，再进入正式提问。"

    style_profiles = {
        "技术面": {
            "persona": "资深架构师",
            "tone": "言简意赅、逻辑严谨、对技术细节极度挑剔",
            "rules": [
                "优先追问底层原理、架构取舍、复杂度与工程可落地性。",
                "每次只问一个问题，必须包含明确的技术判断点。",
                "禁止空泛鼓励，不做长篇解释，不替候选人补全答案。",
                "如果候选人回答模糊，立即追问可量化指标与真实线上证据。",
            ],
            "phrases": ["请给出你当时的架构权衡。", "请量化这个优化收益。"],
        },
        "压力面": {
            "persona": "强势的高管",
            "tone": "高压、质疑、连续追问，测试心理素质",
            "rules": [
                "提问要带挑战性，允许明确否定与质疑，但不得人身攻击。",
                "高频使用“我不这么认为”“你的方案毫无亮点”这类压迫式表达。",
                "聚焦候选人的关键决策、风险承担与结果复盘。",
                "每轮必须有追问钩子，迫使候选人给出更硬证据。",
            ],
            "phrases": ["我不这么认为。", "你的方案毫无亮点。"],
        },
        "行为面 (BQ)": {
            "persona": "资深BP",
            "tone": "结构化引导、鼓励讲清故事脉络",
            "rules": [
                "引导候选人按 STAR（情境/任务/行动/结果）结构回答。",
                "重点挖掘沟通协作、冲突处理、影响力与复盘学习。",
                "每次提问必须要求一个真实案例，不接受抽象观点。",
                "追问必须落到候选人的具体动作与结果指标。",
            ],
            "phrases": ["请用一个真实案例说明。", "你当时具体做了什么动作？"],
        },
        "行为面": {
            "persona": "资深BP",
            "tone": "结构化引导、鼓励讲清故事脉络",
            "rules": [
                "引导候选人按 STAR（情境/任务/行动/结果）结构回答。",
                "重点挖掘沟通协作、冲突处理、影响力与复盘学习。",
                "每次提问必须要求一个真实案例，不接受抽象观点。",
                "追问必须落到候选人的具体动作与结果指标。",
            ],
            "phrases": ["请用一个真实案例说明。", "你当时具体做了什么动作？"],
        },
        "HR面": {
            "persona": "亲和力强的招聘官",
            "tone": "温和专业、重视价值观与长期匹配",
            "rules": [
                "重点考察稳定性、职业规划、文化匹配与动机真实性。",
                "语气保持亲和，不使用对抗式攻击表达。",
                "每个问题都要与候选人履历中的经历做关联。",
                "关注候选人与团队价值观是否一致，并提出可验证问题。",
            ],
            "phrases": ["你为什么在这个阶段做这个选择？", "这和你的长期规划如何一致？"],
        },
    }

    profile = style_profiles.get(interview_mode, style_profiles["技术面"])
    rule_lines = "\n".join(f"- {line}" for line in profile["rules"])
    phrase_lines = "\n".join(f"- {line}" for line in profile["phrases"])

    return f"""
你是{profile["persona"]}，正在进行{interview_mode}模拟面试。

【风格定义】
- 人设：{profile["persona"]}
- 语气：{profile["tone"]}
- 风格锚点短语（可自然使用）：
{phrase_lines}

【强约束规则（必须遵守）】
{rule_lines}
- 下一个问题必须与候选人简历中的具体经历绑定，点名项目/职责/技术/成果中的至少1项。
- 只输出“一个问题”，不要给答案、不要给点评、不要输出多段内容。
- 问题长度控制在1-3句话，避免模板化套话。
- 如果当前信息不足以绑定简历细节，先问1个澄清问题补齐关键背景。
- 如果你的输出不符合上述任一规则，请在内部重写后再输出最终问题。

【候选人简历内容】
{resume_snippet}
""".strip()


def build_next_question_messages(
    interview_mode: str,
    resume_text: str,
    conversation_history: List[str],
) -> List[dict]:
    system_prompt = build_style_system_prompt(interview_mode, resume_text)
    history_text = "\n".join(conversation_history[-8:]).strip() or "（暂无历史对话）"

    user_prompt = (
        "请基于上述规则，生成你的下一个面试问题。\n"
        "务必严格保持指定风格，并结合候选人简历细节。\n"
        f"历史对话如下：\n{history_text}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_chat_completions_url(base_url: str) -> str:
    return build_endpoint_url(base_url, "chat/completions")


def build_models_url(base_url: str) -> str:
    return build_endpoint_url(base_url, "models")


def build_endpoint_url(base_url: str, endpoint: str) -> str:
    clean_url = base_url.strip().rstrip("/")
    if not clean_url:
        raise ValueError("请先填写 Base URL。")

    normalized_endpoint = endpoint.strip().lstrip("/")
    if clean_url.endswith(f"/{normalized_endpoint}"):
        return clean_url

    parsed = urlparse(clean_url)
    path = parsed.path.rstrip("/")
    # 兼容 OpenAI v1 与火山方舟 /api/v3 等版本路径。
    if re.search(r"/(api/)?v\d+$", path):
        return f"{clean_url}/{normalized_endpoint}"

    # 若用户只填写域名，则默认走 OpenAI 兼容的 /v1。
    return f"{clean_url}/v1/{normalized_endpoint}"


def test_api_connection() -> str:
    api_key = st.session_state.get("api_key", "").strip()
    base_url = st.session_state.get("base_url", "").strip()
    if not api_key:
        return "连接失败：请先填写 API Key。"
    try:
        models_url = build_models_url(base_url)
    except ValueError as exc:
        return f"连接失败：{exc}"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = requests.get(models_url, headers=headers, timeout=25)
        response.raise_for_status()
        payload = response.json()
        model_count = len(payload.get("data", [])) if isinstance(payload, dict) else 0
        return f"连接成功：已获取模型列表（{model_count} 个）。"
    except RequestException as exc:
        # 某些网关不暴露 /models，这里回退到 chat/completions 健康检查。
        try:
            completion_url = build_chat_completions_url(base_url)
            probe_payload = {
                "model": st.session_state.get("question_model", "").strip(),
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
                "temperature": 0.0,
            }
            if not probe_payload["model"]:
                return f"连接失败：{exc}；且未配置可用于回退检测的 question model。"
            ping_resp = requests.post(
                completion_url,
                headers={**headers, "Content-Type": "application/json"},
                json=probe_payload,
                timeout=25,
            )
            ping_resp.raise_for_status()
            return "连接成功：/models 不可用，但 chat/completions 探活成功。"
        except RequestException as ping_exc:
            return f"连接失败：{exc}；chat 探活也失败：{ping_exc}"


def extract_resume_keywords(resume_text: str, max_keywords: int = 24) -> List[str]:
    text = (resume_text or "").strip()
    if not text:
        return []
    # 同时兼容中文词片段与英文技术名词（如 Python, Kafka, Redis）。
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_\-+.]{1,}", text)
    seen = set()
    keywords = []
    for token in tokens:
        normalized = token.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        keywords.append(token)
        if len(keywords) >= max_keywords:
            break
    return keywords


def validate_styled_question(
    question: str, interview_mode: str, resume_text: str
) -> Tuple[bool, str]:
    q = (question or "").strip()
    if not q:
        return False, "模型返回为空"
    if "\n" in q:
        return False, "返回了多段文本"

    sentence_chunks = [s for s in re.split(r"[。！？?!]", q) if s.strip()]
    if not 1 <= len(sentence_chunks) <= 3:
        return False, "问题句子数量超出 1-3 句限制"

    if "压力面" in interview_mode:
        pressure_markers = ["我不这么认为", "你的方案毫无亮点"]
        if not any(marker in q for marker in pressure_markers):
            return False, "压力面缺少高压质疑风格短语"

    if "HR面" in interview_mode:
        forbidden = ["你的方案毫无亮点"]
        if any(marker in q for marker in forbidden):
            return False, "HR面包含不合适的攻击性措辞"

    resume_keywords = extract_resume_keywords(resume_text)
    if resume_keywords:
        if not any(keyword in q for keyword in resume_keywords[:18]):
            return False, "问题未显式关联简历关键信息"

    return True, ""


def generate_next_question_with_style(
    interview_mode: str,
    resume_text: str,
    conversation_history: List[str],
    model: str = "",
    max_retries: int = 3,
) -> str:
    api_key = st.session_state.get("api_key", "").strip()
    base_url = st.session_state.get("base_url", "").strip()
    if not api_key:
        raise ValueError("请先在 API 配置区填写兼容 API Key（火山/OpenAI）。")
    completion_url = build_chat_completions_url(base_url)
    selected_model = model or st.session_state.get("question_model", "gpt-4o-mini")
    messages = build_next_question_messages(interview_mode, resume_text, conversation_history)
    request_chars = sum(len(msg.get("content", "")) for msg in messages)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    last_invalid_reason = ""
    current_messages = list(messages)
    for _ in range(max_retries):
        enforce_rate_limit_or_raise("chat_question")
        payload = {
            "model": selected_model,
            "messages": current_messages,
            "temperature": 0.35,
            "max_tokens": 220,
        }
        try:
            response = requests.post(completion_url, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
        except RequestException as exc:
            raise RuntimeError(f"问题生成调用失败：{exc}") from exc

        data = response.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        ok, reason = validate_styled_question(content, interview_mode, resume_text)
        if ok:
            record_usage("chat_question", request_chars, len(content))
            return content

        last_invalid_reason = reason
        current_messages.append({"role": "assistant", "content": content})
        current_messages.append(
            {
                "role": "user",
                "content": (
                    f"你刚才的输出不合格，原因：{reason}。"
                    "请严格遵守系统规则，重新只输出一个问题。"
                ),
            }
        )

    raise RuntimeError(f"多次重试后仍未满足风格约束：{last_invalid_reason}")


def maybe_generate_next_question() -> None:
    resume_context = get_resume_context_text()
    conversation_lines = [
        f"{'候选人' if item['role'] == 'user' else '面试官'}：{item['content']}"
        for item in st.session_state.interview_history
    ]
    question = generate_next_question_with_style(
        interview_mode=st.session_state.interview_mode,
        resume_text=resume_context,
        conversation_history=conversation_lines,
    )
    st.session_state.current_question = question
    st.session_state.question_error = ""
    append_dialogue("assistant", question)


def speak_question_once(question: str) -> None:
    text = (question or "").strip()
    if not text:
        return
    current_key = f"{len(st.session_state.interview_history)}::{text}"
    if st.session_state.last_spoken_question_key == current_key:
        return
    st.session_state.last_spoken_question_key = current_key
    text_json = json.dumps(text)
    components.html(
        f"""
        <script>
        const content = {text_json};
        if (window.speechSynthesis) {{
            window.speechSynthesis.cancel();
            const u = new SpeechSynthesisUtterance(content);
            u.lang = "zh-CN";
            u.rate = 1.0;
            window.speechSynthesis.speak(u);
        }}
        </script>
        """,
        height=0,
    )


def parse_json_object(raw_text: str) -> dict:
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("评分模型返回为空。")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        raise ValueError("评分模型返回内容不是有效 JSON。")


def build_qa_playback(history: List[dict]) -> List[dict]:
    qa_rows = []
    current_q = None
    q_index = 0
    for item in history:
        role = item.get("role", "")
        content = item.get("content", "")
        timestamp = item.get("timestamp", "")
        if role == "assistant":
            q_index += 1
            current_q = {
                "index": q_index,
                "question": content,
                "question_time": timestamp,
                "answer": "",
                "answer_time": "",
            }
            qa_rows.append(current_q)
        elif role == "user":
            if current_q and not current_q["answer"]:
                current_q["answer"] = content
                current_q["answer_time"] = timestamp
            else:
                q_index += 1
                qa_rows.append(
                    {
                        "index": q_index,
                        "question": "（系统未记录到对应问题）",
                        "question_time": "",
                        "answer": content,
                        "answer_time": timestamp,
                    }
                )
    return qa_rows


def build_report_markdown(report: dict) -> str:
    scores = report.get("scores", {})
    playback = report.get("qa_playback", [])
    transcript = report.get("raw_transcript", [])
    lines = [
        "# AI 面试官 - 面试复盘报告",
        "",
        f"- 面试模式：{report.get('interview_mode', '')}",
        f"- 开始时间：{report.get('started_at', '')}",
        f"- 结束时间：{report.get('ended_at', '')}",
        "",
        "## 总评",
        report.get("summary", "已完成评估。"),
        "",
        "## 多维评分",
        f"- 专业度：{int(scores.get('专业度', 0))}",
        f"- 逻辑性：{int(scores.get('逻辑性', 0))}",
        f"- 抗压能力：{int(scores.get('抗压能力', 0))}",
        f"- 沟通技巧：{int(scores.get('沟通技巧', 0))}",
        "",
        "## Q&A 回放记录（含时间戳）",
    ]
    for item in playback:
        lines.extend(
            [
                f"### 第 {item.get('index', 0)} 轮",
                f"- 提问时间：{item.get('question_time', '')}",
                f"- 提问：{item.get('question', '')}",
                f"- 回答时间：{item.get('answer_time', '')}",
                f"- 回答：{item.get('answer', '')}",
                "",
            ]
        )
    lines.extend(["## 语音转文字汇总", ""])
    for line in transcript:
        lines.append(f"- {line}")
    lines.extend(["", "## 改进建议高亮", ""])
    for item in report.get("highlights", []):
        lines.extend(
            [
                f"> 原话问题片段：{item.get('original', '')}",
                f"> 问题说明：{item.get('issue', '')}",
                f"建议口播文案：{item.get('improved', '')}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def build_report_pdf_bytes(report: dict) -> bytes:
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("当前环境未安装 reportlab，无法导出 PDF。")
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    font_name = "Helvetica"
    # 优先尝试注册 Windows 中文字体，保证中文可读。
    for font_path, alias in [
        ("C:/Windows/Fonts/msyh.ttc", "YaHei"),
        ("C:/Windows/Fonts/simhei.ttf", "SimHei"),
    ]:
        try:
            pdfmetrics.registerFont(TTFont(alias, font_path))
            font_name = alias
            break
        except Exception:
            continue

    pdf.setFont(font_name, 11)
    y = height - 42

    def write_line(text: str) -> None:
        nonlocal y
        if y <= 40:
            pdf.showPage()
            pdf.setFont(font_name, 11)
            y = height - 42
        pdf.drawString(36, y, (text or "")[:95])
        y -= 16

    markdown = build_report_markdown(report)
    for row in markdown.splitlines():
        write_line(row)
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def evaluate_interview_performance() -> dict:
    api_key = st.session_state.get("api_key", "").strip()
    base_url = st.session_state.get("base_url", "").strip()
    if not api_key:
        raise ValueError("请先在侧边栏填写 API Key，再结束面试。")

    history = st.session_state.interview_history
    user_lines = [item["content"] for item in history if item["role"] == "user"]
    if not user_lines:
        raise ValueError("当前没有可评分的候选人语音记录。")

    completion_url = build_chat_completions_url(base_url)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    transcript_text = "\n".join(f"- {line}" for line in user_lines)
    system_prompt = (
        "你是严谨的中文面试评估官。请只输出 JSON，不要输出任何额外说明。"
        "你需要基于候选人原话给出多维评分与改进建议。"
    )
    user_prompt = f"""
请根据以下候选人原话进行评估，面试模式：{st.session_state.interview_mode}。

候选人原话：
{transcript_text}

请严格输出 JSON，结构如下：
{{
  "summary": "一句话总结",
  "scores": {{
    "专业度": 0-100整数,
    "逻辑性": 0-100整数,
    "抗压能力": 0-100整数,
    "沟通技巧": 0-100整数
  }},
  "highlights": [
    {{
      "original": "候选人原话片段",
      "issue": "问题说明",
      "improved": "改进后的口播文案（第一人称）"
    }}
  ]
}}
要求：
1) highlights 至少返回 2 条。
2) original 必须来自候选人原话，不要虚构。
3) improved 要可直接口播，简洁有力。
""".strip()
    payload = {
        "model": st.session_state.get("evaluation_model", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.25,
        "max_tokens": 900,
    }
    enforce_rate_limit_or_raise("chat_evaluation")
    request_chars = len(system_prompt) + len(user_prompt)
    try:
        response = requests.post(completion_url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
    except RequestException as exc:
        raise RuntimeError(f"面试评估调用失败：{exc}") from exc

    content = (
        response.json()
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    result = parse_json_object(content)
    record_usage("chat_evaluation", request_chars, len(content))
    result["raw_transcript"] = user_lines
    result["qa_playback"] = build_qa_playback(history)
    result["started_at"] = st.session_state.get("interview_started_at", "")
    result["ended_at"] = st.session_state.get("interview_ended_at", "") or now_ts()
    result["interview_mode"] = st.session_state.get("interview_mode", "")
    result["audio_objects"] = st.session_state.get("audio_objects", [])
    return result


def end_interview_and_generate_report() -> None:
    st.session_state.interview_ended_at = now_ts()
    report = evaluate_interview_performance()
    uid = current_user_id()
    save_report(APP_SETTINGS.sqlite_path, report, user_id=uid)
    if is_cloud_enabled() and st.session_state.get("auth_access_token") and uid != "local":
        try:
            save_cloud_report(
                APP_SETTINGS.supabase_url,
                APP_SETTINGS.supabase_anon_key,
                st.session_state.auth_access_token,
                uid,
                report,
            )
        except Exception as exc:
            st.session_state.report_error = f"云端报告同步失败：{exc}"
    st.session_state.interview_report = report
    st.session_state.in_interview_room = False
    reset_interview_runtime_state(keep_report=True)


def render_interview_report() -> None:
    report = st.session_state.interview_report
    if not report:
        return

    scores = report.get("scores", {})
    st.markdown("### 本场面试复盘报告")
    st.markdown(f"> {report.get('summary', '已完成评估。')}")
    score_cols = st.columns(4)
    metric_names = ["专业度", "逻辑性", "抗压能力", "沟通技巧"]
    for idx, name in enumerate(metric_names):
        with score_cols[idx]:
            st.metric(name, int(scores.get(name, 0)))

    st.markdown("#### 语音转文字汇总")
    for line in report.get("raw_transcript", []):
        st.markdown(f"- {line}")

    st.markdown("#### Q&A 回放记录（含时间戳）")
    playback = report.get("qa_playback", [])
    if not playback:
        st.caption("暂无回放记录。")
    else:
        for item in playback:
            st.markdown(f"**第 {item.get('index', 0)} 轮**")
            st.markdown(
                f"- [{ts_short(item.get('question_time', ''))}] 面试官：{item.get('question', '')}"
            )
            st.markdown(
                f"- [{ts_short(item.get('answer_time', ''))}] 候选人：{item.get('answer', '')}"
            )

    st.markdown("#### 改进建议高亮")
    highlights = report.get("highlights", [])
    if not highlights:
        st.caption("暂无高亮建议。")
    for item in highlights:
        original = item.get("original", "").strip()
        issue = item.get("issue", "").strip()
        improved = item.get("improved", "").strip()
        st.markdown(
            f"> <span style='color:#ff7070'>原话问题片段：</span> {original}",
            unsafe_allow_html=True,
        )
        st.markdown(f"> 问题说明：{issue}")
        st.markdown(f"**建议口播文案：** {improved}")
        st.markdown("---")

    markdown_report = build_report_markdown(report)
    st.download_button(
        "导出评分报告（Markdown）",
        data=markdown_report.encode("utf-8"),
        file_name="interview_report.md",
        mime="text/markdown",
        use_container_width=True,
    )
    if REPORTLAB_AVAILABLE:
        try:
            pdf_bytes = build_report_pdf_bytes(report)
            st.download_button(
                "导出评分报告（PDF）",
                data=pdf_bytes,
                file_name="interview_report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except RuntimeError as exc:
            st.caption(str(exc))
    else:
        st.caption("未安装 reportlab，暂不可导出 PDF。")


def render_history_reports() -> None:
    st.markdown("### 历史面试记录")
    uid = current_user_id()
    if is_cloud_enabled() and st.session_state.get("auth_access_token") and uid != "local":
        records = list_cloud_reports(
            APP_SETTINGS.supabase_url,
            APP_SETTINGS.supabase_anon_key,
            st.session_state.auth_access_token,
            uid,
            limit=50,
        )
    else:
        records = list_reports(APP_SETTINGS.sqlite_path, user_id=uid, limit=50)
    if not records:
        st.caption("暂无历史记录。完成一次面试并生成报告后会出现在这里。")
        return

    options = {f"#{item['id']} | {item['created_at']} | {item['interview_mode']}": item["id"] for item in records}
    labels = list(options.keys())
    default_index = 0
    if st.session_state.history_selected_id:
        target = st.session_state.history_selected_id
        for idx, label in enumerate(labels):
            if options[label] == target:
                default_index = idx
                break

    selected_label = st.selectbox("选择历史报告", labels, index=default_index)
    selected_id = options[selected_label]
    st.session_state.history_selected_id = selected_id
    if is_cloud_enabled() and st.session_state.get("auth_access_token") and uid != "local":
        report = get_cloud_report(
            APP_SETTINGS.supabase_url,
            APP_SETTINGS.supabase_anon_key,
            st.session_state.auth_access_token,
            uid,
            str(selected_id),
        )
    else:
        report = get_report(APP_SETTINGS.sqlite_path, int(selected_id), user_id=uid)
    if not report:
        st.warning("该历史报告不存在或已删除。")
        return

    st.markdown(f"> 摘要：{report.get('summary', '')}")
    cols = st.columns(4)
    for idx, key in enumerate(["专业度", "逻辑性", "抗压能力", "沟通技巧"]):
        with cols[idx]:
            st.metric(key, int(report.get("scores", {}).get(key, 0)))
    st.markdown(
        f"- 面试模式：`{report.get('interview_mode', '')}`  \n"
        f"- 开始：`{report.get('started_at', '')}`  \n"
        f"- 结束：`{report.get('ended_at', '')}`"
    )

    with st.expander("查看完整 Q&A 回放", expanded=False):
        for item in report.get("qa_playback", []):
            st.markdown(f"**第 {item.get('index', 0)} 轮**")
            st.markdown(
                f"- [{ts_short(item.get('question_time', ''))}] 面试官：{item.get('question', '')}"
            )
            st.markdown(
                f"- [{ts_short(item.get('answer_time', ''))}] 候选人：{item.get('answer', '')}"
            )

    md = build_report_markdown(report)
    st.download_button(
        "导出该历史报告（Markdown）",
        data=md.encode("utf-8"),
        file_name=f"interview_report_{selected_id}.md",
        mime="text/markdown",
        use_container_width=True,
    )
    if REPORTLAB_AVAILABLE:
        try:
            pdf_data = build_report_pdf_bytes(report)
            st.download_button(
                "导出该历史报告（PDF）",
                data=pdf_data,
                file_name=f"interview_report_{selected_id}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except RuntimeError:
            st.caption("PDF 导出失败，请检查 reportlab 安装或字体环境。")


def build_transcription_url(base_url: str) -> str:
    return build_endpoint_url(base_url, "audio/transcriptions")


@st.cache_resource
def load_whisper_model(model_size: str = "base"):
    """
    加载本地 Whisper 模型，使用 st.cache_resource 确保全局只加载一次。
    model_size 可选: tiny, base, small, medium, large-v3
    base 模型约 145 MB，CPU 推理速度适中，中文识别效果良好。
    """
    return WhisperModel(model_size, device="cpu", compute_type="int8")


def transcribe_with_cloud_whisper(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    api_key = st.session_state.get("api_key", "").strip()
    base_url = st.session_state.get("base_url", "").strip()
    if not api_key:
        raise ValueError("云端转写模式下，请先填写 API Key。")

    transcription_url = build_transcription_url(base_url)
    files = {
        "file": ("interview_audio.wav", audio_bytes, mime_type),
    }
    data = {
        "model": st.session_state.get("whisper_model", "whisper-1"),
        "response_format": "json",
        "language": "zh",
    }
    enforce_rate_limit_or_raise("whisper_cloud")
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        response = requests.post(
            transcription_url,
            headers=headers,
            data=data,
            files=files,
            timeout=90,
        )
        response.raise_for_status()
    except RequestException as exc:
        raise RuntimeError(f"云端语音转写调用失败：{exc}") from exc

    payload = response.json()
    text = payload.get("text", "").strip()
    if not text:
        raise RuntimeError("云端转写结果为空，请重试。")
    record_usage("whisper_cloud", len(audio_bytes), len(text))
    return text


def transcribe_with_whisper_bytes(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    if st.session_state.get("asr_mode") == "云端兼容 Whisper API":
        return transcribe_with_cloud_whisper(audio_bytes, mime_type=mime_type)

    # 获取或加载本地 Whisper 模型
    model_size = st.session_state.get("local_whisper_size", "base")
    model = load_whisper_model(model_size=model_size)

    # 将音频字节流写入临时文件（faster-whisper 需要文件路径）
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        # 执行转写，指定语言为中文
        segments, info = model.transcribe(tmp_path, language="zh", beam_size=5)
        # 合并所有片段文本
        full_text = "".join(segment.text for segment in segments).strip()

        if not full_text:
            raise RuntimeError("本地转写结果为空，请重新录音。")

        # 记录用量（本地模型成本为 0，但保留调用记录以便监控）
        record_usage("whisper_local", len(audio_bytes), len(full_text))
        return full_text
    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def normalize_mono_pcm_int16(frame) -> tuple[np.ndarray, float, int]:
    raw = frame.to_ndarray()
    sample_rate = getattr(frame, "sample_rate", 16000) or 16000

    if raw.ndim == 2:
        if raw.shape[0] <= 2:
            mono = raw.mean(axis=0)
        else:
            mono = raw.mean(axis=1)
    else:
        mono = raw

    mono_float = mono.astype(np.float32)
    if np.max(np.abs(mono_float)) > 1.5:
        mono_norm = mono_float / 32768.0
    else:
        mono_norm = mono_float

    rms = float(np.sqrt(np.mean(np.square(mono_norm)) + 1e-12))
    mono_int16 = np.clip(mono_norm, -1.0, 1.0)
    mono_int16 = (mono_int16 * 32767.0).astype(np.int16)
    return mono_int16, rms, int(sample_rate)


def pcm_to_wav_bytes(pcm_int16: np.ndarray, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_int16.tobytes())
    return buffer.getvalue()


def reset_vad_state() -> None:
    st.session_state.vad_chunks = []
    st.session_state.vad_is_recording = False
    st.session_state.vad_silence_ms = 0


def handle_vad_frame(frame) -> None:
    energy_threshold = 0.018
    silence_cut_ms = 1200
    min_speech_ms = 850
    max_speech_ms = 20000

    mono_int16, rms, sample_rate = normalize_mono_pcm_int16(frame)
    frame_ms = max(int((len(mono_int16) / sample_rate) * 1000), 10)
    st.session_state.vad_sample_rate = sample_rate

    if rms >= energy_threshold:
        if not st.session_state.vad_is_recording:
            st.session_state.vad_is_recording = True
            st.session_state.vad_chunks = []
            st.session_state.vad_silence_ms = 0
        st.session_state.vad_chunks.append(mono_int16)
        st.session_state.vad_silence_ms = 0
        return

    if not st.session_state.vad_is_recording:
        return

    st.session_state.vad_chunks.append(mono_int16)
    st.session_state.vad_silence_ms += frame_ms

    total_ms = int(
        sum(chunk.shape[0] for chunk in st.session_state.vad_chunks)
        / st.session_state.vad_sample_rate
        * 1000
    )
    if st.session_state.vad_silence_ms >= silence_cut_ms and total_ms < min_speech_ms:
        # 过滤短噪音片段，避免误触发 Whisper 调用。
        reset_vad_state()
        st.session_state.transcribe_error = ""
        return

    if total_ms >= max_speech_ms or (
        st.session_state.vad_silence_ms >= silence_cut_ms and total_ms >= min_speech_ms
    ):
        utterance = np.concatenate(st.session_state.vad_chunks)
        reset_vad_state()

        wav_bytes = pcm_to_wav_bytes(utterance, sample_rate)
        if is_cloud_enabled() and st.session_state.get("auth_access_token") and current_user_id() != "local":
            try:
                encrypted = encrypt_bytes(wav_bytes, APP_SETTINGS.encryption_key)
                object_path = upload_audio_blob(
                    APP_SETTINGS.supabase_url,
                    APP_SETTINGS.supabase_anon_key,
                    st.session_state.auth_access_token,
                    APP_SETTINGS.supabase_bucket,
                    current_user_id(),
                    encrypted,
                    f"{int(time.time() * 1000)}.enc",
                )
                if object_path:
                    st.session_state.audio_objects.append(object_path)
            except Exception:
                # 上传失败不阻断面试主流程。
                pass
        try:
            transcript = transcribe_with_whisper_bytes(wav_bytes)
            st.session_state.last_transcript = transcript
            append_dialogue("user", transcript)
            try:
                maybe_generate_next_question()
            except (ValueError, RuntimeError) as exc:
                st.session_state.question_error = str(exc)
            st.session_state.transcribe_error = ""
        except (ValueError, RuntimeError) as exc:
            st.session_state.transcribe_error = str(exc)


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### 账户与权限")
        st.session_state.use_cloud_storage = st.toggle(
            "启用 Supabase 云端模式",
            value=st.session_state.use_cloud_storage,
            help="启用后将使用 Supabase Auth + 云端表与对象存储；关闭则仅本地模式。",
        )
        cloud_ready = is_cloud_enabled()
        if st.session_state.use_cloud_storage and not cloud_ready:
            dep_hint = "supabase 依赖未安装。" if not SUPABASE_AVAILABLE else "请检查 SUPABASE_URL / SUPABASE_ANON_KEY。"
            st.warning(f"Supabase 未就绪（{dep_hint}）当前使用本地模式。")

        if cloud_ready:
            st.session_state.auth_email = st.text_input(
                "登录邮箱", value=st.session_state.auth_email, placeholder="name@example.com"
            )
            st.session_state.auth_password = st.text_input(
                "登录密码", type="password", value=st.session_state.auth_password
            )
            auth_col1, auth_col2 = st.columns(2)
            with auth_col1:
                if st.button("注册", use_container_width=True):
                    try:
                        result = sign_up_with_password(
                            APP_SETTINGS.supabase_url,
                            APP_SETTINGS.supabase_anon_key,
                            st.session_state.auth_email.strip(),
                            st.session_state.auth_password,
                        )
                        st.session_state.auth_user_id = result["user_id"]
                        st.session_state.auth_access_token = result.get("access_token", "")
                        st.session_state.auth_refresh_token = result.get("refresh_token", "")
                        st.session_state.auth_logged_in = bool(st.session_state.auth_access_token)
                        st.session_state.auth_status = (
                            "注册成功。若未自动登录，请点击“登录”。"
                        )
                    except Exception as exc:
                        st.session_state.auth_status = f"注册失败：{exc}"
            with auth_col2:
                if st.button("登录", use_container_width=True):
                    try:
                        result = sign_in_with_password(
                            APP_SETTINGS.supabase_url,
                            APP_SETTINGS.supabase_anon_key,
                            st.session_state.auth_email.strip(),
                            st.session_state.auth_password,
                        )
                        st.session_state.auth_user_id = result["user_id"]
                        st.session_state.auth_access_token = result["access_token"]
                        st.session_state.auth_refresh_token = result["refresh_token"]
                        st.session_state.auth_logged_in = True
                        st.session_state.auth_status = f"已登录：{result.get('email', '')}"
                        st.session_state.retention_checked = False
                    except Exception as exc:
                        st.session_state.auth_status = f"登录失败：{exc}"
            if st.session_state.auth_logged_in:
                st.success(f"当前用户：{st.session_state.auth_user_id[:8]}...")
                if st.button("退出登录", use_container_width=True):
                    st.session_state.auth_logged_in = False
                    st.session_state.auth_access_token = ""
                    st.session_state.auth_refresh_token = ""
                    st.session_state.auth_user_id = "local"
                    st.session_state.auth_status = "已退出登录。"
            if st.session_state.auth_status:
                st.caption(st.session_state.auth_status)
        else:
            st.caption("当前为本地模式（单用户）。")

        st.divider()
        st.markdown("### API 配置区")
        st.session_state.api_key = st.text_input(
            "兼容格式 API Key（火山/OpenAI）",
            type="password",
            value=st.session_state.api_key,
            placeholder="请填写服务商 API Key",
            help="用于聊天模型调用；若选择云端语音转写模式，也会用于音频转写接口。",
        )
        st.session_state.base_url = st.text_input(
            "Base URL",
            value=st.session_state.base_url,
            placeholder="例如：https://ark.cn-beijing.volces.com/api/v3",
            help="支持 OpenAI 兼容地址；可填写 /v1 或 /api/v3 前缀。",
        )
        if st.button("从 .env 重新加载默认配置", use_container_width=True):
            reload_defaults_from_env()
            st.rerun()
        if st.button("测试 API 连通性", use_container_width=True):
            st.session_state.api_test_status = test_api_connection()
        if st.session_state.api_test_status:
            st.caption(st.session_state.api_test_status)

        st.markdown("#### 模型配置")
        st.session_state.question_model = st.text_input(
            "追问模型 (Chat)",
            value=st.session_state.question_model,
            placeholder="例如：ep-xxx 或 gpt-4o-mini",
            help="用于生成下一题。",
        )
        st.session_state.evaluation_model = st.text_input(
            "评分模型 (Chat)",
            value=st.session_state.evaluation_model,
            placeholder="例如：ep-xxx 或 gpt-4o-mini",
            help="用于面试结束后的评分与建议。",
        )
        st.session_state.asr_mode = st.radio(
            "语音转写模式",
            ["本地 faster-whisper", "云端兼容 Whisper API"],
            index=0 if st.session_state.asr_mode == "本地 faster-whisper" else 1,
            help="本地模式不消耗云端 ASR 费用；云端模式支持火山/OpenAI 兼容转写接口。",
        )
        if st.session_state.asr_mode == "本地 faster-whisper":
            st.session_state.local_whisper_size = st.selectbox(
                "本地 Whisper 模型大小",
                ["tiny", "base", "small", "medium", "large-v3"],
                index=["tiny", "base", "small", "medium", "large-v3"].index(
                    st.session_state.local_whisper_size
                    if st.session_state.local_whisper_size in {"tiny", "base", "small", "medium", "large-v3"}
                    else "base"
                ),
                help="模型越大准确率通常越高，但推理更慢；建议先用 base。",
            )
        else:
            st.session_state.whisper_model = st.text_input(
                "云端语音转写模型 (Whisper)",
                value=st.session_state.whisper_model,
                placeholder="例如：ep-xxx 或 whisper-1",
                help="云端模式下用于 /audio/transcriptions 的模型 ID。",
            )
        st.divider()
        st.markdown("### 隐私与合规")
        st.caption(st.session_state.privacy_notice or get_privacy_notice(APP_SETTINGS.retention_days, can_encrypt(APP_SETTINGS.encryption_key)))
        st.caption(
            f"录音加密密钥状态：{'已配置' if can_encrypt(APP_SETTINGS.encryption_key) else '未配置（将明文存储）'}"
        )
        if st.button("删除我的全部历史数据", use_container_width=True):
            clear_all_user_data()
        st.divider()
        st.markdown("### 限流与成本监控")
        summary = get_cost_summary(APP_SETTINGS.sqlite_path, current_user_id(), hours=24)
        st.caption(
            f"24小时请求数：{int(summary['request_count'])} | 估算成本：${summary['estimated_cost_usd']:.4f}"
        )
        st.caption(
            f"1分钟限流阈值：{APP_SETTINGS.max_api_requests_per_minute} 次"
        )

        st.divider()
        st.markdown("### 面试模式选择")
        options = ["技术面", "行为面 (BQ)", "压力面", "HR面"]
        st.session_state.interview_mode = st.selectbox(
            "选择你要模拟的面试类型",
            options=options,
            index=options.index(st.session_state.interview_mode),
        )

        st.caption(
            "技术面：底层原理/代码/架构\n\n"
            "行为面：沟通协作/领导力准则\n\n"
            "压力面：高压追问/细节质疑\n\n"
            "HR面：稳定性/规划/文化与薪资"
        )

        st.divider()
        st.markdown("### 面试状态管理")
        if st.button("进入面试间", use_container_width=True):
            if st.session_state.use_cloud_storage and not st.session_state.auth_logged_in:
                st.session_state.auth_status = "请先登录后再进入面试间（云端模式）。"
                st.rerun()
            reset_interview_runtime_state(keep_report=True)
            st.session_state.interview_started_at = now_ts()
            st.session_state.in_interview_room = True
            st.rerun()

        if st.session_state.in_interview_room and st.button(
            "退出面试间", use_container_width=True
        ):
            st.session_state.in_interview_room = False
            st.rerun()


def render_setup_page() -> None:
    st.markdown('<div class="main-title">AI 面试官</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">上传材料并生成个性化模拟问题，进入沉浸式面试练习。</div>',
        unsafe_allow_html=True,
    )
    if st.session_state.report_error:
        st.error(st.session_state.report_error)
    render_interview_report()
    render_history_reports()
    st.markdown("### 上线自检")
    for name, ok, tip in get_launch_readiness_items():
        status = "✅" if ok else "⚠️"
        st.markdown(f"- {status} {name}：{tip}")

    left, right = st.columns([1.2, 1], gap="large")

    with left:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">输入材料</div>', unsafe_allow_html=True)
        st.session_state.resume_file = st.file_uploader(
            "个人简历 (PDF)",
            type=["pdf"],
            accept_multiple_files=False,
        )
        if st.session_state.resume_file:
            resume_bytes = st.session_state.resume_file.getvalue()
            current_digest = hashlib.sha1(resume_bytes).hexdigest()
            if st.session_state.resume_file_digest != current_digest:
                st.session_state.resume_file_digest = current_digest
                st.session_state.resume_text_cache = extract_resume_text(st.session_state.resume_file)
        elif st.session_state.resume_file_digest:
            st.session_state.resume_file_digest = ""
            st.session_state.resume_text_cache = ""

        if st.session_state.resume_text_cache:
            st.caption("已解析简历文本，可用于自动追问。")
        elif st.session_state.resume_file and not PDF_READER_AVAILABLE:
            st.caption("当前未安装 pypdf，简历 PDF 文本无法自动解析。")

        st.session_state.jd_text = st.text_area(
            "目标岗位 JD (文本框)",
            value=st.session_state.jd_text,
            placeholder="请粘贴岗位职责、任职要求、技术栈关键字等内容...",
            height=180,
        )

        uploaded_txt = st.file_uploader(
            "过往面经参考 (TXT，可选)",
            type=["txt"],
            accept_multiple_files=False,
        )
        if uploaded_txt:
            st.session_state.experience_text = read_txt_upload(uploaded_txt)

        st.session_state.experience_text = st.text_area(
            "过往面经参考 (文本框/TXT)",
            value=st.session_state.experience_text,
            placeholder="可粘贴你搜集到的面经题目、面试流程与追问细节...",
            height=220,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">题库生成</div>', unsafe_allow_html=True)
        st.write(f"当前面试模式：`{st.session_state.interview_mode}`")
        generate_clicked = st.button("生成面试题库", use_container_width=True, type="primary")

        if generate_clicked:
            with st.spinner("正在构建模拟面试题库，请稍候..."):
                time.sleep(1.8)
                st.session_state.question_bank = fake_ai_generate_questions()

        if st.session_state.question_bank:
            st.markdown("#### 预览题库（测试假数据）")
            for q in st.session_state.question_bank:
                st.markdown(f'<div class="result-block">{q}</div>', unsafe_allow_html=True)
        else:
            st.info("点击“生成面试题库”后将在这里展示测试问题。")

        st.markdown("</div>", unsafe_allow_html=True)


def render_interview_room() -> None:
    placeholder = st.empty()
    with placeholder.container():
        st.markdown(
            """
            <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            [data-testid="stSidebar"] {display: none;}
            [data-testid="collapsedControl"] {display: none;}
            [data-testid="stAppViewContainer"] {
                background: #000 !important;
            }
            .block-container {
                max-width: 100%;
                padding-top: 1.25rem;
                padding-bottom: 1rem;
                padding-left: 1.8rem;
                padding-right: 1.8rem;
            }

            .immersive-wrap {
                min-height: 90vh;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            }

            .room-grid {
                display: grid;
                grid-template-columns: 1.45fr 0.7fr;
                gap: 1rem;
                align-items: start;
            }

            .camera-panel {
                border: 1px solid rgba(255,255,255,0.16);
                border-radius: 16px;
                background: #040405;
                padding: 0.8rem;
                min-height: 56vh;
                box-shadow: 0 10px 28px rgba(0,0,0,0.45);
            }

            .panel-headline {
                color: #ececf0;
                font-size: 0.95rem;
                margin-bottom: 0.5rem;
            }

            .interviewer-card {
                border: 1px solid rgba(255,255,255,0.16);
                border-radius: 16px;
                background: #0b0b0c;
                padding: 1rem;
                box-shadow: 0 8px 24px rgba(0,0,0,0.4);
            }

            .avatar {
                width: 84px;
                height: 84px;
                border-radius: 50%;
                background: radial-gradient(circle at 30% 30%, #f4f4f5 0%, #94949b 38%, #2f2f35 100%);
                margin: 0 auto 0.7rem auto;
            }

            .interviewer-name {
                text-align: center;
                font-size: 0.95rem;
                font-weight: 600;
                margin-bottom: 0.5rem;
            }

            .wave {
                height: 34px;
                display: flex;
                justify-content: center;
                align-items: end;
                gap: 4px;
                margin-top: 0.4rem;
            }

            .wave span {
                width: 5px;
                border-radius: 999px;
                background: #d0d0d4;
                animation: wave 1.2s ease-in-out infinite;
            }

            .wave span:nth-child(1) {height: 7px; animation-delay: 0s;}
            .wave span:nth-child(2) {height: 16px; animation-delay: .1s;}
            .wave span:nth-child(3) {height: 24px; animation-delay: .2s;}
            .wave span:nth-child(4) {height: 12px; animation-delay: .3s;}
            .wave span:nth-child(5) {height: 18px; animation-delay: .4s;}

            @keyframes wave {
                0%,100% {opacity: .45; transform: scaleY(.75);}
                50% {opacity: 1; transform: scaleY(1.15);}
            }

            .subtitle-board {
                border: 1px solid rgba(255,255,255,0.16);
                border-radius: 16px;
                background: #070708;
                margin-top: 0.9rem;
                padding: 0.9rem 1rem;
                min-height: 20vh;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        top_left, top_right = st.columns([1.2, 1])
        with top_left:
            st.markdown(
                f"### 面试进行中 · `{st.session_state.interview_mode}`",
            )
            st.caption("沉浸式黑色界面已启用，建议佩戴耳机并保持环境安静。")
        with top_right:
            if st.button("结束面试并生成报告", use_container_width=True, type="primary"):
                try:
                    end_interview_and_generate_report()
                    st.rerun()
                except (ValueError, RuntimeError) as exc:
                    st.session_state.report_error = str(exc)
            if st.button("清空当前字幕", use_container_width=True):
                st.session_state.subtitle_lines = []
                st.session_state.interview_history = []
                st.session_state.current_question = ""
                st.session_state.question_error = ""
                st.session_state.last_spoken_question_key = ""
                st.session_state.interview_bootstrapped = False
                reset_vad_state()
                st.rerun()
            if st.button("返回设置页", use_container_width=True):
                st.session_state.in_interview_room = False
                st.session_state.auto_listen_enabled = False
                reset_vad_state()
                st.rerun()

        if not st.session_state.interview_bootstrapped:
            st.session_state.interview_bootstrapped = True
            try:
                maybe_generate_next_question()
            except (ValueError, RuntimeError) as exc:
                st.session_state.question_error = str(exc)

        main_left, main_right = st.columns([1.55, 0.75], gap="large")
        with main_left:
            st.markdown('<div class="camera-panel">', unsafe_allow_html=True)
            st.markdown(
                '<div class="panel-headline">你的摄像头画面（低延迟模式）</div>',
                unsafe_allow_html=True,
            )
            if WEBRTC_AVAILABLE:
                webrtc_ctx = webrtc_streamer(
                    key="interview-room-camera",
                    mode=WebRtcMode.SENDRECV,
                    media_stream_constraints={
                        "video": {
                            "width": {"ideal": 640},
                            "height": {"ideal": 360},
                            "frameRate": {"ideal": 15, "max": 24},
                        },
                        "audio": {
                            "echoCancellation": True,
                            "noiseSuppression": True,
                            "autoGainControl": True,
                        },
                    },
                    async_processing=True,
                    desired_playing_state=True,
                    video_html_attrs={
                        "autoPlay": True,
                        "controls": False,
                        "muted": True,
                        "style": {"width": "100%", "borderRadius": "12px"},
                    },
                )
                if not webrtc_ctx.state.playing:
                    st.caption("请允许浏览器摄像头/麦克风权限后开始视频预览。")
            else:
                st.warning("未安装 streamlit-webrtc，当前降级为拍照模式。")
                webrtc_ctx = None
                st.camera_input("摄像头预览（降级模式）")
            st.markdown("</div>", unsafe_allow_html=True)

        with main_right:
            st.markdown(
                """
                <div class="interviewer-card">
                    <div class="avatar"></div>
                    <div class="interviewer-name">AI 面试官</div>
                    <div style="text-align:center;color:#c9c9cf;font-size:0.85rem;">
                        正在聆听候选人回答
                    </div>
                    <div class="wave">
                        <span></span><span></span><span></span><span></span><span></span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("")
            st.markdown("#### 语音输入")
            st.session_state.auto_listen_enabled = st.toggle(
                "开始说话（VAD 自动监听）",
                value=st.session_state.auto_listen_enabled,
            )
            st.caption("开启后会持续监听，检测静音自动截断并提交 Whisper 转写。")
            if st.session_state.auto_listen_enabled and not AUTOREFRESH_AVAILABLE:
                st.warning("未安装 streamlit-autorefresh，将使用基础轮询模式。")
            if st.session_state.transcribe_error:
                st.error(st.session_state.transcribe_error)
            if st.session_state.question_error:
                st.error(st.session_state.question_error)
            if st.session_state.current_question:
                st.markdown("#### 下一题")
                st.markdown(f"> {st.session_state.current_question}")
                speak_question_once(st.session_state.current_question)
            if st.session_state.vad_is_recording:
                st.success("正在收音中，停顿约 1 秒后会自动提交。")
            elif st.session_state.auto_listen_enabled:
                st.info("监听中，等待你开始说话...")
            else:
                st.caption("关闭监听后不会自动转写。")

        if (
            WEBRTC_AVAILABLE
            and webrtc_ctx
            and webrtc_ctx.state.playing
            and st.session_state.auto_listen_enabled
            and webrtc_ctx.audio_receiver
        ):
            # 小批次轮询减少阻塞，兼顾实时性和流畅度。
            if AUTOREFRESH_AVAILABLE:
                st_autorefresh(interval=700, key="vad-polling-refresh")
            for _ in range(2):
                try:
                    frames = webrtc_ctx.audio_receiver.get_frames(timeout=0.12)
                except queue.Empty:
                    frames = []
                for frame in frames:
                    handle_vad_frame(frame)
            if not AUTOREFRESH_AVAILABLE:
                time.sleep(0.2)
                st.rerun()
        elif not st.session_state.auto_listen_enabled:
            reset_vad_state()

        st.markdown('<div class="subtitle-board">', unsafe_allow_html=True)
        st.markdown("#### 字幕区")
        if st.session_state.transcribe_error:
            st.caption("转写异常后，可重新录音提交。")
        if st.session_state.subtitle_lines:
            for line in st.session_state.subtitle_lines[-8:]:
                st.markdown(f"- {line}")
        else:
            st.caption("你的语音转文字内容会实时累积在这里。")
        st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    init_state()
    ensure_retention_policy_once()
    inject_base_style()
    if st.session_state.in_interview_room:
        render_interview_room()
    else:
        render_sidebar()
        render_setup_page()


if __name__ == "__main__":
    main()
