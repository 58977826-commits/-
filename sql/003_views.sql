-- =====================================================================
-- 报表视图 - 服务于 Streamlit 七张报表（§15.1 ~ §15.7）
-- =====================================================================

-- §15.1 月度首页核心指标
CREATE OR REPLACE VIEW v_monthly_summary AS
SELECT
    客户ID,
    客户名称,
    项目ID,
    项目名称,
    账期,
    SUM(实际应收)                              AS 月度账单总额,
    COUNT(*)                                   AS 分析号码数,
    AVG(实际应收)                              AS 人均账单金额,
    SUM(超套金额)                              AS 超套金额,
    SUM(CASE WHEN 是否超套 THEN 1 ELSE 0 END)  AS 超套号码数,
    SUM(CASE WHEN 是否零用量 THEN 1 ELSE 0 END) AS 零用量号码数,
    SUM(CASE WHEN 是否高流量 THEN 1 ELSE 0 END) AS 高流量号码数,
    SUM(CASE WHEN 是否高通话 THEN 1 ELSE 0 END) AS 高通话号码数,
    SUM(CASE WHEN 是否漫游 THEN 1 ELSE 0 END)  AS 漫游号码数,
    SUM(CASE WHEN 是否事件未闭环 THEN 1 ELSE 0 END) AS 未闭环事件数,
    SUM(CASE WHEN 异常类型 IS NOT NULL AND 异常类型 <> '' THEN 1 ELSE 0 END) AS 异常待处理数
FROM fact_tem_monthly
GROUP BY 客户ID, 客户名称, 项目ID, 项目名称, 账期;

-- §15.6 成本中心分摊
CREATE OR REPLACE VIEW v_costcenter_allocation AS
SELECT
    客户ID,
    客户名称,
    项目ID,
    项目名称,
    账期,
    BU,
    Department,
    CostCenter,
    COUNT(*)                                   AS 号码数,
    COUNT(DISTINCT 员工ID)                      AS 员工数,
    SUM(实际应收)                              AS 实际应收合计,
    SUM(超套金额)                              AS 超套金额,
    SUM(CASE WHEN 是否零用量 THEN 实际应收 ELSE 0 END) AS 零用量费用,
    SUM(CASE WHEN 异常类型 IS NOT NULL AND 异常类型 <> '' THEN 异常金额 ELSE 0 END) AS 异常费用
FROM fact_tem_monthly
GROUP BY 客户ID, 客户名称, 项目ID, 项目名称, 账期, BU, Department, CostCenter;

-- §15.5 异常清单
CREATE OR REPLACE VIEW v_anomaly_list AS
SELECT
    客户ID,
    客户名称,
    项目ID,
    项目名称,
    账期,
    服务号码,
    员工姓名,
    Department,
    CostCenter,
    异常类型,
    异常金额,
    实际应收,
    是否存在当月事件,
    当月事件类型,
    建议动作,
    LineManager  AS 责任人,
    处理状态,
    备注
FROM fact_tem_monthly
WHERE 异常类型 IS NOT NULL AND 异常类型 <> '';

-- §15.4 超套清单
CREATE OR REPLACE VIEW v_overpackage_list AS
SELECT
    客户ID,
    客户名称,
    项目ID,
    项目名称,
    账期,
    服务号码,
    员工姓名,
    Department,
    CostCenter,
    标准套餐金额,
    实际应收,
    超套金额,
    超套率,
    总流量GB,
    总通话分钟,
    当月事件类型,
    当月事件动作
FROM fact_tem_monthly
WHERE 是否超套 = TRUE;

-- §15.7 事件运营
CREATE OR REPLACE VIEW v_event_overview AS
SELECT
    客户ID,
    项目ID,
    数据月份,
    事件类型,
    事件动作,
    事件状态,
    COUNT(*) AS 事件数
FROM raw_event
GROUP BY 客户ID, 项目ID, 数据月份, 事件类型, 事件动作, 事件状态;
