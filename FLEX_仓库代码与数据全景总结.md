# FLEX 仓库代码与数据全景总结

## 1. 仓库定位与总体结论

`FLEX` 是一个面向家庭能源系统与能源社区的三层建模框架，核心链路是：

1. `FLEX-Behavior` 生成住户行为画像（10分钟到小时级）。
2. `FLEX-Operation` 读取行为画像 + 建筑与设备参数，计算家庭能源系统运行（参考调度 + 成本优化调度）。
3. `FLEX-Community` 读取多个家庭的 Operation 输出，从聚合商视角计算 P2P 交易与电池套利收益。

该仓库代码结构清晰，主流程由 `tests/` 与 `projects/` 提供运行入口；数据库统一使用 SQLite，小时级结果主要以 parquet 存储。

---

## 2. 目录与职责

- `models/behavior`：行为模型（人->户）
- `models/operation`：家庭能源运行模型（Ref 规则模拟 + Opt 优化）
- `models/community`：能源社区聚合商模型
- `models/behavior/tus_process`：基于 TUS 原始调查数据生成 Markov 参数的预处理链
- `tests/behavior|operation|community`：三模型示例工程（含输入数据）
- `projects/zvei`：实际项目样例（输入结构与 operation test 基本一致）
- `plotters/*`：结果绘图
- `utils/*`：配置、数据库、时间函数、parquet、绘图基础工具
- `utils/tables.py`：输入/输出表名枚举（系统“数据字典主索引”）

---

## 3. 端到端数据流（Behavior -> Operation -> Community）

## 3.1 Behavior 阶段

输入（BehaviorScenario*、BehaviorParam*、BehaviorID*）
-> 输出：
- `BehaviorResult_PersonProfiles`（个人10分钟行为与用能）
- `BehaviorResult_HouseholdProfiles`（家庭小时负荷/热水/占用）

## 3.2 Operation 阶段

输入（OperationScenario + 各组件表 + 气象 + 价格 + 行为轮廓）
-> 每个 `ID_Scenario` 生成：
- Ref: `OperationResult_RefHour/Month/Year`
- Opt: `OperationResult_OptHour/Month/Year`

其中 `Hour` 通常为 parquet 文件（按场景拆分），`Month/Year` 写入 SQLite。

## 3.3 Community 阶段

输入来自 operation：
- `OperationScenario` -> `CommunityScenario_OperationScenario`
- `OperationResult_RefHour` -> `CommunityScenario_Household_RefHour`
- `OperationResult_RefYear` -> `CommunityScenario_Household_RefYear`
- 另有社区参数与价格

输出：
- `CommunityResult_AggregatorHour`
- `CommunityResult_AggregatorYear`

---

## 4. 三个模型的核心逻辑

## 4.1 FLEX-Behavior

核心文件：
- `models/behavior/main.py`
- `models/behavior/scenario.py`
- `models/behavior/person.py`
- `models/behavior/household.py`

逻辑分两步：

1. 个人画像生成 `gen_person_profiles`
- 读取 `BehaviorScenario_Person` 里的 `(id_person_type, id_teleworking_type)` 组合。
- 使用 Markov 参数（活动起始/转移/持续）按 10 分钟模拟全年活动序列。
- 把活动映射到技术触发，再映射为电器功率与热水需求。
- 加入地点逻辑（在家/外出）和 teleworking 概率。

2. 家庭画像聚合 `gen_household_profiles`
- 按 `BehaviorScenario_Household` 中的家庭类型组成（各人群数量）随机抽样个人画像并聚合。
- 将 10 分钟数据聚合到小时。
- 附加照明与基底电器负荷（modem/refrigerator）。

关键特征：
- 时间粒度：个人 10min，家庭 1h。
- 输出中的 `appliance_electricity`、`hot_water`、`occupancy` 直接供 Operation 阶段使用。

## 4.2 FLEX-Operation

核心文件：
- `models/operation/scenario.py`
- `models/operation/model_base.py`
- `models/operation/model_ref.py`
- `models/operation/model_opt.py`
- `models/operation/data_collector.py`
- `models/operation/main.py`

逻辑分三层：

