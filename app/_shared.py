"""Streamlit 多页共享工具：sidebar、查询封装、联通品牌 UI 组件。"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ---------------------------------------------------------------------------
# 品牌设计 token（中国联通视觉规范取色）
# ---------------------------------------------------------------------------
BRAND_RED = "#E60012"
BRAND_RED_DARK = "#B8000E"
BRAND_RED_DEEP = "#8C0010"
BRAND_RED_SOFT = "#FFEDEF"
BRAND_RED_FADE = "rgba(230, 0, 18, 0.06)"
BRAND_INK = "#1A1A1A"
BRAND_INK_SOFT = "#5C5C66"
BRAND_GREY = "#F7F7F8"
BRAND_LINE = "#E5E5EA"

# 联通"中国结"标志 SVG（简化版，单色，去 logo 文字）
UNICOM_KNOT_SVG = """
<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <g fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="22" cy="22" r="10"/>
    <circle cx="42" cy="22" r="10"/>
    <circle cx="22" cy="42" r="10"/>
    <circle cx="42" cy="42" r="10"/>
    <path d="M16 16 L48 48 M48 16 L16 48"/>
  </g>
</svg>
"""


# ---------------------------------------------------------------------------
# 全局 CSS 注入
# ---------------------------------------------------------------------------
# 关键设计点：
#   1. 主背景：多层 radial-gradient 光晕 + 极淡 SVG 网格底纹，营造空间感
#   2. 固定装饰：左上 / 右下两处大圆光晕（fixed 定位，滚动不动）
#   3. 玻璃态卡片：白色半透 + backdrop-filter 模糊，hover 上抬
#   4. Hero：双层渐变（径向高光 + 对角线性渐变）+ 圆点纹理 + 内发光
#   5. 中文字体优先 PingFang SC / Microsoft YaHei

# 极淡 SVG 网格，作为底纹（base64 内嵌避免额外请求）
_GRID_SVG = (
    "data:image/svg+xml;utf8,"
    "%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2240%22%20height%3D%2240%22%3E"
    "%3Cpath%20d%3D%22M0%2040L0%200L40%200%22%20fill%3D%22none%22%20stroke%3D%22%23E60012%22%20"
    "stroke-opacity%3D%220.045%22%20stroke-width%3D%221%22%2F%3E%3C%2Fsvg%3E"
)

_GLOBAL_CSS = f"""
<style>
  /* ====== 顶部去掉 Streamlit 默认装饰 ====== */
  #MainMenu {{ visibility: hidden; }}
  header[data-testid="stHeader"] {{
    background: transparent;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
  }}

  /* ====== 全局字体 ====== */
  html, body, [class*="css"] {{
    font-family: "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }}

  /* ====== 主背景：多层渐变 + 网格底纹 ====== */
  .stApp, div[data-testid="stAppViewContainer"] {{
    background:
      /* 右上角大块红色淡晕 */
      radial-gradient(circle 720px at 105% -120px, rgba(230, 0, 18, 0.10) 0%, transparent 55%),
      /* 左上角次级红色淡晕 */
      radial-gradient(circle 480px at -80px 80px, rgba(230, 0, 18, 0.06) 0%, transparent 60%),
      /* 底部左侧暗红淡晕 */
      radial-gradient(circle 600px at -100px 105%, rgba(140, 0, 16, 0.05) 0%, transparent 55%),
      /* 网格底纹 */
      url("{_GRID_SVG}"),
      /* 整体对角微渐变 */
      linear-gradient(135deg, #FBFBFC 0%, #FFFFFF 45%, #F6F6F8 100%);
    background-attachment: fixed, fixed, fixed, fixed, fixed;
    background-repeat: no-repeat, no-repeat, no-repeat, repeat, no-repeat;
    min-height: 100vh;
  }}

  /* 固定装饰：右下角浮动光晕 */
  .stApp::before {{
    content: "";
    position: fixed;
    right: -160px;
    bottom: -160px;
    width: 520px;
    height: 520px;
    background: radial-gradient(circle, rgba(230, 0, 18, 0.07) 0%, transparent 70%);
    pointer-events: none;
    z-index: 0;
  }}

  /* 主内容容器叠在装饰之上 */
  section.stMain {{
    position: relative;
    z-index: 1;
  }}

  /* ====== 主内容区 padding ====== */
  section.stMain .block-container {{
    padding-top: 1.5rem;
    padding-bottom: 3rem;
    max-width: 1280px;
  }}

  /* ====== H1 / H2 / H3 ====== */
  h1 {{
    color: {BRAND_INK};
    font-weight: 800;
    letter-spacing: -0.025em;
    text-shadow: 0 1px 0 rgba(255, 255, 255, 0.8);
  }}
  h2 {{
    color: {BRAND_INK};
    font-weight: 700;
    border-left: 4px solid {BRAND_RED};
    padding-left: 0.85rem;
    margin-top: 2rem !important;
    line-height: 1.4;
  }}
  h3 {{
    color: {BRAND_INK};
    font-weight: 600;
  }}

  /* ====== 侧边栏：渐变 + 微毛玻璃 + 右下角光晕 ====== */
  section[data-testid="stSidebar"] {{
    background:
      radial-gradient(circle 400px at 100% 100%, rgba(230, 0, 18, 0.08) 0%, transparent 60%),
      linear-gradient(180deg, #FFFFFF 0%, #FBFBFC 55%, {BRAND_GREY} 100%);
    border-right: 1px solid {BRAND_LINE};
    box-shadow: 1px 0 12px rgba(0, 0, 0, 0.03);
  }}
  section[data-testid="stSidebar"] .stTitle, section[data-testid="stSidebar"] h1 {{
    color: {BRAND_RED};
  }}

  /* ====== 侧边栏导航高亮 ====== */
  section[data-testid="stSidebarNav"] a {{
    border-radius: 8px !important;
    transition: all 0.16s ease;
  }}
  section[data-testid="stSidebarNav"] a[aria-current="page"] {{
    background: linear-gradient(90deg, {BRAND_RED_SOFT} 0%, rgba(255, 237, 239, 0.4) 100%);
    color: {BRAND_RED} !important;
    font-weight: 600;
    box-shadow: inset 3px 0 0 {BRAND_RED};
  }}
  section[data-testid="stSidebarNav"] a:hover {{
    color: {BRAND_RED} !important;
    transform: translateX(2px);
  }}

  /* ====== 主按钮：联通红 + 高级光感 ====== */
  .stButton > button[kind="primary"],
  .stDownloadButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {BRAND_RED} 0%, {BRAND_RED_DARK} 100%);
    border: 1px solid {BRAND_RED_DARK};
    color: #FFFFFF;
    font-weight: 600;
    box-shadow:
      0 4px 12px rgba(230, 0, 18, 0.28),
      inset 0 1px 0 rgba(255, 255, 255, 0.2);
    transition: all 0.18s ease;
  }}
  .stButton > button[kind="primary"]:hover,
  .stDownloadButton > button[kind="primary"]:hover {{
    background: linear-gradient(135deg, {BRAND_RED_DARK} 0%, {BRAND_RED_DEEP} 100%);
    transform: translateY(-1px);
    box-shadow:
      0 6px 18px rgba(230, 0, 18, 0.36),
      inset 0 1px 0 rgba(255, 255, 255, 0.2);
  }}

  /* ====== 普通按钮 ====== */
  .stButton > button {{
    transition: all 0.16s ease;
    border-radius: 8px;
  }}
  .stButton > button:hover {{
    border-color: {BRAND_RED};
    color: {BRAND_RED};
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(230, 0, 18, 0.10);
  }}

  /* ====== Metric 卡片：玻璃态 + hover 浮起 ====== */
  div[data-testid="stMetric"] {{
    background: rgba(255, 255, 255, 0.72);
    backdrop-filter: blur(12px) saturate(180%);
    -webkit-backdrop-filter: blur(12px) saturate(180%);
    border: 1px solid rgba(229, 229, 234, 0.7);
    border-left: 3px solid {BRAND_RED};
    border-radius: 12px;
    padding: 1.1rem 1.3rem;
    box-shadow:
      0 1px 3px rgba(0, 0, 0, 0.04),
      0 8px 24px rgba(0, 0, 0, 0.03);
    transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
  }}
  div[data-testid="stMetric"]::after {{
    content: "";
    position: absolute;
    top: 0;
    right: 0;
    width: 80px;
    height: 80px;
    background: radial-gradient(circle, rgba(230, 0, 18, 0.06) 0%, transparent 70%);
    pointer-events: none;
  }}
  div[data-testid="stMetric"]:hover {{
    transform: translateY(-2px);
    border-left-width: 4px;
    box-shadow:
      0 4px 8px rgba(0, 0, 0, 0.04),
      0 16px 32px rgba(230, 0, 18, 0.10);
  }}
  div[data-testid="stMetricLabel"] {{
    color: {BRAND_INK_SOFT};
    font-size: 0.82rem;
    font-weight: 500;
    letter-spacing: 0.01em;
  }}
  div[data-testid="stMetricValue"] {{
    color: {BRAND_INK};
    font-weight: 800;
    font-size: 1.55rem !important;
    letter-spacing: -0.02em;
  }}

  /* ====== Dataframe：玻璃态卡片包裹 ====== */
  div[data-testid="stDataFrame"] {{
    background: rgba(255, 255, 255, 0.78);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(229, 229, 234, 0.7);
    border-radius: 12px;
    padding: 4px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
  }}
  div[data-testid="stDataFrame"] thead tr th {{
    background-color: {BRAND_GREY} !important;
    color: {BRAND_INK} !important;
    font-weight: 600 !important;
    border-bottom: 2px solid {BRAND_RED} !important;
  }}

  /* ====== Info / Success / Warning / Error 提示 ====== */
  div[data-testid="stAlert"] {{
    border-radius: 10px;
    backdrop-filter: blur(8px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  }}

  /* ====== Tabs ====== */
  div[data-baseweb="tab-list"] {{
    border-bottom-color: {BRAND_LINE} !important;
  }}
  div[data-baseweb="tab-list"] button[aria-selected="true"] {{
    color: {BRAND_RED} !important;
    border-bottom-color: {BRAND_RED} !important;
    border-bottom-width: 2px !important;
    font-weight: 600;
  }}

  /* ====== Selectbox / TextInput 玻璃化 ====== */
  div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {{
    background: rgba(255, 255, 255, 0.72) !important;
    backdrop-filter: blur(8px);
  }}
  div[data-baseweb="select"] > div:focus-within,
  div[data-baseweb="input"] > div:focus-within {{
    border-color: {BRAND_RED} !important;
    box-shadow: 0 0 0 3px rgba(230, 0, 18, 0.12);
  }}

  /* ====== Hero banner：双层渐变 + 圆点纹理 + 中国结 ====== */
  .tem-hero {{
    background:
      /* 顶层径向高光 */
      radial-gradient(circle 380px at 18% 10%, rgba(255, 255, 255, 0.22) 0%, transparent 55%),
      /* 圆点纹理 */
      radial-gradient(circle at 1px 1px, rgba(255, 255, 255, 0.08) 1px, transparent 0),
      /* 主色对角渐变 */
      linear-gradient(135deg, {BRAND_RED} 0%, {BRAND_RED_DARK} 55%, {BRAND_RED_DEEP} 100%);
    background-size: auto, 22px 22px, auto;
    color: #FFFFFF;
    border-radius: 18px;
    padding: 2.4rem 2.6rem;
    margin: 0 0 1.8rem 0;
    box-shadow:
      0 12px 40px rgba(230, 0, 18, 0.28),
      0 2px 6px rgba(140, 0, 16, 0.16),
      inset 0 1px 0 rgba(255, 255, 255, 0.18);
    position: relative;
    overflow: hidden;
    isolation: isolate;
  }}
  /* 装饰：Hero 右上角白色光圈 */
  .tem-hero::before {{
    content: "";
    position: absolute;
    top: -120px;
    right: -120px;
    width: 360px;
    height: 360px;
    background: radial-gradient(circle, rgba(255, 255, 255, 0.16) 0%, transparent 65%);
    pointer-events: none;
  }}
  /* 装饰：Hero 底部红色暗光 */
  .tem-hero::after {{
    content: "";
    position: absolute;
    bottom: -80px;
    left: 30%;
    width: 320px;
    height: 200px;
    background: radial-gradient(ellipse, rgba(0, 0, 0, 0.16) 0%, transparent 65%);
    pointer-events: none;
  }}
  .tem-hero .tem-hero-title {{
    font-size: 2.1rem;
    font-weight: 800;
    margin: 0 0 0.5rem 0;
    letter-spacing: -0.02em;
    line-height: 1.25;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
    position: relative;
    z-index: 1;
  }}
  .tem-hero .tem-hero-sub {{
    font-size: 1.02rem;
    opacity: 0.94;
    margin: 0;
    line-height: 1.65;
    position: relative;
    z-index: 1;
  }}
  .tem-hero .tem-hero-meta {{
    margin-top: 1.3rem;
    display: inline-flex;
    align-items: center;
    background: rgba(255, 255, 255, 0.18);
    border: 1px solid rgba(255, 255, 255, 0.32);
    backdrop-filter: blur(8px);
    color: #FFFFFF;
    padding: 0.5rem 1.1rem;
    border-radius: 999px;
    font-size: 0.85rem;
    font-weight: 500;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    position: relative;
    z-index: 1;
  }}
  .tem-hero .tem-hero-meta::before {{
    content: "●";
    color: #FFFFFF;
    margin-right: 8px;
    font-size: 0.6rem;
    animation: pulse 2s ease-in-out infinite;
  }}
  @keyframes pulse {{
    0%, 100% {{ opacity: 1; }}
    50%      {{ opacity: 0.4; }}
  }}
  .tem-hero .tem-hero-knot {{
    position: absolute;
    right: 36px;
    top: 50%;
    transform: translateY(-50%);
    width: 140px;
    height: 140px;
    opacity: 0.28;
    z-index: 0;
  }}
  .tem-hero .tem-hero-knot svg {{
    width: 100%;
    height: 100%;
  }}

  /* ====== Section 标签 ====== */
  .tem-section-tag {{
    display: inline-block;
    background: linear-gradient(135deg, {BRAND_RED_SOFT} 0%, rgba(255, 237, 239, 0.6) 100%);
    color: {BRAND_RED};
    padding: 0.22rem 0.7rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
    letter-spacing: 0.02em;
    border: 1px solid rgba(230, 0, 18, 0.18);
    box-shadow: 0 1px 2px rgba(230, 0, 18, 0.06);
  }}

  /* ====== Expander 玻璃化 ====== */
  div[data-testid="stExpander"] {{
    border: 1px solid rgba(229, 229, 234, 0.7);
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.6);
    backdrop-filter: blur(8px);
  }}
  div[data-testid="stExpander"] summary:hover {{
    color: {BRAND_RED};
  }}

  /* ====== Divider 渐变 ====== */
  hr {{
    border: none;
    height: 1px;
    background: linear-gradient(90deg, transparent 0%, {BRAND_LINE} 20%, {BRAND_LINE} 80%, transparent 100%);
  }}

  /* ====== File uploader 卡片化 ====== */
  div[data-testid="stFileUploader"] section {{
    background: rgba(255, 255, 255, 0.72);
    backdrop-filter: blur(8px);
    border: 2px dashed rgba(230, 0, 18, 0.28);
    border-radius: 14px;
    transition: all 0.2s ease;
  }}
  div[data-testid="stFileUploader"] section:hover {{
    border-color: {BRAND_RED};
    background: rgba(255, 237, 239, 0.36);
  }}

  /* ====== Caption 颜色 ====== */
  div[data-testid="stCaption"] {{
    color: {BRAND_INK_SOFT};
  }}

  /* ====== Form 容器卡片化 ====== */
  div[data-testid="stForm"] {{
    background: rgba(255, 255, 255, 0.64);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(229, 229, 234, 0.6);
    border-radius: 14px;
    padding: 1.4rem !important;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
  }}

  /* ====================================================================
     背景光晕动画层
     ==================================================================== */
  .tem-bg-fx {{
    position: fixed;
    inset: 0;
    pointer-events: none;
    overflow: hidden;
    z-index: 0;
    /* 用户偏好减少动画时直接禁用 */
  }}
  @media (prefers-reduced-motion: reduce) {{
    .tem-bg-fx {{ display: none; }}
  }}

  /* ----- 4 个缓慢漂移的大光晕 ----- */
  .tem-glow {{
    position: absolute;
    width: 320px;
    height: 320px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(230, 0, 18, 0.16) 0%, transparent 70%);
    filter: blur(36px);
    animation: tem-drift 36s ease-in-out infinite;
    will-change: transform;
  }}
  .tem-glow.g1 {{ left: 8%;  top: 18%; animation-delay: 0s;  animation-duration: 42s; }}
  .tem-glow.g2 {{ left: 72%; top: 55%; animation-delay: 10s; animation-duration: 36s;
                  background: radial-gradient(circle, rgba(140, 0, 16, 0.14) 0%, transparent 70%); }}
  .tem-glow.g3 {{ left: 30%; top: 78%; animation-delay: 18s; animation-duration: 48s; width: 260px; height: 260px; }}
  .tem-glow.g4 {{ left: 85%; top: 12%; animation-delay: 24s; animation-duration: 40s; width: 220px; height: 220px;
                  background: radial-gradient(circle, rgba(255, 102, 113, 0.16) 0%, transparent 70%); }}

  @keyframes tem-drift {{
    0%   {{ transform: translate3d(0, 0, 0)            scale(1);    opacity: 0.65; }}
    25%  {{ transform: translate3d(60px, -50px, 0)     scale(1.08); opacity: 0.85; }}
    50%  {{ transform: translate3d(-30px, 80px, 0)     scale(0.94); opacity: 0.55; }}
    75%  {{ transform: translate3d(-80px, -30px, 0)    scale(1.05); opacity: 0.78; }}
    100% {{ transform: translate3d(0, 0, 0)            scale(1);    opacity: 0.65; }}
  }}

  /* 让正文层稳稳叠在背景装饰之上 */
  section[data-testid="stSidebar"], section.stMain {{
    position: relative;
    z-index: 1;
  }}
