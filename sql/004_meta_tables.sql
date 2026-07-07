-- =====================================================================
-- TEM 元数据表：Import Gate 报告 + 项目差异规则
-- 支撑 B 路径：Import Gate / 规则表 / 差异表
-- =====================================================================

-- 每次 ingest 写库前的 Gate 校验报告（JSON 明细）
CREATE TABLE IF NOT EXISTS meta_import_report (
    导入批次号     VARCHAR NOT NULL,
    客户ID         VARCHAR NOT NULL,
    项目ID         VARCHAR NOT NULL,
    账期           VARCHAR,
    目标表         VARCHAR NOT NULL,
    源文件         VARCHAR,
    行数           INTEGER,
    状态           VARCHAR NOT NULL,          -- passed | warned | blocked
    报告JSON       VARCHAR,
    数据更新时间   TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_meta_import_report_batch
  ON meta_import_report(导入批次号);

CREATE INDEX IF NOT EXISTS idx_meta_import_report_scope
  ON meta_import_report(客户ID, 项目ID, 账期);

-- 项目差异确认表（标准规则 vs 本项目规则）
CREATE TABLE IF NOT EXISTS meta_project_diff (
    客户ID         VARCHAR NOT NULL,
    项目ID         VARCHAR NOT NULL,
    规则ID         VARCHAR NOT NULL,
    规则类别       VARCHAR,
    标准规则       VARCHAR,
    本项目规则     VARCHAR,
    确认方         VARCHAR,
    是否可复用     BOOLEAN DEFAULT TRUE,
    备注           VARCHAR,
    生效账期       VARCHAR,
    数据来源       VARCHAR DEFAULT 'config/project_diff.yaml',
    数据更新时间   TIMESTAMP,
    PRIMARY KEY (客户ID, 项目ID, 规则ID)
);
