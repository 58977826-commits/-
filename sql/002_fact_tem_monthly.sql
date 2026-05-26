-- =====================================================================
-- TEM 月度通信费用分析结果表 fact_tem_monthly
-- 设计依据：《一期账务底座与 TEM 通信费用管理模块详细设计 v1.1》§12
--   主键：客户ID + 项目ID + 账期 + 服务号码
--   来源：raw_usage / raw_billing_list / raw_billing_detail /
--         raw_asset / raw_employee / raw_event 经过匹配 + 规则引擎计算后落库
-- =====================================================================

CREATE TABLE IF NOT EXISTS fact_tem_monthly (
    -- 平台管理（§12.4）
    客户ID                 VARCHAR NOT NULL,
    客户名称               VARCHAR,
    项目ID                 VARCHAR NOT NULL,
    项目名称               VARCHAR,

    -- 基础信息
    账期                   VARCHAR NOT NULL,
    服务号码               VARCHAR NOT NULL,

    -- 员工信息
    员工ID                 VARCHAR,
    员工姓名               VARCHAR,
    邮箱                   VARCHAR,

    -- 组织信息
    BU                     VARCHAR,
    Department             VARCHAR,
    CostCenter             VARCHAR,
    LineManager            VARCHAR,

    -- 资产信息
    资产状态               VARCHAR,
    设备型号               VARCHAR,
    IMEI                   VARCHAR,
    序列号                 VARCHAR,

    -- 费用信息
    标准套餐金额           DOUBLE,
    实际应收               DOUBLE,
    超套金额               DOUBLE,                  -- C02
    超套率                 DOUBLE,                  -- C04

    -- 用量信息
    总流量GB               DOUBLE,
    总通话分钟             DOUBLE,
    短信条数               INTEGER,

    -- 判断标签（§12.4 + 派生）
    是否零用量             BOOLEAN,
    是否零用量但计费       BOOLEAN,                 -- Z02
    是否长期闲置           BOOLEAN,                 -- Z03
    是否低用量             BOOLEAN,
    是否高流量             BOOLEAN,
    是否高通话             BOOLEAN,
    是否漫游               BOOLEAN,
    是否增值业务异常       BOOLEAN,
    增值业务金额           DOUBLE,                  -- B05 派生
    是否离职后计费         BOOLEAN,
    是否超套               BOOLEAN,
    是否资产缺失           BOOLEAN,
    是否人员缺失           BOOLEAN,

    -- 事件信息
    是否存在当月事件       BOOLEAN,
    当月事件类型           VARCHAR,
    当月事件动作           VARCHAR,
    当月事件状态           VARCHAR,
    是否事件未闭环         BOOLEAN,
    是否改号               BOOLEAN,
    新服务号码             VARCHAR,
    是否副卡申请           BOOLEAN,
    副卡号码               VARCHAR,
    系统流水号             VARCHAR,

    -- 异常处理
    异常类型               VARCHAR,                 -- 多类型逗号拼接
    异常金额               DOUBLE,
    建议动作               VARCHAR,
    处理状态               VARCHAR DEFAULT '未处理',
    备注                   VARCHAR,

    -- 数据血缘
    导入批次号             VARCHAR,
    数据更新时间           TIMESTAMP,

    PRIMARY KEY (客户ID, 项目ID, 账期, 服务号码)
);

CREATE INDEX IF NOT EXISTS idx_fact_tem_costcenter
  ON fact_tem_monthly(客户ID, 项目ID, 账期, CostCenter);

CREATE INDEX IF NOT EXISTS idx_fact_tem_employee
  ON fact_tem_monthly(客户ID, 员工ID);