1. 场景装配（`OperationScenario`）
- 从 `OperationScenario` 总表拿到每个组件 ID。
- 到各 `OperationScenario_Component_*` 表取对应参数并实例化组件对象。
- 注入外生时序：天气、PV发电、价格、行为负荷、占用温度边界、EV出行。

2. 物理与参数预计算（`OperationModel`）
- 5R1C 建筑热工模型：计算供暖/制冷需求、室温、热容温度。
- 供暖系统 COP、蓄热/热水箱参数、太阳得热、EV 约束上界等。

3. 两类求解
- Ref (`model_ref.py`)：规则驱动模拟（PV优先负荷，再电池，再热水箱，再上网）
- Opt (`model_opt.py`)：Pyomo 优化，目标最小化购电+燃料-上网收益

优化模型包含：
- 供暖水箱、热水箱能量平衡
- 5R1C 温度约束
- 热泵/锅炉互斥激活逻辑
- PV分配、固定电池、EV 充放电、购售电平衡

结果采集：
- 小时级按场景写 parquet，月/年写 SQLite
- 变量清单在 `models/operation/constants.py:OperationResultVar`

## 4.3 FLEX-Community

核心文件：
- `models/community/main.py`
- `models/community/scenario.py`
- `models/community/household.py`
- `models/community/model.py`
- `models/community/aggregator.py`
- `models/community/data_collector.py`

流程：

1. 场景建立
- 读取社区场景参数、社区电价、家庭映射表、家庭 ref 结果（小时+年）。
- 将每个 operation 场景包装成 `Household` 对象，提取小时负荷/PV/电池状态等。

2. 社区层聚合
- 计算社区总负荷、总PV、社区购电/上网、社区自发自用。
- P2P 交易量 = 社区PV内部消费 - 各户独立自消费。

3. 聚合商收益
- P2P 收益：`p2p_trading * (sell_price - buy_price)`
- 优化收益：一个简化电池套利模型（charge/discharge/soc + buy/sell 价格），目标最大化套利利润。

---

## 5. 输入数据逐表说明（含“是什么 + 在模型里做什么”）

下述说明以 `tests/*/input` 为主，`projects/zvei/input` 与 operation test 基本同构。

## 5.1 Behavior 输入表

### `BehaviorScenario_Person`
- 数据：人群类型与远程办公类型组合（6行，2列）。
- 作用：定义要生成哪些“个人画像原型”。

### `BehaviorScenario_Household`
- 数据：每种家庭类型中，不同人群/远程办公类型的人数配置（8行，6列）。
- 作用：将个人画像按家庭组成聚合成家庭画像。

### `BehaviorParam_Activity_TUSProfile`
- 数据：TUS 统计下各人群/日类型的 144 个10分钟活动标签序列（7176行，146列）。
- 作用：训练/抽样 Markov 链基础分布；也用于最常见活动替代规则。

### `BehaviorParam_Activity_TUSStart`
- 数据：各人群/日类型在 t1 的活动起始概率。
- 作用：每天活动链起点抽样。

### `BehaviorParam_Activity_ChangeProb`
- 数据：`(人群,日类型,时刻,上一个活动)->当前活动` 的转移概率。
- 作用：Markov 活动状态转移。

### `BehaviorParam_Activity_DurationProb`
- 数据：`(人群,日类型,时刻,活动)->持续时长` 的概率。
- 作用：决定活动片段长度（10分钟粒度）。

### `BehaviorParam_Activity_Location`
- 数据：活动 ID 到地点类型（在家/外出/二选一）的映射。
- 作用：生成在家占用与在家可用负荷。

### `BehaviorParam_TeleworkingProb`
- 数据：远程办公类型到在家办公概率。
- 作用：工作活动的地点判定。

### `BehaviorParam_Technology_TriggerProbability`
- 数据：活动触发技术的概率。
- 作用：活动 -> 技术设备使用抽样。

### `BehaviorParam_Technology_Power`
- 数据：各技术功率值。
- 作用：将技术触发转成电器负荷/热水需求。

### `BehaviorParam_Technology_Duration`
- 数据：各技术持续时长。
- 作用：负荷脉冲持续时间控制。

