# Operation 模型代码审计与重构计划（面向可读性、稳健性、效率）

## 0. 审计范围与当前基线

本次仅审计 `models/operation` 及其运行入口/数据基线，不修改代码。

已确认你的基线状态：

- 基线目录：`/Users/songminyu/GitHub/FLEX_cnb/projects/test_operation/output_benchmark`
- 当前包含：
  - `OperationResult_RefHour_S1.parquet.gzip`
  - `OperationResult_OptHour_S1.parquet.gzip`
  - `test_operation.sqlite`
- 输入场景表：`projects/test_operation/input/OperationScenario.xlsx`
  - sheet 顺序为 `['test', 'Sheet1', 'Sheet2', 'Sheet3']`
  - `test` sheet 仅 1 个 scenario
  - 由于 `pd.read_excel()` 默认读第一个 sheet，当前运行会读取 `test`

这意味着：后续重构后可直接用 `projects/test_operation/output` 与 `output_benchmark` 做一致性对比。

---

## 1. 代码审计结论（按优先级）

## P0（应先修，影响正确性/可恢复运行）

1. `run_operation_model` 的续跑清理逻辑存在确定性 bug
- 文件：`models/operation/main.py:102`
- 问题：`db.connection` 在 `DB` 类中不存在（应为 `db.engine` 或封装接口）。
- 影响：当触发 `align_progress()` 的删除逻辑时会报错，续跑不可用。

2. 反射式装配 + 缺失校验，错误信息不友好
- 文件：`models/operation/scenario.py:57-64`
- 问题：依赖 `OperationScenarioComponent.__dict__` 和动态属性名，无 schema 校验。
- 影响：列名错、ID不存在、重复行时容易在深处才报错，定位困难。

3. Ref 模型存在“先算后截断”的不透明补丁
- 文件：`models/operation/model_ref.py:502`
- 问题：`self.Q_DHWTank_bypass.clip(min=0)` 带 TODO 且原因未闭环。
- 影响：可能掩盖前序能量平衡或单位问题，影响可解释性与可信度。

## P1（高优，影响稳健性与维护成本）

4. 求解器硬编码为 gurobi
- 文件：`models/operation/model_opt.py:479`
- 问题：`pyo.SolverFactory("gurobi")` 写死。
- 影响：部署环境受限，无法无缝切换 HiGHS/CPLEX/CBC/GLPK。

5. 大量硬编码常量（`8760`、范围循环）
- 文件：`model_base.py` / `model_opt.py` / `data_collector.py` 多处
- 问题：对时间长度、年类型、输入维度不自适应。
- 影响：扩展到闰年/子年窗口/多时段时改动面大。

6. 运行时校验不足（输入列、单位、空值）
- 文件：`scenario.py` / `main.py`
- 问题：对关键列是否存在、是否全8760、ID是否可映射缺少显式校验。
- 影响：异常多数在中后段才暴露，排障成本高。

7. 配置与边界设置遍布多个 for 循环
- 文件：`model_opt.py` 中 `config_*` 系列
- 问题：逻辑重复、冗长；变量 fix/unfix/ub 的状态切换分散。
- 影响：可读性差、引入回归的概率高。

## P2（中优，影响效率与工程质量）

8. 参数灌入效率一般（Python 层 8760 循环赋值）
- 文件：`model_opt.py:563+`
- 问题：大量逐时赋值。
- 影响：单场景尚可，多场景时初始化开销明显。

9. DataCollector 以 `__dict__` + 枚举扫描提取结果，耦合较强
- 文件：`data_collector.py:105+`
- 问题：结果变量由字符串反射读取，缺类型约束。
- 影响：重命名变量易静默破坏输出。

10. 缺少“黄金基线回归测试”自动化脚本
- 现状：你已手工建立 `output_benchmark`，但还没有程序化比较工具。
- 影响：重构后难以快速、稳定判定“逻辑未伤”。

---

## 2. 重构目标与非目标

## 目标

1. 可读性：模块职责清晰、减少重复、关键逻辑可追踪。  
2. 稳健性：输入校验前置、错误信息可定位、续跑机制可用。  
3. 效率：降低初始化与 I/O 冗余开销。  
4. 可替换求解器：从架构上支持多 solver。

## 非目标（第一阶段）

1. 不改变模型数学逻辑（约束/目标/时序行为保持一致）。  
2. 不改动输入表格式。  
3. 不先追求“更优目标值”，先追求“结果一致”。

---

## 3. 分阶段重构计划

## 阶段 A：基线与测试护栏（先做）

1. 新增回归比较脚本（建议 `scripts/compare_operation_outputs.py`）
- 比较对象：
  - `output/OperationResult_RefHour_S1.parquet.gzip` vs benchmark
  - `output/OperationResult_OptHour_S1.parquet.gzip` vs benchmark
  - `output/test_operation.sqlite` vs benchmark sqlite 中关键表
- 比较策略：
  - 结构一致：文件存在、列名顺序、行数、dtypes
  - 数值一致：
    - 严格模式：逐元素完全相等（`==`）
    - 容差模式：`atol=1e-9`（只在跨求解器时启用）

