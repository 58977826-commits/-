-- =====================================================================
-- 应用登录账号（Streamlit 看板）
-- =====================================================================

CREATE TABLE IF NOT EXISTS meta_app_user (
    username       VARCHAR PRIMARY KEY,
    password_hash  VARCHAR NOT NULL,
    password_salt  VARCHAR NOT NULL,
    is_admin       BOOLEAN NOT NULL DEFAULT FALSE,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMP,
    updated_at     TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_meta_app_user_admin
  ON meta_app_user(is_admin);