### `BehaviorID_Activity`
- 数据：活动 ID 与名称。
- 作用：语义映射 + 绘图标签。

### `BehaviorID_Technology`
- 数据：技术 ID 与名称。
- 作用：语义映射。

### `BehaviorID_PersonType`
- 数据：人群类型字典。
- 作用：输入定义层（当前仿真主逻辑主要按 ID 范围硬编码 1..4）。

### `BehaviorID_DayType`
- 数据：工作日/周末字典。
- 作用：输入定义层。

### `BehaviorID_Location`
- 数据：地点字典（outside/home/home_or_outside）。
- 作用：输入定义层。

### `BehaviorID_TeleworkingType`
- 数据：远程办公类型字典。
- 作用：输入定义层。

### `BehaviorID_HouseholdCompositionType`
- 数据：家庭构成类型字典。
- 作用：用于 `BehaviorScenario_Household` 语义标识；当前核心计算未直接读取该表。

## 5.2 Operation 输入表

### `OperationScenario`
- 数据：每个 `ID_Scenario` 绑定各组件 ID（建筑、锅炉、PV、电池、行为、价格等）。
- 作用：场景主索引，驱动组件参数拼装。

### `OperationScenario_Component_Building`
- 数据：建筑热工参数与住户参数（`Af/Hop/Hve/CM_factor/窗面积/供温/person_num/...`）。
- 作用：
  - 5R1C 热工方程参数；
  - 基础电器与热水总需求尺度（按人数）；
  - 温控、通风和电网边界基础。

### `OperationScenario_Component_Region`
- 数据：区域代码与年份。
- 作用：与天气/价格表耦合（当前主要用于元信息）。

### `OperationScenario_RegionWeather`
- 数据：8760小时天气与辐照、单位化PV发电曲线。
- 作用：外温、太阳得热、PV发电时序输入。

### `OperationScenario_Component_Boiler`
- 数据：供暖设备类型（Air_HP/gases/solids 等）、效率参数。
- 作用：决定热泵路径还是燃料锅炉路径；决定 COP/燃料转换。

### `OperationScenario_Component_SpaceHeatingTank`
- 数据：采暖水箱容积、温度上下限、损耗参数。
- 作用：供暖储能动态与约束。

### `OperationScenario_Component_HotWaterTank`
- 数据：生活热水箱容积、温度上下限、损耗参数。
- 作用：热水储能动态与约束。

### `OperationScenario_Component_SpaceCoolingTechnology`
- 数据：制冷效率与最大功率。
- 作用：是否允许制冷与制冷功率上界。

### `OperationScenario_Component_PV`
- 数据：PV 装机规模、朝向。
- 作用：把单位化 `pv_generation_*` 转成户级 PV 出力。

### `OperationScenario_Component_Battery`
- 数据：固定电池容量、充放电效率与功率上限。
- 作用：固定电池 SOC 与充放电约束。

### `OperationScenario_Component_Vehicle`
- 数据：EV 容量、能耗率、充放电效率、V2X开关、驾驶画像ID。
- 作用：构造 EV 需求与在家可充放约束。

### `OperationScenario_DrivingProfile_ParkingHome`
- 数据：8760小时在家停车状态曲线（按 profile ID 列）。
- 作用：EV 是否可充放电的时序开关。

### `OperationScenario_DrivingProfile_Distance`
- 数据：8760小时行驶距离曲线（按 profile ID 列）。
- 作用：EV 行驶耗电需求 `distance * consumption_rate`。

### `OperationScenario_Component_Behavior`
- 数据：在家/不在家温度上下限、遮阳触发阈值与降幅。
- 作用：室温舒适边界 + 太阳得热折减。

### `OperationScenario_BehaviorProfile`
- 数据：多种 demand profile type 的小时 `appliance/hot_water/occupancy/ventilation_supply_temperature`。
- 作用：
  - 作为行为形状输入，按建筑人数缩放成绝对负荷；
  - 生成动态室温约束与通风送风温度。

### `OperationScenario_Component_EnergyPrice`
- 数据：每个价格方案映射到 `id_electricity/id_feedin/id_gases/id_solids`。
- 作用：把场景价格ID映射到小时价格列。

