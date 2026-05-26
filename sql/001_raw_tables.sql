-- =====================================================================
-- TEM 一期账务底座 - 五类原始数据表 DDL
-- 设计依据：《一期账务底座与 TEM 通信费用管理模块详细设计 v1.1》
--   §6.1 平台通用字段（所有表强制带 8 个）
--   §7   raw_usage    运营商用量数据表
--   §8   raw_billing  运营商账单清单 + 明细（拆为两张）
--   §9   raw_asset    资产管理系统表
--   §10  raw_employee 企业人员信息表
--   §11  raw_event    月度事件变更总表
-- =====================================================================

-- 平台通用字段（§6.1）说明：
--   客户ID / 客户名称 / 项目ID / 项目名称 / 数据月份 / 数据来源 / 导入批次号 / 数据更新时间

-- ---------------------------------------------------------------------
-- 表一：raw_usage_运营商用量数据表（§7）
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_usage (
    -- §6.1 平台通用字段
    客户ID         VARCHAR NOT NULL,
    客户名称       VARCHAR,
    项目ID         VARCHAR NOT NULL,
    项目名称       VARCHAR,
    数据月份       VARCHAR,
    数据来源       VARCHAR,
    导入批次号     VARCHAR NOT NULL,
    数据更新时间   TIMESTAMP,

    -- §7.4 业务字段
    账期               VARCHAR NOT NULL,            -- 如 202604
    服务号码           VARCHAR NOT NULL,
    总短信条数         INTEGER,
    总通话时长_秒      DOUBLE,
    总通话分钟         DOUBLE,                      -- U02: 秒/60
    总流量_M           DOUBLE,
    总流量_GB          DOUBLE,                      -- U03: M/1024
    主叫通话时长       DOUBLE,
    被叫通话时长       DOUBLE,
    国内漫游流量       DOUBLE,
    港澳台漫游流量     DOUBLE,
    国际漫游流量       DOUBLE,
    是否有语音         BOOLEAN,
    是否有流量         BOOLEAN,
    是否有短信         BOOLEAN,
    是否零用量         BOOLEAN,                     -- U05
    是否漫游使用       BOOLEAN                      -- U06
);

CREATE INDEX IF NOT EXISTS idx_raw_usage_pk
  ON raw_usage(客户ID, 项目ID, 账期, 服务号码);