2. 固化运行命令
- 运行入口：`python -m projects.test_operation.main`
- 运行后自动触发 compare 脚本并输出 PASS/FAIL。

交付标准：在“未改业务逻辑”前提下，严格模式 PASS。

## 阶段 B：稳定性修复（不改数学）

1. 修复 `align_progress` 续跑 bug（`db.connection`）
2. 加入输入校验层（建议 `operation/validation.py`）
- 校验时序表必须 8760 行
- 校验关键列存在（如价格列、驾驶画像列、行为 profile 列）
- 校验 `OperationScenario` 中所有 ID 都能映射到组件表
3. 统一异常类型与错误消息（包含 scenario_id、表名、列名）

交付标准：坏输入在前置阶段失败，报错可定位。

## 阶段 C：可读性与结构优化（不改数学）

1. 拆分 `model_opt.py`
- `opt_model_structure.py`（变量/约束定义）
- `opt_model_config.py`（参数灌入、边界切换）
- `opt_model_solve.py`（求解器调用）

2. 建立“变量组/约束组”命名规范
- 统一前缀（thermal_* / battery_* / ev_* / grid_*）

3. 将反射式数据提取改成显式映射表
- `RESULT_FIELDS = {...}`
- 避免 `__dict__` 隐式耦合

交付标准：单文件长度下降，关键函数复杂度下降，输出不变。

## 阶段 D：效率优化（不改数学）

1. 优化参数灌入
- 用批量字典或向量化方式替代重复 for 赋值（在 Pyomo 可行范围内）。
2. 减少重复 DataFrame 读取/转换
- 场景级缓存 + ndarray 复用。
3. 日志与 profile
- 增加计时点：场景装配、实例配置、求解、写盘。

交付标准：单场景总耗时下降（目标 10%-25%，视 solver 耗时占比）。

## 阶段 E：求解框架演进（Pyomo -> Linopy 可选）

先做“并行实现 + A/B 对比”，不直接替换线上主路径。

---

## 4. Linopy 迁移分析

## 4.1 为什么可考虑 Linopy

1. 表达方式更贴近向量化建模（xarray/numpy 维度友好）。  
2. 在大规模线性问题上，建模代码常比逐标量约束更简洁。  
3. 求解器选择更灵活（如 HiGHS/Gurobi/CPLEX 等，具体以 Linopy 支持为准）。

## 4.2 迁移收益

1. 约束可批量表达，代码长度有望明显下降。  
2. 减少 Python 层 8760 次循环构造约束的样板代码。  
3. 便于将来扩展到多维索引（场景 x 时段 x 技术）。

## 4.3 迁移成本/风险

1. 需要重写 `model_opt`（工作量最大）。  
2. 数值细节（变量边界、初值、容差、求解器参数）可能导致“非逐点完全一致”。  
3. 团队学习成本：Pyomo -> Linopy 的 API 与调试方式差异。  
4. 现有 DataCollector 与变量命名耦合，需一起改造。

## 4.4 适用性判断（对当前项目）

- 当前优化模型是线性连续模型为主，Linopy 技术上可承接。  
- 但短期目标是“重构不伤逻辑并通过 benchmark 全一致”，建议先做阶段 A-D，再开 Linopy 分支做 PoC。

---

## 5. 除 Linopy 外的选择

1. **保留 Pyomo（首选稳健路径）**
- 优点：现有代码可增量重构，风险最低。
- 可做：抽象 solver 工厂，支持 gurobi/highs/cplex/cbc。

2. **Pyomo + APPsi/持久化接口优化**
- 优点：在保留数学模型的同时提升求解集成与性能可控性。
- 成本：中等。

3. **gurobipy 直接建模**
- 优点：性能与控制力强。
- 缺点：强绑定 Gurobi，失去 solver 中立性，不符合你“可换 solver”的目标。

4. **CVXPY**
- 优点：建模清晰，求解器切换方便。
- 缺点：更偏凸优化抽象；对大规模工程 LP 的落地与性能未必优于 Pyomo/Linopy。

5. **PuLP / OR-Tools 线性求解器接口**
- 优点：上手快。
- 缺点：表达复杂能量系统模型时可维护性与扩展性通常不如 Pyomo/Linopy。

结论：
- 若目标是“短期稳妥 + 可多 solver”，优先 **Pyomo 重构**。
- 若目标是“中长期更向量化 + 便于后续扩展”，可在稳定后引入 **Linopy 并行实现**。

---

## 6. 建议执行顺序（与你的 benchmark 约束对齐）

1. 先实现阶段 A（自动对比护栏）。  
2. 执行阶段 B/C/D 的“无数学变更重构”，每一步都跑：
- `python -m projects.test_operation.main`
- compare `output` vs `output_benchmark`（严格模式）

3. 全部通过后，再开 `linopy` 分支做 PoC：
- 先对 scenario=1 跑通；
- 再比较 strict/atol 两套结果；
- 最后决定是否替换主实现。

---

## 7. 本次确认

我已经完成 Operation 代码审计，并形成这份可执行重构计划文档。  
下一步如你确认，我会按“阶段 A（基线比较脚本）”先落地，实现自动对比 `output` 与 `output_benchmark`。
