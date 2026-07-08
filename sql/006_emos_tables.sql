-- =====================================================================
-- EMOS 项目落地配置与经验回流（MMS/EMOS AI-native）
-- =====================================================================

CREATE TABLE IF NOT EXISTS meta_emos_project_type (
    项目类型ID     VARCHAR PRIMARY KEY,
    项目类型名称   VARCHAR NOT NULL,
    适用场景       VARCHAR,
    典型服务范围   VARCHAR,
    主要风险       VARCHAR,
    数据更新时间   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meta_emos_service_item (
    服务项ID       VARCHAR PRIMARY KEY,
    服务模块       VARCHAR NOT NULL,
    服务项名称     VARCHAR NOT NULL,
    说明           VARCHAR,
    是否必选       BOOLEAN DEFAULT FALSE,
    适用条件       VARCHAR,
    数据更新时间   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meta_emos_component (
    组件编号       VARCHAR PRIMARY KEY,
    组件名称       VARCHAR NOT NULL,
    组件类型       VARCHAR NOT NULL,
    来源项目       VARCHAR,
    适用项目类型   VARCHAR,
    对应服务项     VARCHAR,
    输入数据       VARCHAR,
    输出物         VARCHAR,
    关键变量       VARCHAR,
    风险点         VARCHAR,
    是否标准组件   BOOLEAN DEFAULT TRUE,
    成熟度         VARCHAR,
    AI摘要文件     VARCHAR,
    数据更新时间   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meta_emos_match_rule (
    规则ID         VARCHAR PRIMARY KEY,
    条件表达式     VARCHAR NOT NULL,
    推荐服务项     VARCHAR,
    推荐组件       VARCHAR,
    推荐理由       VARCHAR,
    关联风险       VARCHAR,
    优先级         INTEGER DEFAULT 100,
    数据更新时间   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meta_emos_knowledge_card (
    知识卡片编号   VARCHAR PRIMARY KEY,
    主题           VARCHAR NOT NULL,
    核心结论       VARCHAR NOT NULL,
    适用场景       VARCHAR,
    来源项目       VARCHAR,
    关联组件       VARCHAR,
    AI使用方式     VARCHAR,
    是否可复用     BOOLEAN DEFAULT TRUE,
    数据更新时间   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meta_emos_ai_prompt (
    PromptID       VARCHAR PRIMARY KEY,
    场景           VARCHAR NOT NULL,
    模板名称       VARCHAR NOT NULL,
    模板正文       VARCHAR NOT NULL,
    版本           VARCHAR DEFAULT 'V0.1',
    数据更新时间   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meta_emos_project_profile (
    画像ID         VARCHAR PRIMARY KEY,
    客户名称       VARCHAR NOT NULL,
    行业           VARCHAR,
    项目类型       VARCHAR,
    用户规模       VARCHAR,
    画像JSON       VARCHAR NOT NULL,
    创建人         VARCHAR,
    数据更新时间   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meta_emos_recommendation (
    推荐ID         VARCHAR PRIMARY KEY,
    画像ID         VARCHAR NOT NULL,
    推荐JSON       VARCHAR NOT NULL,
    数据更新时间   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meta_emos_ai_suggestion (
    记录ID         VARCHAR PRIMARY KEY,
    画像ID         VARCHAR,
    场景           VARCHAR NOT NULL,
    AI输出         VARCHAR,
    人工结论       VARCHAR,
    是否采纳       VARCHAR,
    是否回流       BOOLEAN DEFAULT FALSE,
    数据更新时间   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meta_emos_component_version (
    版本记录ID     VARCHAR PRIMARY KEY,
    组件编号       VARCHAR NOT NULL,
    原版本         VARCHAR,
    新版本         VARCHAR,
    更新原因       VARCHAR,
    来源项目       VARCHAR,
    数据更新时间   TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_emos_component_source ON meta_emos_component(来源项目);
CREATE INDEX IF NOT EXISTS idx_emos_profile_client ON meta_emos_project_profile(客户名称);
CREATE INDEX IF NOT EXISTS idx_emos_rec_profile ON meta_emos_recommendation(画像ID);