### `OperationScenario_EnergyPrice`
- 数据：8760小时多能源价格列（`electricity_1`, `gases_1` ...）。
- 作用：购电/上网/燃料成本时序输入。

### `OperationScenario_Component_HeatingElement`
- 数据：电辅热功率与效率。
- 作用：热泵/锅炉不足时的补热通道与约束。

## 5.3 Community 输入表

### `CommunityScenario`
- 数据：社区场景参数（聚合商电池容量、效率、买卖价系数、是否可控住户电池等）。
- 作用：定义聚合商策略与优化边界。

### `CommunityScenario_EnergyPrice`
- 数据：社区电价与上网电价时序。
- 作用：P2P 定价与套利优化的 buy/sell 价格。

### `CommunityScenario_OperationScenario`
- 数据：社区内家庭对应的 operation 场景组件 ID。
- 作用：建立家庭集合与属性映射。

### `CommunityScenario_Household_RefHour`
- 数据：家庭级小时结果（PV/Load/Grid/Feed2Grid/BatSoC）。
- 作用：社区总负荷、总发电、P2P交易量、可控电池空间计算。

### `CommunityScenario_Household_RefYear`
- 数据：家庭年汇总结果。
- 作用：家庭年度成本等汇总信息输入（当前主要用于家庭对象赋值和扩展分析）。

### `CommunityScenario_Component_Battery`
- 数据：住户电池容量与效率参数字典。
- 作用：当“聚合商可控住户电池”开启时，构建可用总储能边界。

## 5.4 TUS 预处理输入（`models/behavior/tus_process/input`）

这些不是主运行必须输入，但用于再生成 Behavior 的 Markov 参数：

- `TUS_ActivityProfile`：原始活动日记（高维时段字段）
- `TUS_Persons` / `TUS_Households`：调查对象属性
- `Relation_TUSActivity`：原调查活动编码到模型活动编码映射
- `ID_Activity` / `ID_PersonType` / `ID_DayType`：标签字典

输出在 `tus_process/output` 形成：
- `BehaviorParam_Activity_TUSProfile`
- `BehaviorParam_Activity_ChangeProb`
- `BehaviorParam_Activity_DurationProb`
- `BehaviorParam_Activity_TUSStart`

---

## 6. 输出数据体系

### Behavior
- `BehaviorResult_PersonProfiles`（CSV + SQLite）
- `BehaviorResult_HouseholdProfiles`（CSV + SQLite）

### Operation
- 小时：`OperationResult_RefHour_S{ID}.parquet.gzip`、`OperationResult_OptHour_S{ID}.parquet.gzip`
- 月/年：`OperationResult_*Month`、`OperationResult_*Year`（SQLite）

### Community
- `CommunityResult_AggregatorHour`（SQLite）
- `CommunityResult_AggregatorYear`（SQLite）

---

## 7. 运行入口与推荐顺序

示例入口：
- Behavior：`tests/behavior/main.py`
- Operation：`tests/operation/main.py`
- Community：`tests/community/main.py`

推荐端到端顺序：
1. 跑 Behavior，得到家庭画像。
2. 生成或准备 Operation 的 `BehaviorProfile` 并跑 Operation（Ref/Opt）。
3. 将 Operation 结果拷贝/转换到 Community 输入，再跑 Community。

---

## 8. 代码实现层面的关键观察

1. 框架主线明确，`utils/tables.py` 统一了表命名，降低了 I/O 混乱风险。
2. Operation 的物理模型与优化模型分离（`model_base` 与 `model_opt`），可维护性较好。
3. Community 模型是在 Operation 结果之上的“聚合层”，复用了已有家庭结果，计算成本低。
4. `projects/zvei/input` 与 `tests/operation/input` 基本同构，可视为项目化数据副本。
5. 数据中存在一些“字段已存在但当前主逻辑未直接使用”的情况（如部分 ID 字典表、OperationScenario 里的 `Mode` 等）。

---

## 9. 一句话总结

这个仓库本质上是一个“从住户行为到家庭运行再到社区聚合”的分层能源建模流水线：Behavior 提供需求与占用行为，Operation 提供家庭能流与成本结果，Community 在此基础上评估聚合商的 P2P 与储能运营价值。
