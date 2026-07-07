"""TEM 命令行入口。

子命令：
  tem init-db                                 创建/重建 DuckDB 库 + 6 张表 + 视图
  tem ingest --客户 X --项目 Y --账期 YYYYMM   按 data/raw/... 目录扫描并导入 5 类原始数据
  tem build  --客户 X --项目 Y --账期 YYYYMM   生成 fact_tem_monthly
  tem export --客户 X --项目 Y --账期 YYYYMM   导出月度 Excel 报表
  tem run    --客户 X --项目 Y --账期 YYYYMM   依次执行 ingest + build + export
  tem status                                  查看 DuckDB 库与各 raw_* 表行数
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

from .build import build_fact_tem_monthly
from .config import get_settings
from .db import connect, init_db, list_tables
from .ingest import (
    IngestContext,
    ingest_asset,
    ingest_billing,
    ingest_employee,
    ingest_event,
    ingest_usage,
)
from .reports import export_monthly_reports


def _build_ctx(客户ID: str, 项目ID: str, 账期: str | None) -> IngestContext:
    return IngestContext(客户ID=客户ID, 项目ID=项目ID, 账期=账期).resolve_meta()


@click.group()
def cli() -> None:
    """TEM 一期账务底座 CLI."""


@cli.command("sync-diff")
def cmd_sync_diff() -> None:
    """从 config/project_diff.yaml 同步项目差异规则到 DuckDB。"""
    from .meta.project_diff import sync_project_diff_from_config

    n = sync_project_diff_from_config(verbose=True)
    click.echo(f"[sync-diff] 已同步 {n} 条规则到 meta_project_diff")


@cli.command("init-db")
def cmd_init_db() -> None:
    """创建/重建 DuckDB 库与 DDL。"""
    init_db()
    click.echo(f"[init-db] 当前表: {', '.join(list_tables())}")


@cli.command("status")
def cmd_status() -> None:
    """查看库内各表行数。"""
    settings = get_settings()
    click.echo(f"DuckDB 路径: {settings.db_path}")
    if not settings.db_path.exists():
        click.echo("[status] 数据库尚未初始化，先运行: tem init-db")
        return
    with connect(read_only=True) as con:
        for t in list_tables():
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            click.echo(f"  {t:<28}: {n} 行")


def _common_opts(f):
    f = click.option("--客户", "客户ID", required=True, help="客户ID")(f)
    f = click.option("--项目", "项目ID", required=True, help="项目ID")(f)
    f = click.option("--账期", "账期", required=False, help="YYYYMM，如 202604（asset/employee 可不传）")(f)
    return f


@cli.command("ingest")
@_common_opts
@click.option("--type", "types",
              multiple=True,
              type=click.Choice(["usage", "billing", "asset", "employee", "event"]),
              help="只导入指定类型；不传则全部尝试")
def cmd_ingest(客户ID: str, 项目ID: str, 账期: str | None, types: tuple[str, ...]) -> None:
    """按目录约定扫描并导入原始数据。"""
    ctx = _build_ctx(客户ID, 项目ID, 账期)
    targets = types or ("usage", "billing", "asset", "employee", "event")

    if "usage" in targets:
        n = ingest_usage(ctx)
        click.echo(f"[ingest] raw_usage          : {n} 行")
    if "billing" in targets:
        counts = ingest_billing(ctx)
        click.echo(f"[ingest] raw_billing_list   : {counts.get('billing_list', 0)} 行")
        click.echo(f"[ingest] raw_billing_detail : {counts.get('billing_detail', 0)} 行")
    if "asset" in targets:
        n = ingest_asset(ctx)
        click.echo(f"[ingest] raw_asset          : {n} 行")
    if "employee" in targets:
        n = ingest_employee(ctx)
        click.echo(f"[ingest] raw_employee       : {n} 行")
    if "event" in targets:
        n = ingest_event(ctx)
        click.echo(f"[ingest] raw_event          : {n} 行")


@cli.command("build")
@_common_opts
def cmd_build(客户ID: str, 项目ID: str, 账期: str | None) -> None:
    """跑规则引擎，生成 fact_tem_monthly。"""
    if not 账期:
        raise click.UsageError("build 子命令需要 --账期 参数")
    n = build_fact_tem_monthly(客户ID, 项目ID, 账期)
    click.echo(f"[build] fact_tem_monthly: {n} 行 ({客户ID}/{项目ID}/{账期})")


@cli.command("export")
@_common_opts
def cmd_export(客户ID: str, 项目ID: str, 账期: str | None) -> None:
    """导出月度 Excel 报表。"""
    if not 账期:
        raise click.UsageError("export 子命令需要 --账期 参数")
    out = export_monthly_reports(客户ID, 项目ID, 账期)
    click.echo(f"[export] 生成报表: {out}")


@cli.command("run")
@_common_opts
def cmd_run(客户ID: str, 项目ID: str, 账期: str | None) -> None:
    """一键执行 ingest + build + export。"""
    if not 账期:
        raise click.UsageError("run 子命令需要 --账期 参数")
    ctx = _build_ctx(客户ID, 项目ID, 账期)
    n_usage = ingest_usage(ctx)
    counts = ingest_billing(ctx)
    n_asset = ingest_asset(ctx)
    n_emp = ingest_employee(ctx)
    n_event = ingest_event(ctx)
    click.echo(
        f"[run/ingest] usage={n_usage}, billing_list={counts.get('billing_list', 0)}, "
        f"billing_detail={counts.get('billing_detail', 0)}, asset={n_asset}, "
        f"employee={n_emp}, event={n_event}"
    )
    n_fact = build_fact_tem_monthly(客户ID, 项目ID, 账期)
    click.echo(f"[run/build] fact_tem_monthly: {n_fact}")
    out = export_monthly_reports(客户ID, 项目ID, 账期)
    click.echo(f"[run/export] {out}")


def main() -> None:  # pragma: no cover
    cli(prog_name="tem", standalone_mode=True)


if __name__ == "__main__":  # pragma: no cover
    main()
