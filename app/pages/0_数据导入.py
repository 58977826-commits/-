"""§数据导入 - 拖拽 Excel/CSV → 自动识别字段 → 一键入库。

特性：
  - 支持一次上传多个文件
  - 列名识别为主、文件名兜底，5 类表自动归类
  - 识别预览：每个 sheet 的列名与归属一目了然
  - 一键执行 ingest + 可选触发规则引擎 build
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
_APP = _ROOT / "app"
for _p in (_SRC, _APP):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _shared import init_page, section_tag  # noqa: E402
from tem.build import build_fact_tem_monthly  # noqa: E402
from tem.config import get_settings  # noqa: E402
from tem.db import connect  # noqa: E402
from tem.ingest import (  # noqa: E402
    IngestContext,
    IngestGateError,
    auto_ingest_files,
    detect_excel_file,
    prevalidate_files,
)


init_page("数据导入", layout="wide")
section_tag("数据接入")
st.title("📤 数据导入")
st.caption("拖拽 Excel / CSV 文件 → 系统自动识别属于用量 / 账单 / 资产 / 人员 / 事件中的哪一类 → 一键入库")


# ---------------------------------------------------------------------------
# 上下文（客户 / 项目 / 账期）
# ---------------------------------------------------------------------------
settings = get_settings()

# 客户 / 项目 下拉选项
_client_choices: list[tuple[str, str]] = []
for c in settings.clients:
    cid = c.get("客户ID", "")
    cname = c.get("客户名称", cid)
    _client_choices.append((cid, f"{cid} · {cname}"))
if not _client_choices:
    _client_choices = [(settings.default_客户ID, f"{settings.default_客户ID} · {settings.default_客户名称}")]

# 当前会话中已选择的客户，作为默认值
_default_cid = st.session_state.get("客户ID") or _client_choices[0][0]
_default_pid = st.session_state.get("项目ID") or "work-phone"
_default_period = st.session_state.get("账期") or "202604"

st.subheader("第 1 步：选择客户 / 项目 / 账期")

col1, col2, col3 = st.columns(3)
with col1:
    cid_labels = [lbl for _, lbl in _client_choices]
    cid_values = [v for v, _ in _client_choices]
    idx = cid_values.index(_default_cid) if _default_cid in cid_values else 0
    selected_label = st.selectbox("客户", cid_labels, index=idx)
    客户ID = cid_values[cid_labels.index(selected_label)]

with col2:
    # 项目下拉来自 settings.yaml，允许手动输入新项目
    projects_for_client = []
    for c in settings.clients:
        if c.get("客户ID") == 客户ID:
            projects_for_client = [p.get("项目ID", "") for p in c.get("projects", [])]
            break
    if 项目ID := st.selectbox(
        "项目",
        projects_for_client or [_default_pid],
        index=(projects_for_client.index(_default_pid) if _default_pid in projects_for_client else 0),
        key="proj_select",
    ):
        pass
    new_proj = st.text_input("（也可手动输入新项目 ID）", value="", placeholder="留空则使用上面选中的")
    if new_proj.strip():
        项目ID = new_proj.strip()

with col3:
    账期 = st.text_input(
        "账期 (YYYYMM)",
        value=_default_period,
        help="账期格式如 202604。资产 / 人员 / 事件表无账期粒度，但仍需提供给规则引擎",
    )


# ---------------------------------------------------------------------------
# 文件上传
# ---------------------------------------------------------------------------
st.subheader("第 2 步：上传 Excel / CSV 文件")
st.caption(
    "可一次上传多个文件，系统会按表头列名自动识别每个文件属于哪一类。"
    "列名不识别时会尝试用文件名兜底（如 `raw_usage_*.xlsx`）。"
)

uploaded_files = st.file_uploader(
    "拖拽或点击选择文件（支持 .xlsx / .xls / .csv，可多选）",
    type=["xlsx", "xls", "csv"],
    accept_multiple_files=True,
    key="tem_uploader",
)


# 识别预览
def _save_uploads_to_temp(files, tmp_dir: Path) -> list[Path]:
    out = []
    for uf in files:
        # 保留原始文件名
        target = tmp_dir / uf.name
        target.write_bytes(uf.getbuffer())
        out.append(target)
    return out


_TABLE_LABELS = {
    "usage": "运营商用量 → raw_usage",
    "billing": "运营商账单 → raw_billing_list / raw_billing_detail",
    "asset": "资产管理 → raw_asset",
    "employee": "企业人员 → raw_employee",
    "event": "月度事件 → raw_event",
    None: "未识别 ⚠️",
}


def _render_gate_reports(gate_reports: list[dict]) -> None:
    """展示 Import Gate 校验报告（导入与预检共用）。"""
    if not gate_reports:
        return
    st.markdown("##### Import Gate 校验报告")
    gate_rows = []
    for gr in gate_reports:
        issues = gr.get("issues", [])
        errors = [i["message"] for i in issues if i.get("level") == "error"]
        warns = [i["message"] for i in issues if i.get("level") == "warning"]
        gate_rows.append({
            "目标表": gr.get("target_table"),
            "行数": gr.get("row_count"),
            "通过": "是" if gr.get("passed") else "否",
            "未映射列数": len(gr.get("unmapped_source_columns", [])),
            "主键重复行": gr.get("duplicate_pk_count", 0),
            "错误": "；".join(errors[:2]) or "—",
            "警告": "；".join(warns[:2]) or "—",
        })
    st.dataframe(pd.DataFrame(gate_rows), use_container_width=True, hide_index=True)

    with st.expander("查看 Gate 详细问题", expanded=False):
        for gr in gate_reports:
            st.markdown(f"**{gr.get('target_table')}** · {gr.get('row_count', 0)} 行")
            for issue in gr.get("issues", []):
                level = issue.get("level", "info")
                icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(level, "·")
                st.markdown(f"- {icon} **{issue.get('code', '')}** {issue.get('message', '')}")


if uploaded_files:
    st.subheader("第 3 步：识别预览")

    # 暂存到临时目录用于预览
    if "_preview_dir" not in st.session_state:
        st.session_state["_preview_dir"] = tempfile.mkdtemp(prefix="tem_preview_")
    preview_dir = Path(st.session_state["_preview_dir"])
    # 清空旧文件
    for f in preview_dir.glob("*"):
        try:
            f.unlink()
        except OSError:
            pass
    preview_paths = _save_uploads_to_temp(uploaded_files, preview_dir)

    rows = []
    for p in preview_paths:
        info = detect_excel_file(p)
        rows.append({
            "文件": p.name,
            "识别结果": _TABLE_LABELS.get(info["primary_type"], "未识别"),
            "依据": "文件名兜底" if info.get("from_filename") else ("列名匹配" if info["primary_type"] else "—"),
            "sheet 数": len([s for s in info["sheets"] if s["table_type"] != "skip"]),
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # 展开看每个 sheet 的列详情
    with st.expander("查看各文件的 sheet 列名详情", expanded=False):
        for p in preview_paths:
            info = detect_excel_file(p)
            st.markdown(f"#### 📄 {p.name}")
            for s in info["sheets"]:
                if s["table_type"] == "skip":
                    st.caption(f"  sheet `{s['name']}` → 跳过（字典 / 下拉表）")
                    continue
                t = _TABLE_LABELS.get(s["table_type"], "未识别")
                st.markdown(f"- sheet `{s['name']}` → **{t}** · {len(s['columns'])} 列")
                if s["columns"]:
                    st.caption("  · 列名：" + ", ".join(s["columns"]))

    # ---------------------------------------------------------------------------
    # 入库
    # ---------------------------------------------------------------------------
    st.subheader("第 4 步：开始导入")

    col_a, col_b = st.columns([1, 3])
    with col_a:
        do_build = st.checkbox("入库后跑规则引擎", value=True, help="生成 fact_tem_monthly 月度结果表")
    with col_b:
        do_clear_cache = st.checkbox("导入后清空看板缓存", value=True, help="强制首页 / 各报表页刷新")

    btn_pre, btn_import = st.columns(2)
    with btn_pre:
        run_precheck = st.button("🔍 导入前预检", help="只跑 Import Gate，不写库、不复制 raw 目录")
    with btn_import:
        run_import = st.button("🚀 开始导入", type="primary")

    if run_precheck:
        if not (客户ID and 项目ID and 账期):
            st.error("客户 / 项目 / 账期 不能为空")
            st.stop()

        ctx = IngestContext(客户ID=客户ID, 项目ID=项目ID, 账期=账期)
        with st.spinner("Import Gate 预检中（不写库）..."):
            result = prevalidate_files(preview_paths, ctx)

        summary = result["summary"]
        if summary.get("would_block"):
            st.error(
                f"预检未通过：{summary.get('error_count', 0)} 个错误，"
                f"{summary.get('warning_count', 0)} 个警告。"
                " strict 模式下正式导入将被阻断。"
            )
        elif summary.get("passed"):
            st.success(
                f"✅ 预检通过：{summary.get('file_count', 0)} 个文件，"
                f"预计 {summary.get('row_count', 0)} 行可写入"
            )
        else:
            st.warning("预检完成，但未产生有效 Gate 报告，请检查文件识别结果。")

        st.markdown("##### 预检文件报告")
        precheck_df = pd.DataFrame([
            {
                "文件": r["file"],
                "识别为": _TABLE_LABELS.get(r["primary_type"], "未识别"),
                "依据": "文件名兜底" if r.get("from_filename") else "列名匹配",
                "预检通过": "是" if r.get("precheck_passed") else "否",
                "会阻断导入": "是" if r.get("precheck_blocked") else "否",
                "错误": r.get("error", "—"),
            }
            for r in result["file_reports"]
        ])
        st.dataframe(precheck_df, use_container_width=True, hide_index=True)
        _render_gate_reports(result.get("gate_reports", []))

    if run_import:
        if not (客户ID and 项目ID and 账期):
            st.error("客户 / 项目 / 账期 不能为空")
            st.stop()

        with tempfile.TemporaryDirectory(prefix="tem_ingest_") as td:
            tmp_paths = _save_uploads_to_temp(uploaded_files, Path(td))
            ctx = IngestContext(客户ID=客户ID, 项目ID=项目ID, 账期=账期)

            with st.spinner("识别 + 入库中..."):
                try:
                    result = auto_ingest_files(tmp_paths, ctx)
                except IngestGateError as e:
                    st.error(f"Import Gate 阻断写库：{e}")
                    for gr in e.report.issues:
                        if gr.level == "error":
                            st.markdown(f"- **{gr.code}** {gr.message}")
                    st.stop()

            counts = result["ingest_counts"]
            gate_reports = result.get("gate_reports", [])
            if any(v > 0 for v in counts.values()):
                st.success(f"✅ 导入完成：{len(uploaded_files)} 个文件，{sum(counts.values())} 行入库")
            else:
                st.warning("⚠️ 没有数据进入任何 raw_* 表，请检查识别结果或列名映射")

            st.markdown("##### 入库行数")
            count_df = pd.DataFrame([
                {"表名": k, "新增/覆盖行数": v} for k, v in counts.items() if v > 0
            ])
            if not count_df.empty:
                st.dataframe(count_df, use_container_width=True, hide_index=True)

            st.markdown("##### 文件处理报告")
            report_df = pd.DataFrame([
                {
                    "文件": r["file"],
                    "识别为": _TABLE_LABELS.get(r["primary_type"], "未识别"),
                    "依据": "文件名兜底" if r.get("from_filename") else "列名匹配",
                    "落地路径": r.get("landed_at", "—"),
                    "错误": r.get("error", "—"),
                }
                for r in result["file_reports"]
            ])
            st.dataframe(report_df, use_container_width=True, hide_index=True)

            _render_gate_reports(gate_reports)

            if do_build and any(v > 0 for v in counts.values()):
                with st.spinner("跑规则引擎生成 fact_tem_monthly..."):
                    n = build_fact_tem_monthly(客户ID, 项目ID, 账期)
                st.success(f"📊 fact_tem_monthly 写入 {n} 行")

            if do_clear_cache:
                st.cache_data.clear()

            # 把当前选择写回 session_state，方便切到看板各页时自动定位
            st.session_state["客户ID"] = 客户ID
            st.session_state["项目ID"] = 项目ID
            st.session_state["账期"] = 账期

            st.info(
                f"现在可以切换到左侧任一报表页（建议先看 **诚翼畅联数据管理平台** 首页或 **费用统计**），"
                f"系统会自动定位到 `{客户ID} / {项目ID} / {账期}`"
            )

else:
    st.info("👆 请先在上面的上传框中拖入文件。文件不会立即入库，先做识别预览。")


# ---------------------------------------------------------------------------
# 底部：当前库内已有数据
# ---------------------------------------------------------------------------
st.divider()
with st.expander("查看当前库内已有的 (客户 / 项目 / 账期) 组合", expanded=False):
    try:
        with connect(read_only=True) as con:
            df_combo = con.execute("""
                SELECT 客户ID, 项目ID, 账期, COUNT(*) AS 号码数, SUM(实际应收) AS 实际应收合计
                FROM fact_tem_monthly
                GROUP BY 客户ID, 项目ID, 账期
                ORDER BY 客户ID, 项目ID, 账期 DESC
            """).fetchdf()
        if df_combo.empty:
            st.caption("库内还没有任何 fact_tem_monthly 数据。先上传文件 + 跑规则引擎。")
        else:
            st.dataframe(df_combo, use_container_width=True, hide_index=True)
    except Exception as e:  # noqa: BLE001
        st.error(f"查询失败：{e}")