-- ---------------------------------------------------------------------
-- 表二A：raw_billing_list 账单清单（§8.4）  每号码每月一行
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_billing_list (
    客户ID         VARCHAR NOT NULL,
    客户名称       VARCHAR,
    项目ID         VARCHAR NOT NULL,
    项目名称       VARCHAR,
    数据月份       VARCHAR,
    数据来源       VARCHAR,
    导入批次号     VARCHAR NOT NULL,
    数据更新时间   TIMESTAMP,

    账期           VARCHAR NOT NULL,
    服务号码       VARCHAR NOT NULL,
    用户状态       VARCHAR,                         -- 在网/停机/销户
    计费应收       DOUBLE,
    账务优惠       DOUBLE,
    实际应收       DOUBLE,                          -- B01 主金额口径
    账户标识       VARCHAR,
    账户名称       VARCHAR,
    用户标识       VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_raw_billing_list_pk
  ON raw_billing_list(客户ID, 项目ID, 账期, 服务号码);

-- ---------------------------------------------------------------------
-- 表二B：raw_billing_detail 账单明细（§8.5）  每号码 N 条费用科目
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_billing_detail (
    客户ID         VARCHAR NOT NULL,
    客户名称       VARCHAR,
    项目ID         VARCHAR NOT NULL,
    项目名称       VARCHAR,
    数据月份       VARCHAR,
    数据来源       VARCHAR,
    导入批次号     VARCHAR NOT NULL,
    数据更新时间   TIMESTAMP,

    账期           VARCHAR NOT NULL,
    服务号码       VARCHAR NOT NULL,
    一级科目       VARCHAR NOT NULL,                -- 月固定费/上网费/语音通话费/增值业务费/国际漫游...
    二级科目       VARCHAR,
    三级科目       VARCHAR,
    明细科目编码   VARCHAR,
    计费应收       DOUBLE,
    账务优惠       DOUBLE,
    实际应收       DOUBLE
);

CREATE INDEX IF NOT EXISTS idx_raw_billing_detail_pk
  ON raw_billing_detail(客户ID, 项目ID, 账期, 服务号码);

-- ---------------------------------------------------------------------
-- 表三：raw_asset 资产管理系统表（§9）
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_asset (
    客户ID         VARCHAR NOT NULL,
    客户名称       VARCHAR,
    项目ID         VARCHAR NOT NULL,
    项目名称       VARCHAR,
    数据月份       VARCHAR,
    数据来源       VARCHAR,
    导入批次号     VARCHAR NOT NULL,
    数据更新时间   TIMESTAMP,

    服务号码       VARCHAR,                         -- A01: 来源 Phone number
    联系人         VARCHAR,
    邮箱           VARCHAR,
    员工编号       VARCHAR,
    内部用户编号   VARCHAR,
    组织名称       VARCHAR,
    资产状态       VARCHAR,                         -- 在用/库存/停用
    品牌           VARCHAR,
    型号           VARCHAR,
    IMEI           VARCHAR,
    序列号         VARCHAR,
    采购日期       DATE,
    投产日期       DATE,
    保修到期日     DATE,
    标准套餐金额   DOUBLE                           -- C01: 超套基准
);

CREATE INDEX IF NOT EXISTS idx_raw_asset_pk
  ON raw_asset(客户ID, 项目ID, 服务号码);

-- ---------------------------------------------------------------------
-- 表四：raw_employee 企业人员信息表（§10）
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_employee (
    客户ID         VARCHAR NOT NULL,
    客户名称       VARCHAR,
    项目ID         VARCHAR,
    项目名称       VARCHAR,
    数据月份       VARCHAR,
    数据来源       VARCHAR,
    导入批次号     VARCHAR NOT NULL,
    数据更新时间   TIMESTAMP,

    员工ID         VARCHAR NOT NULL,                -- E01 主键字段
    员工姓名       VARCHAR,
    邮箱           VARCHAR,
    员工状态       VARCHAR,                         -- 在职/离职/转岗
    法人主体       VARCHAR,
    BU             VARCHAR,                         -- BU / Function
    Department     VARCHAR,
    CostCenter     VARCHAR,
    LineManager    VARCHAR,
    ManagerEmail   VARCHAR,
    Location       VARCHAR,
    生效日期       DATE,
    离职日期       DATE
);

CREATE INDEX IF NOT EXISTS idx_raw_employee_pk
  ON raw_employee(客户ID, 员工ID);

-- ---------------------------------------------------------------------
-- 表五：raw_event 月度事件变更总表（§11，第一阶段以"总表"为准）
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_event (
    客户ID         VARCHAR NOT NULL,
    客户名称       VARCHAR,
    项目ID         VARCHAR NOT NULL,
    项目名称       VARCHAR,
    数据月份       VARCHAR,
    数据来源       VARCHAR,
    导入批次号     VARCHAR NOT NULL,
    数据更新时间   TIMESTAMP,

    -- §11.4 业务字段（标准化命名）
    原始服务号码   VARCHAR,                         -- EV03
    新服务号码     VARCHAR,                         -- EV04
    副卡号码       VARCHAR,                         -- EV06
    事件类型       VARCHAR NOT NULL,                -- 入职/套餐变更/离职归还/维修/设备丢失
    事件动作       VARCHAR,                         -- 库存变更/新套餐申请/改号/副卡申请...
    开始时间       DATE,
    完成时间       DATE,
    事件状态       VARCHAR,                         -- On-Boarding/Completed/Canceled
    原使用人       VARCHAR,
    当前使用人     VARCHAR,
    员工ID         VARCHAR,                         -- EV07 来源：使用人WWID
    部门           VARCHAR,
    系统流水号     VARCHAR,
    当前设备序列号 VARCHAR,
    旧设备序列号   VARCHAR,
    备注           VARCHAR,
    事件月份       VARCHAR                          -- 由开始时间派生 yyyymm
);

CREATE INDEX IF NOT EXISTS idx_raw_event_pk
  ON raw_event(客户ID, 项目ID, 原始服务号码, 开始时间, 事件类型, 事件动作);
