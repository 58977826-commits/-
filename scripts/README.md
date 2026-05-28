# scripts/

辅助脚本，便于在真实账单到位前快速验证端到端管道。

## generate_mock_data.py

生成一个覆盖 12 种典型场景的 mock 数据集，写入 `data/raw/demo/mock/202604/...`。

包含的场景：

| 号码 | 场景 | 触发规则 |
|------|------|---------|
| P001 | 正常使用 + 标准套餐 | 无异常 |
| P002 | 零用量但仍计费 | Z02 |
| P003 | 超套预警（上网费多 94 元） | C05 |
| P004 | 高流量（80GB） + 高通话（120分钟） | H01 / H02 |
| P005 | 漫游使用 + 国际漫游费 | 漫游 |
| P006 | 增值业务异常（彩铃 33 元） | B05 |
| P007 | 离职员工但仍计费（E007 已离职） | 离职后计费 |
| P008 | 资产无对应人员 | 人员缺失 |
| P009 | 账单有号码但无资产 | 资产缺失 |
| P010 | 当月改号事件 | EV12 |
| P011 | 副卡申请事件 | EV12 |
| P012 | 离职归还 On-Boarding 未闭环 | EV10 |

运行：

```powershell
python scripts/generate_mock_data.py
tem run --客户 demo --项目 mock --账期 202604
streamlit run app/streamlit_app.py
```

## verify_results.py

在 mock 数据跑完 `tem run` 后，逐一校验 12 个场景是否被规则引擎正确识别。

```powershell
python scripts/verify_results.py
```

预期输出 `ALL PASS`。

## 真实 Excel 到位后的验证 Playbook

按下列顺序操作，每一步都需要保留下沉的样本以便回归：

1. **第一次预览** —— 不要立即导入。先用 Excel/Pandas 看一下真实 Excel 的列名清单：
   ```python
   import pandas as pd
   pd.read_excel("XXX.xlsx", nrows=0).columns.tolist()
   ```

2. **对照 ``src/tem/normalize/fields.py``** —— 若真实列名不在 ``SERVICE_NUMBER_ALIASES`` / ``TABLE_ALIASES`` 等字典里，**只需追加别名**，无需改主代码。

3. **小样本试跑** —— 先把 1 个客户 1 个项目 1 个账期的样本投递到 ``data/raw/...``，运行：
   ```powershell
   tem ingest --客户 X --项目 Y --账期 YYYYMM
   tem status
   ```
   核对各 raw_* 表行数是否符合预期。

4. **跑规则引擎** —— `tem build --客户 X --项目 Y --账期 YYYYMM`，然后到 DuckDB 查 `fact_tem_monthly` 验证：
   - `是否资产缺失` / `是否人员缺失` 数量是否合理（前期容易高）
   - `异常类型` 分布是否在预期范围内
   - 标准套餐金额是否如实读到（A06 风险点）

5. **看板复核** —— `streamlit run "app/诚翼畅联数据管理平台.py"`，选中刚跑通的客户/项目/账期，逐页核对指标。

6. **导出 Excel 回交** —— `tem export --客户 X --项目 Y --账期 YYYYMM`，把 `data/output/*_TEM月报.xlsx` 提交给运营经理做人工抽检。

7. **回归与字典扩展** —— 每次新月或新客户接入时，建议保留一份 `tests/data/<客户>_<账期>_minimal.xlsx` 作为单元测试基准。