</style>
"""


_BG_FX_HTML = """
<div class="tem-bg-fx" aria-hidden="true">
  <div class="tem-glow g1"></div>
  <div class="tem-glow g2"></div>
  <div class="tem-glow g3"></div>
  <div class="tem-glow g4"></div>
</div>
"""


def apply_brand_theme(
    page_title: str = "TEM 通信费用管理",
    layout: str = "wide",
    background_fx: bool = True,
) -> None:
    """每个 Streamlit 页面在最顶部调用一次，应用品牌主题 + 注入 CSS。

    会做这些事：
      1. 设置 page 标题 / icon / layout
      2. 注入全局 CSS（联通红主题、字体、卡片、表格样式等）
      3. 注入背景光晕动画层（可关闭）
      4. 隐藏 Streamlit 默认页脚 / 菜单（已通过 CSS）

    Args:
      background_fx: 是否启用背景光晕动画，默认 True。
                     系统会自动遵从 prefers-reduced-motion，无需在此处禁用。
    """
    st.set_page_config(
        page_title=f"{page_title} · 诚翼畅联",
        page_icon="📡",
        layout=layout,
        menu_items={
            "About": "诚翼畅联 · TEM 一期账务底座 MVP\n"
                     "终端全生命周期管理平台 · 通信费用管理模块"
        },
    )
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)
    if background_fx:
        st.markdown(_BG_FX_HTML, unsafe_allow_html=True)


def hero(title: str, subtitle: str, meta: str | None = None) -> None:
    """在页面顶部渲染一个联通红 Hero banner。

    title    主标题（如"TEM 通信费用管理 · 月度首页"）
    subtitle 副文案
    meta     右下角小标签（如客户/项目/账期）
    """
    meta_html = f'<div class="tem-hero-meta">{meta}</div>' if meta else ""
    st.markdown(
        f"""
        <div class="tem-hero">
            <div class="tem-hero-knot">{UNICOM_KNOT_SVG}</div>
            <p class="tem-hero-title">{title}</p>
            <p class="tem-hero-sub">{subtitle}</p>
            {meta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_tag(label: str) -> None:
    """渲染小标签，常配合 st.subheader 使用，对齐设计文档章节编号。"""
    st.markdown(f'<span class="tem-section-tag">{label}</span>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 业务过滤器（保留旧 API，向后兼容）
# ---------------------------------------------------------------------------
def get_filters() -> tuple[str | None, str | None, str | None]:
    return (
        st.session_state.get("客户ID"),
        st.session_state.get("项目ID"),
        st.session_state.get("账期"),
    )


def require_filters() -> bool:
    """子页通用：未选客户/项目/账期时给出友好提示。"""
    客户ID, 项目ID, 账期 = get_filters()
    if not (客户ID and 项目ID and 账期):
        st.info("请回到 **streamlit app** 首页选择客户/项目/账期；或在 **📤 数据导入** 页上传数据后自动定位。")
        return False
    meta = f"客户 {客户ID} · {st.session_state.get('客户名称') or ''}　/　项目 {项目ID} · {st.session_state.get('项目名称') or ''}　/　账期 {账期}"
    st.caption(meta)
    return True


def query_fact(sql: str, extra_params: list | None = None) -> pd.DataFrame:
    """以当前 session_state 的客户/项目/账期为参数执行 SQL。

    SQL 必须含三个 ? 占位符：客户ID, 项目ID, 账期。
    """
    from tem.db import connect

    客户ID, 项目ID, 账期 = get_filters()
    params = [客户ID, 项目ID, 账期] + (extra_params or [])
    with connect(read_only=True) as con:
        return con.execute(sql, params).fetchdf()
