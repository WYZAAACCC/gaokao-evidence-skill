# Gaokao Real Evidence Advisor

## Description
证据驱动的高考志愿推荐系统。给定"学校+专业"，自动完成10+维度、**600+条搜索查询**的深度搜索，证据收集、交叉验证、画像报告生成。**全程由 Claude 自身完成——WebSearch 负责搜索，Claude 原生推理负责 Claim 提取和报告撰写，零外部 API 依赖，即插即用。**

## Triggers
- `/gaokao "学校名" "专业名"` 或 `/高考 "学校名" "专业名"`
- 用户问"XX学校XX专业怎么样""XX学校的XX专业值得报吗"
- 用户需要深度对比学校或专业

## ⚠️ 搜索强度选择（强制执行）

**在开始任何搜索之前，必须询问用户选择搜索强度。严禁自行决定降低搜索量。**

向用户展示以下三个选项：

```
请选择搜索强度：

🔥 高强度 (deep) — 完整 600+ 条查询，10维度全覆盖，适合最终决策
   · 社媒 130+ 条 · 录取 75 条 · 就业 75 条 · 其余维度各 50-60 条
   · 预计耗时: 40-60 分钟 · 报告: 20,000+ 字

⭐ 中强度 (standard) — 约 300 条核心查询，维度完整但深度适中
   · 社媒 60 条 · 录取 35 条 · 就业 35 条 · 其余维度各 20-30 条
   · 预计耗时: 20-30 分钟 · 报告: 10,000-15,000 字

💡 低强度 (quick) — 约 150 条重点查询，快速摸底
   · 社媒 30 条 · 录取 15 条 · 就业 15 条 · 其余维度各 10-15 条
   · 预计耗时: 10-15 分钟 · 报告: 5,000-8,000 字
```

**用户选择后，严格按照对应强度执行，不得自行增减。**

## 核心原则
- **证据优先**: 每个结论必须来自搜索结果，禁止编造
- **坦诚不足**: 搜索结果不足明确告知，不允许猜测填充
- **覆盖全面**: 必须覆盖全部10个维度，不得跳过任一维度
- **社媒重要**: 社媒反馈是最重要的信息来源之一，不可削减
- **强度锁定**: 用户选择的搜索强度即为硬性指标，Claude 不得以"效率""时间"或其他任何理由自行降级
- **持久执行**: 每批执行 8-10 条搜索，每 50 条保存中间结果，直到全部完成
- **Claude 原生分析**: 搜索完成后由 Claude 直接抽取 Claim、分析共识/争议、撰写报告。不依赖任何外部 LLM API

## Workflow

### Phase 0: 确认搜索强度（必须执行，不可跳过）

询问用户选择搜索强度（高/中/低），记录选择。**没有用户明确选择，不得开始搜索。**

### Phase 1: 按强度生成搜索查询

将下方所有查询模板中的 `{school}` 替换为学校名，`{major}` 替换为专业名。

| 强度 | 查询数量 | 选取规则 |
|------|---------|---------|
| 🔥 高 | 全部 600+ 条 | 逐条执行，一维不漏 |
| ⭐ 中 | ~300 条 | 优先执行标注 ⭐ 的查询（每个子节最重要的条目），确保10维度全覆盖 |
| 💡 低 | ~150 条 | 依次搜索各维度，当某维度已获取充足信息（≥15条有效结果）时跳到下一维度 |

**高强度下严禁跳过任何查询。中强度下必须覆盖全部10维度，每维度至少20条。低强度下必须覆盖全部10维度，每维度至少10条。**

### Phase 2: 分批搜索 + 增量 Claim 提取

使用 `WebSearch` 工具执行 **Phase 1 确定的所有查询**（数量由 Phase 0 的强度选择决定）。

**每批执行 8-10 条**，每批完成后：
1. 保存原始结果到 `reports/raw_search_{school}_{major}_batch{N}.json`
2. **立即从本批结果中提取关键 Claim**，追加到 `reports/claims_{school}_{major}.json`

**强制规则**：
- 必须执行完该强度下的全部查询，不得提前终止
- 即使某个维度看起来"信息已经足够"，也必须执行完该维度的所有查询
- 遇到 400 错误按内容安全过滤策略处理（跳过+换词），不减少剩余查询数量
- 每完成一批后报告进度："已完成 120/600，当前维度：就业质量"

Claim 提取格式：
```json
{
  "claim_text": "从搜索摘要中提炼的具体声明（1-2句话，不可编造）",
  "dimension": "admission|education|baoyan|employment|industry|lab|social|life|risk",
  "polarity": "positive|negative|neutral",
  "confidence": "high|medium|low",
  "source_url": "搜索结果URL",
  "source_title": "搜索结果标题"
}
```

### Phase 3: Claude 原生分析

所有批次完成后，基于 `reports/claims_{school}_{major}.json` 中的全部 Claim，执行以下分析：

#### 3.1 运行规则引擎（纯 Python，无需 API）
```bash
cd ~/.claude/skills/gaokao-evidence && python -c "
import json, sys
sys.path.insert(0, '.')
from packages.ranking.scoring import generate_consensus_analysis, analyze_risk_items, find_counter_evidence, compute_conclusion_confidence

with open('reports/claims_{school}_{major}.json', encoding='utf-8') as f:
    claims = json.load(f)

consensus = generate_consensus_analysis(claims)
risks = analyze_risk_items(claims)
counters = find_counter_evidence(claims)
dim_count = len(set(c.get('dimension','') for c in claims))
conf = compute_conclusion_confidence(len(claims), dim_count, has_official=True, has_social=True, has_counter_evidence=len(counters)>0)

print(json.dumps({'consensus': consensus, 'risks': risks, 'counters': len(counters), 'confidence': conf}, ensure_ascii=False, indent=2))
" > reports/analysis_{school}_{major}.json
```

#### 3.2 Claude 交叉验证
读取 `reports/claims_{school}_{major}.json` 和 `reports/analysis_{school}_{major}.json`，执行：

- **去重与合并**：同一事实的多个 Claim 合并，标注独立来源数量
- **共识/争议/孤证分类**：结合规则引擎输出，Claude 做语义级判断
- **反证核查**：对矛盾 Claim 对逐条判断可信度
- **缺失维度识别**：哪些维度 Claim 数量不足（<5条），标记为"数据缺失"
- **可信度校准**：综合来源权威性、时效性、独立来源数量，给出每条结论的可信度

#### 3.3 生成关键问答
基于 Claim 数据集，回答 5 个核心问题：
1. 该学校该专业总体值得报考吗？明确结论 + 置信度
2. 最大的优势和最大的风险分别是什么？
3. 什么样的学生适合/不适合？
4. 本科就业、考研、保研三条路径的概率和性价比？
5. 对普通家庭学生的性价比分析？

### Phase 4: Claude 撰写完整报告

按照下方 Output Format 结构，将 Phase 3 的分析结果撰写为完整报告，写入 `reports/{school}_{major}_报告.md`。

报告生成原则：
- 每个结论必须标注在 Phase 3 中确定的**可信度** + **证据来源 URL**
- 数值必须标注时间（如"2024届数据"）
- 不确定的数据用"数据缺失"明确标注，禁止编造
- 社媒反馈必须区分"共识"/"争议"/"孤证"
- 报告目标字数: **15,000-25,000 字**

---

## 搜索查询模板 (600+ queries)

> **使用说明**: 将 `{school}` 替换为目标学校全称（如"南京理工大学"），`{major}` 替换为目标专业全称（如"自动化"）。每个 `-` 开头的行是一条独立的 WebSearch 查询。

---

### 1. 院校真实情况 (50条)

#### 1.1 基本定位 (8条)
- `{school} 学校简介 历史 隶属 工信部 国防科工`
- `{school} 是211吗 是985吗 双一流 什么档次`
- `{school} 全国排名 2024 2025 软科 校友会 USNews`
- `{school} 国防七子 兵工七子 是什么 地位`
- `{school} 工信部直属 和教育部直属 区别 优势`
- `{school} 主管部门 国防科工局 工信部 背景`
- `{school} 创办历史 哈军工 分建 沿革`
- `{school} 校训 校风 军工文化 传统`

#### 1.2 综合实力 (8条)
- `{school} 科研经费 预算 2024 2025 全国排名`
- `{school} 院士数量 两院院士 全职 双聘`
- `{school} 国家级人才 杰青 长江学者 万人计划`
- `{school} 国家重点学科 一流学科 数量`
- `{school} ESI排名 前1% 前1‰ 学科`
- `{school} 国家自然科学基金 项目数 经费`
- `{school} 国家级科研平台 国家重点实验室 数量`
- `{school} 三大奖 国家自然科学奖 技术发明奖 科技进步奖`

#### 1.3 优势学科 (6条)
- `{school} 王牌专业 最强专业 有哪些 排名`
- `{school} 学科评估 第四轮 第五轮 A类 B类`
- `{school} 国家级一流本科专业 名单 多少个`
- `{school} 工程教育认证 专业 通过WA`
- `{school} 博士后流动站 博士点 硕士点 数量`
- `{school} 优势专业 和 北理 南航 哈工程 对比`

#### 1.4 校区与规模 (6条)
- `{school} 校区分布 有几个校区 都在哪`
- `{school} 南京校区 江阴校区 区别 哪个好`
- `{school} 校园面积 占地面积 多少亩`
- `{school} 在校学生 人数 本科生 研究生 比例`
- `{school} 师资规模 专任教师 多少 人`
- `{school} 男女比例 工科院校 男女比 多少`

#### 1.5 社会声誉 (7条)
- `{school} 毕业生 口碑 用人单位 评价 怎么样`
- `{school} 在211里 排第几 什么水平 中上 顶尖`
- `{school} 社会认可度 含金量 值不值得上`
- `{school} 和985比 差距 哪些985不如南理工`
- `{school} 考研 复试 歧视 双非 公平吗`
- `{school} 校招 企业 认可度 HR 怎么看`
- `{school} 长三角 认可度 江苏 上海 浙江 就业 口碑`

#### 1.6 发展动态 (5条)
- `{school} 最新 新闻 2025 发展 动态`
- `{school} 新校区 建设 规划 未来 发展`
- `{school} 学科建设 突破 新获批 平台`
- `{school} 经费 增长 预算 增加 趋势`
- `{school} 综合排名 上升 下降 趋势 2024 2025`

#### 1.7 国防特色 (5条)
- `{school} 军工 背景 国防 特色 优势 领域`
- `{school} 兵器 科学 技术 全国排名 第一`
- `{school} 军工项目 国防科研 经费 占比`
- `{school} 涉密 专业 哪些 就业 限制`
- `{school} 军民融合 产业化 成果 转化`

#### 1.8 入学体验 (5条)
- `{school} 开学典礼 军训 新生 感受 怎么样`
- `{school} 学术氛围 学风 严谨 还是 自由`
- `{school} 学校管理 行政 效率 官僚 吐槽`
- `{school} 奖助学金 助学贷款 困难补助 体系`
- `{school} 国际交流 交换生 出国机会 多不多`

---

### 2. 专业培养情况 (60条)

#### 2.1 学科实力 (8条)
- `{school} {major} 学科评估 第几轮 什么等级 A B C`
- `{school} {major} 全国排名 第几名 专业排名`
- `{school} {major} 是国家一流专业吗 国家特色专业`
- `{school} {major} 工程教育认证 通过了吗 WA`
- `{school} {major} 博士点 硕士点 博士后流动站 有吗`
- `{school} {major} 所属学院 什么学院 学院实力 怎么样`
- `{school} {major} 重点学科 省级 国家级`
- `{school} {major} 和清华 浙大 上交 这个专业比 差距 多大`

#### 2.2 课程体系 (10条)
- `{school} {major} 培养方案 课程设置 2024`
- `{school} {major} 核心课程 专业必修课 都学什么`
- `{school} {major} 大一 课程表 都上什么课 具体`
- `{school} {major} 大二 课程表 专业基础课 有哪些`
- `{school} {major} 大三 专业课 方向 分流 怎么选`
- `{school} {major} 大四 还有课吗 课多吗 实习`
- `{school} {major} 主要编程语言 学什么 C++ Python MATLAB`
- `{school} {major} 数学课 多不多 高数 线代 概率论 复变`
- `{school} {major} 物理课 大学物理 实验 难度`
- `{school} {major} 选修课 多不多 有什么 好选的`

#### 2.3 教学质量 (8条)
- `{school} {major} 老师 教学水平 怎么样 讲课好`
- `{school} {major} 最受欢迎的老师 推荐 哪位`
- `{school} {major} 哪门课最难 挂科率高 容易挂`
- `{school} {major} 期末考试 多吗 闭卷 开卷 考试难度`
- `{school} {major} 课程设计 课设 多不多 做什么`
- `{school} {major} 实验课 多吗 动手机会 操作`
- `{school} {major} 毕业设计 论文 什么 时候 开始 选题`
- `{school} {major} 教学设备 实验室 条件 怎么样 老旧`

#### 2.4 实践与实习 (8条)
- `{school} {major} 实习 安排 什么时候 去哪里实习`
- `{school} {major} 金工实习 电工实习 什么 时候 做什么`
- `{school} {major} 生产实习 毕业实习 有哪些 单位`
- `{school} {major} 实训 基地 校内 校外 有哪些`
- `{school} {major} 本科生 进实验室 做项目 机会 多吗`
- `{school} {major} 竞赛 参加 什么 电子设计大赛 智能车`
- `{school} {major} 大创 项目 申报 好立项吗`
- `{school} {major} 校企合作 实习基地 哪些 企业 合作`

#### 2.5 专业方向 (8条)
- `{school} {major} 专业方向 有哪些 分流方向`
- `{school} {major} 控制理论 方向 学什么 就业 如何`
- `{school} {major} 嵌入式 方向 学什么 就业 前景`
- `{school} {major} 机器人 方向 学什么 有哪些 课`
- `{school} {major} 人工智能 方向 课程 深度 怎么样`
- `{school} {major} 工业自动化 PLC 方向 就业 情况`
- `{school} {major} 飞行器控制 导航制导 军工方向`
- `{school} {major} 哪个方向最热门 最好就业`

#### 2.6 学习体验 (10条)
- `{school} {major} 课程 难不难 跟得上吗 压力 多大`
- `{school} {major} 挂科率 恐怖吗 补考 重修 好过吗`
- `{school} {major} 学风 卷不卷 同学 都 很努力 吗`
- `{school} {major} 学了这个专业 后悔 吗 知乎`
- `{school} {major} 大一大二 基础课 跟不上 怎么办`
- `{school} {major} 专业课 和 基础课 哪个更难`
- `{school} {major} 课表 满不满 一周 多少 节课`
- `{school} {major} 这个专业 适合 什么样的人 不适合 什么样`
- `{school} {major} 需要 提前学 什么 基础 编程`
- `{school} {major} 买了什么 教材 推荐 哪本 书`

#### 2.7 师资力量 (8条)
- `{school} 自动化学院 {major} 师资 教授 副教授 多少人`
- `{school} {major} 院士 长江学者 杰青 有哪些`
- `{school} {major} 导师 推荐 哪个 研究方向 好`
- `{school} {major} 哪些 老师 比较 坑 避雷`
- `{school} {major} 年轻老师 多不多 海归 比例`
- `{school} {major} 师生比 多少人 带多少学生`
- `{school} {major} 老师 负责任 吗 答疑 好找吗`
- `{school} {major} 辅导员 怎么样 关心 学生 吗`

---

### 3. 录取与风险 (75条)

#### 3.1 分数线-江苏省 (6条)
- `{school} {major} 江苏 录取分数线 2024 2023 2022`
- `{school} {major} 江苏 录取位次 最低 多少名`
- `{school} {major} 江苏 物理类 分数线 位次`
- `{school} {major} 江苏 鼎新班 录取分数 位次 2024`
- `{school} {major} 江苏 各专业 录取分数 对比`
- `{school} 江苏 投档线 2024 2023 2022 趋势`

#### 3.2 分数线-各省 (20条)
- `{school} {major} 浙江 录取分数线 位次 2024`
- `{school} {major} 安徽 录取分数线 位次 2024`
- `{school} {major} 河南 录取分数线 位次 2024`
- `{school} {major} 河北 录取分数线 位次 2024`
- `{school} {major} 山东 录取分数线 位次 2024`
- `{school} {major} 湖北 录取分数线 位次 2024`
- `{school} {major} 湖南 录取分数线 位次 2024`
- `{school} {major} 广东 录取分数线 位次 2024`
- `{school} {major} 四川 录取分数线 位次 2024`
- `{school} {major} 北京 录取分数线 位次 2024`
- `{school} {major} 上海 录取分数线 位次 2024`
- `{school} {major} 江西 录取分数线 位次 2024`
- `{school} {major} 福建 录取分数线 位次 2024`
- `{school} {major} 山西 录取分数线 位次 2024`
- `{school} {major} 陕西 录取分数线 位次 2024`
- `{school} {major} 重庆 录取分数线 位次 2024`
- `{school} {major} 辽宁 录取分数线 位次 2024`
- `{school} {major} 黑龙江 录取分数线 位次 2024`
- `{school} {major} 吉林 录取分数线 位次 2024`
- `{school} {major} 各省分数线 汇总 最低位次`

#### 3.3 招生计划 (8条)
- `{school} {major} 招生计划 2025 招多少人 扩招`
- `{school} {major} 招生人数 变化 趋势 扩招 缩招`
- `{school} {major} 2025 新增 多少人 扩招 120`
- `{school} {major} 各省 招生 名额 分配 多少个`
- `{school} {major} 大类招生 包含哪些 专业 怎么分`
- `{school} {major} 专业分流 什么时候 按什么 分`
- `{school} 全国 招生计划 2025 总人数`
- `{school} {major} 对江苏 招生 有倾斜吗 本地保护`

#### 3.4 报考要求 (6条)
- `{school} {major} 选科要求 物理 化学 必须选吗`
- `{school} {major} 体检要求 色盲 色弱 近视 限制`
- `{school} {major} 单科成绩 要求 数学 英语 最低分`
- `{school} {major} 提前批 和 普通批 区别 怎么选`
- `{school} {major} 国家专项 地方专项 高校专项 怎么报`
- `{school} {major} 中外合作 有吗 录取 分数 区别`

#### 3.5 特殊班级 (8条)
- `{school} 鼎新班 是什么 培养 模式 优势`
- `{school} 钱学森学院 怎么进 选拔 条件 2024`
- `{school} 钱学森班 保研率 培养 特色 学费`
- `{school} {major} 卓越工程师 班 怎么 进 有什么 好`
- `{school} {major} 创新班 实验班 和 普通班 区别`
- `{school} 大类招生 鼎新班 钱学森班 报考 顺序`
- `{school} {major} 是不是 有 特殊的班 或 计划 培养`
- `{school} 本硕博 贯通 培养 有吗 自动化 能吗`

#### 3.6 志愿策略 (8条)
- `{school} {major} 多少分 能上 报考 难度 分析`
- `{school} {major} 冲一冲 稳一稳 保一保 怎么 排`
- `{school} {major} 高考志愿 第几志愿 填 合适`
- `{school} {major} 录取概率 位次 比 学校 线 高多少`
- `{school} {major} 和 同分数段 其他 学校 怎么选`
- `{school} {major} 要不要 服从调剂 被调剂 风险`
- `{school} {major} 转专业 好转吗 条件 成功率 多少`
- `{school} {major} 大类招生 分流 能保证 去自动化 吗`

#### 3.7 录取趋势 (7条)
- `{school} 录取位次 趋势 2020 2021 2022 2023 2024`
- `{school} {major} 录取位次 上升 还是 下降 趋势`
- `{school} 各省 录取 趋势 越来越难 还是 容易`
- `{school} {major} 新高考 改革 影响 录取 位次 变化`
- `{school} {major} 2025 预计 录取 位次 预测`
- `{school} {major} 大小年 现象 有吗 波动 大吗`
- `{school} {major} 分数线 会降吗 什么 情况下 降`

#### 3.8 报考建议 (7条)
- `{school} {major} 值得报考吗 知乎 综合分析`
- `{school} {major} 录取了 值得去吗 还是复读`
- `{school} {major} 和复读 怎么选 能上 更好的 吗`
- `{school} {major} 二本分数 能上吗 捡漏 可能吗`
- `{school} {major} 保底 能保吗 垫一垫 稳不稳`
- `{school} {major} 家长 应该 怎么帮 孩子 选 建议`
- `{school} {major} 张雪峰 推荐 过吗 怎么说`

#### 3.9 转专业 (5条)
- `{school} 转专业 政策 2024 条件 难度`
- `{school} 转专业 成功率 多少人 成功`
- `{school} 从其他专业 转进 自动化 有多难`
- `{school} 从自动化 转到 计算机 电子 可能吗`
- `{school} 转专业 考试 面试 内容 怎么准备`

---

### 4. 保研升学 (60条)

#### 4.1 保研率与数据 (8条)
- `{school} {major} 保研率 多少 百分之几 2024`
- `{school} {major} 2025届 保研率 推免 多少人`
- `{school} 全校 保研率 推免 1085人 2024 2025`
- `{school} {major} 2023届 2022届 保研率 变化 趋势`
- `{school} {major} 保研率 在211里 什么水平 对比`
- `{school} {major} 保研率 比南航 比合工大 高还是低`
- `{school} {major} 实际保研率 和 官方 数据 一致吗`
- `{school} {major} 保研 名额 怎么分配 班级 年级`

#### 4.2 保研条件 (8条)
- `{school} {major} 保研条件 绩点 前百分之几`
- `{school} {major} 保研 看什么 成绩 竞赛 论文 专利`
- `{school} {major} 保研 加分项 哪些 竞赛 论文 加分`
- `{school} {major} 保研 需要 英语六级 多少分`
- `{school} {major} 保研 成绩 排名 需要 前多少`
- `{school} {major} 保研 名额 够吗 竞争 激烈吗`
- `{school} {major} 保研 边缘人 怎么办 还能保吗`
- `{school} {major} 挂科了 还能保研吗 有影响吗`

#### 4.3 保研去向 (10条)
- `{school} {major} 保研去向 哪些 学校 2024`
- `{school} {major} 保研 清华 自动化系 有人去吗 多少`
- `{school} {major} 保研 浙大 控制学院 每年多少人`
- `{school} {major} 保研 上交 自动化 每年多少人`
- `{school} {major} 保研 北航 西工大 哈工大 多少`
- `{school} {major} 保研 中科院 自动化所 计算所`
- `{school} {major} 保研 本校 比例 多少人留本校`
- `{school} {major} 保研 东南大学 同济 同济 华科`
- `{school} {major} 保研 外校 更好 还是本校`
- `{school} {major} 保研去向 晒 录取 offer 经验`

#### 4.4 保研策略 (8条)
- `{school} {major} 保研 夏令营 怎么报名 经验`
- `{school} {major} 保研 联系导师 什么时候 合适`
- `{school} {major} 保研 预推免 九推 经验`
- `{school} {major} 保研 面试 问什么 怎么准备`
- `{school} {major} 保研 个人陈述 简历 怎么写`
- `{school} {major} 保研 清华 自动化 难不难 经验`
- `{school} {major} 保研失败 了 怎么办 考研 来得及吗`
- `{school} {major} 保研 后 大四 做什么 提前 进组`

#### 4.5 考研情况 (8条)
- `{school} {major} 考研 本校 好考吗 复试 优势`
- `{school} {major} 考研 报录比 多少 竞争 激烈`
- `{school} {major} 考研 初试 科目 考什么 专业课`
- `{school} {major} 考研 复试 会刷人吗 歧视双非吗`
- `{school} {major} 考研 去外校 难吗 能考上吗`
- `{school} {major} 二战 的 人多吗 考研失败 怎么办`
- `{school} {major} 考研 还是 工作 怎么选 值不值`
- `{school} {major} 考研 清华 浙大 上交 有可能吗`

#### 4.6 深造率 (5条)
- `{school} {major} 深造率 升学率 多少 百分比`
- `{school} {major} 出国 留学 比例 哪些国家`
- `{school} {major} 直博 硕博连读 机会 多吗`
- `{school} {major} 读研 比例 趋势 越来越多吗`
- `{school} {major} 不读研 能 找到好工作吗`

#### 4.7 保研经验贴 (8条)
- `{school} {major} 保研 经验贴 知乎 全过程`
- `{school} {major} 保研 上岸 小红书 晒 offer`
- `{school} {major} 从{school}到清华 自动化 保研 经历`
- `{school} {major} 保研 边缘人 逆袭 成功 经验`
- `{school} {major} 保研 浙大 上交 中科院 面经`
- `{school} {major} GPA3.5 能保研吗 保研成功`
- `{school} {major} 没有竞赛 没有论文 能保研吗`
- `{school} {major} 保研拿了 哪些 offer 最终选了 哪里`

#### 4.8 出国深造 (5条)
- `{school} {major} 出国 申请 哪些 学校 什么专业`
- `{school} {major} 出国 比例 去美国 德国 日本 多吗`
- `{school} {major} 自动化 出国 受限吗 军工背景 影响`
- `{school} {major} 留学 回来 就业 有优势吗`
- `{school} {major} 交换生 短期出国 机会 有哪些`

---

### 5. 就业质量 (75条)

#### 5.1 就业率与数据 (8条)
- `{school} {major} 就业率 2024 数据 多少`
- `{school} {major} 本科 就业率 硕士 就业率 对比`
- `{school} {major} 就业质量报告 2024 2023 官方`
- `{school} 毕业生就业质量年度报告 PDF 2024`
- `{school} {major} 真实就业率 和官方数据差距 知乎`
- `{school} {major} 未就业 的 多少人 都去哪了`
- `{school} {major} 灵活就业 比例 高吗 水分`
- `{school} 就业率 全校 最高 的 专业 有哪些`

#### 5.2 薪资水平 (10条)
- `{school} {major} 平均薪资 年薪 月薪 起薪 2024`
- `{school} {major} 本科毕业 起薪 多少 一个月`
- `{school} {major} 硕士毕业 薪资 年薪 多少`
- `{school} {major} 博士毕业 年薪 多少 差距`
- `{school} {major} 毕业五年 薪资 十年 薪资 发展`
- `{school} {major} 不同城市 薪资 区别 北京 上海 深圳 南京`
- `{school} {major} 年终奖 多少 几个月工资`
- `{school} {major} 薪资 涨幅 每年 涨多少`
- `{school} {major} offer 薪资 晒 offer 三方 多少钱`
- `{school} {major} 和南航 合工大 比 薪资 谁更高`

#### 5.3 就业去向-军工 (8条)
- `{school} {major} 军工 央企 就业 哪些 单位`
- `{school} 中国兵器 录用 多少人 招聘`
- `{school} 中电科 航天科技 航天科工 录用`
- `{school} {major} 军工研究所 薪资 待遇 怎么样`
- `{school} {major} 中国兵器 214所 203所 怎么样`
- `{school} {major} 进 军工 央企 有编制吗 稳定吗`
- `{school} {major} 军工 跳槽 出来 好找工作吗`
- `{school} {major} 涉密 单位 影响 出国 跳槽 吗`

#### 5.4 就业去向-民企 (10条)
- `{school} {major} 校招 华为 录用 多少人 2024`
- `{school} {major} 中兴 录用 多少人 招聘`
- `{school} {major} 比亚迪 录用 薪资 待遇`
- `{school} {major} 大疆 蔚来 汇川 宁德时代 录用`
- `{school} {major} 互联网大厂 阿里 腾讯 百度 能去吗`
- `{school} {major} 海康 大华 宇视 安防 行业 就业`
- `{school} {major} 西门子 施耐德 ABB 外企 就业`
- `{school} {major} 去 车企 上汽 蔚来 比亚迪 理想 小鹏`
- `{school} {major} 私企 和 国企 怎么选 哪个好`
- `{school} {major} 民营企业 校招 名单 有哪些 企业来`

#### 5.5 就业地域 (8条)
- `{school} {major} 就业地域 长三角 比例 多少`
- `{school} {major} 留在 南京 的 多少 比例`
- `{school} {major} 去上海 深圳 广州 北京 的 多吗`
- `{school} {major} 去苏州 无锡 常州 杭州 多少`
- `{school} {major} 回老家 省会 的 多吗 好找工作吗`
- `{school} {major} 去武汉 成都 西安 合肥 的 多吗`
- `{school} {major} 不同地域 薪资 对比 差距大吗`
- `{school} {major} 毕业生 主要 流向 哪些 城市 TOP5`

#### 5.6 就业质量细节 (8条)
- `{school} {major} 五险一金 都有吗 交多少 公积金`
- `{school} {major} 包吃包住 吗 有 宿舍 吗`
- `{school} {major} 加班 多吗 996 吗 工作强度`
- `{school} {major} 稳定性 裁员 应届生 试用期`
- `{school} {major} 工作环境 工厂 还是 办公室`
- `{school} {major} 出差 多不多 驻外 项目`
- `{school} {major} 晋升 空间 天花板 发展路径`
- `{school} {major} 签约 违约金 多少 毁约 容易吗`

#### 5.7 实习与秋招 (8条)
- `{school} {major} 秋招 什么时候 开始 准备什么`
- `{school} {major} 春招 机会 还多吗 找不到 怎么办`
- `{school} {major} 实习 怎么找 什么时候 开始 实习`
- `{school} {major} 大厂实习 好找吗 有内推吗`
- `{school} {major} 暑期实习 寒假实习 经验`
- `{school} 校园招聘会 哪些 企业 来 2024`
- `{school} {major} 简历 怎么写 项目经验 重要吗`
- `{school} {major} 面试 都问 什么 技术面 HR面`

#### 5.8 长线发展 (7条)
- `{school} {major} 毕业三年 后 现在 在做什么 知乎`
- `{school} {major} 毕业五年 后 年薪 多少 发展 如何`
- `{school} {major} 转行 的 多吗 都转去 做什么`
- `{school} {major} 考公 的 多吗 好考吗 岗位多吗`
- `{school} {major} 进体制内 容易吗 选调 生 有吗`
- `{school} {major} 创业 的 有吗 成功 案例`
- `{school} {major} 三十五岁 后 职业 发展 怎么样`

#### 5.9 就业对比 (8条)
- `{school} {major} 本科就业 vs 硕士就业 差距多大`
- `{school} {major} 技术岗 vs 非技术岗 薪资 差距`
- `{school} {major} 研发岗 vs 技术支持 哪个 发展好`
- `{school} {major} 军工 vs 民企 薪资对比 长远看`
- `{school} {major} 国企 vs 私企 哪个 更适合`
- `{school} {major} 读研 三年 和 工作 三年 哪个值`
- `{school} {major} 就业 最好 的 方向 是哪个`
- `{school} {major} 最差 的 出路 是什么 有什么选择`

---

### 6. 行业趋势 (40条)

#### 6.1 行业前景 (8条)
- `自动化 专业 就业前景 2025 趋势 分析`
- `自动化 行业 未来十年 发展 趋势 预测`
- `智能制造 2025 工业4.0 对自动化 人才需求`
- `自动化 会被AI替代吗 人工智能 冲击`
- `自动化 工程师 三十岁 四十岁 职业发展`
- `自动化 岗位 需求 增长 还是 下降 2025`
- `自动化 传统方向 和 新兴方向 前景 对比`
- `自动化 人才 缺口 多大 2025 就业市场`

#### 6.2 细分领域 (8条)
- `工业自动化 PLC 工程师 前景 薪资 2025`
- `机器人 工程师 薪资 前景 2025 中国`
- `自动驾驶 感知 控制 规划 就业 前景 2025`
- `嵌入式开发 前景 薪资 2025 还会火吗`
- `机器视觉 就业 前景 薪资 2025`
- `新能源 自动化 岗位 风电 光伏 储能 就业`
- `半导体 自动化 设备 就业 前景`
- `低空经济 无人机 飞行器控制 前景 2025`

#### 6.3 薪资对比 (6条)
- `自动化 应届生 薪资 2024 华为 比亚迪 大疆`
- `自动化 和计算机 薪资对比 差距 多大 2024`
- `自动化 硕士 年薪 行业 平均 2024`
- `自动化 不同行业 薪资 排行 军工 互联网 汽车`
- `自动化 和 电子信息 和 电气 薪资 对比`
- `自动化 毕业 五年 十年 薪资 天花板`

#### 6.4 考研vs就业 (5条)
- `自动化 考研 还是 直接就业 怎么选 2025`
- `自动化 考研后 薪资提升 幅度 多少`
- `自动化 读研 三年 值得吗 ROI分析`
- `自动化 本科 好找工作吗 还是必须读研`
- `自动化 考研 竞争 多激烈 报录比 2025`

#### 6.5 行业转型 (5条)
- `自动化 转 计算机 AI 容易吗 怎么转`
- `自动化 转 金融 量化 有可能吗 如何`
- `自动化 转 产品经理 技术管理 路径`
- `自动化 考公 考编 有哪些 岗位 对口`
- `自动化 创业 方向 做什么 有机会`

#### 6.6 政策与趋势 (4条)
- `中国制造2025 智能制造 政策 对自动化 利好`
- `新质生产力 自动化 人工智能 政策 导向`
- `工业自动化 国产替代 机会 2025`
- `全球 自动化 趋势 德国 日本 对比 中国`

#### 6.7 具体企业薪资 (4条)
- `华为 自动化 岗位 薪资 校招 2024 2025`
- `比亚迪 自动化 薪资 等级 F类 本科 硕士`
- `大疆 嵌入式 控制算法 薪资 校招 2024`
- `西门子 ABB 施耐德 应届生 薪资 2024 中国`

---

### 7. 实验室与科研 (35条)

#### 7.1 科研平台 (8条)
- `{school} {major} 实验室 重点实验室 国家级 省部级`
- `{school} 瞬态物理 国家重点实验室 自动化 参与`
- `{school} {major} 科研平台 有哪些 实验室 中心`
- `{school} {major} 实验设备 先进吗 条件 怎么样`
- `{school} {major} 实验室 面积 建设 投入多少`
- `{school} {major} 军工 实验室 民口 实验室 都有吗`
- `{school} {major} 和 其他学校 实验室 条件 对比`
- `{school} {major} 大数据 人工智能 机器人 实验室 新建`

#### 7.2 研究方向 (8条)
- `{school} {major} 研究方向 有哪些 课题组 做什么`
- `{school} {major} 军工 方向 武器 系统 火控 导航`
- `{school} {major} 控制理论 非线性 鲁棒 自适应`
- `{school} {major} 机器人 无人系统 智能车 方向`
- `{school} {major} 计算机视觉 模式识别 深度学习`
- `{school} {major} 导航 制导 控制 飞行器 方向`
- `{school} {major} 智能电网 电力系统 新能源 方向`
- `{school} {major} 哪个 方向 最 强 最有 特色`

#### 7.3 导师选择 (6条)
- `{school} {major} 导师 推荐 哪个好 知乎 经验`
- `{school} {major} 导师 避雷 哪些 比较坑`
- `{school} {major} 导师 学生 评价 口碑`
- `{school} {major} 年轻导师 还是 大牛导师 怎么选`
- `{school} {major} 导师 项目多 经费充足 吗`
- `{school} {major} 导师 放实习吗 管得严吗`

#### 7.4 本科生科研 (7条)
- `{school} {major} 本科生 进实验室 什么时候 好`
- `{school} {major} 本科生 科研 发论文 可能性`
- `{school} {major} 大创 科研训练 怎么做 选题`
- `{school} {major} 本科生 参与 军工 项目 能吗`
- `{school} {major} 竞赛 挑战杯 互联网+ 电子设计`
- `{school} {major} 本科生 做科研 影响 学习成绩 吗`
- `{school} {major} 科研 和 就业 怎么 平衡`

#### 7.5 科研氛围 (6条)
- `{school} {major} 科研氛围 学术氛围 浓厚吗`
- `{school} {major} 学术报告 讲座 多吗 学术交流`
- `{school} {major} 研究生 待遇 助学金 多少`
- `{school} {major} 发论文 要求 毕业 条件`
- `{school} {major} 硕士 直博 要求 条件`
- `{school} {major} 博士生 毕业 去向 高校 还是 企业`

---

### 8. ★社媒真实反馈 (130条 — 最重要!)

#### 8.1 知乎-就读体验 (18条)
- `{school} {major} 知乎 就读体验 怎么样`
- `{school} {major} 知乎 值得读吗 深度分析`
- `{school} {major} 知乎 第一天 入学 什么感受`
- `{school} {major} 知乎 大一 新生 应该 准备什么`
- `{school} {major} 知乎 如果重来 还会选 这个专业吗`
- `{school} {major} 知乎 我后悔 选择 这个 学校 专业`
- `{school} {major} 知乎 过来人 忠告 建议 踩坑`
- `{school} {major} 知乎 学了四年 最大的收获`
- `{school} {major} 知乎 大学四年 怎么规划 经验`
- `{school} {major} 知乎 这个专业 让我 最满意 的地方`
- `{school} {major} 知乎 这个专业 让我 最不满意 的地方`
- `{school} {major} 知乎 在{school}学自动化 是怎样的体验`
- `{school} {major} 知乎 我为什么 退学 复读`
- `{school} {major} 知乎 如果当时 选了 XX 现在 会更好吗`
- `{school} {major} 知乎 高中同学 vs 大学同学 发展 对比`
- `{school} {major} 知乎 父母 让我 选这个 专业 对吗`
- `{school} {major} 知乎 普通家庭 农村学生 读这个 合适吗`
- `{school} {major} 知乎 女生 读自动化 是怎样 体验`

#### 8.2 知乎-就业与薪资 (12条)
- `{school} {major} 知乎 就业 真实 情况 怎么样`
- `{school} {major} 知乎 2024 就业 难吗 秋招`
- `{school} {major} 知乎 找工作 面经 分享`
- `{school} {major} 知乎 去了 什么 公司 做什么`
- `{school} {major} 知乎 第一份工作 薪资 多少钱`
- `{school} {major} 知乎 毕业三年 现状 发展`
- `{school} {major} 知乎 转行 了 吗 做什么 去了`
- `{school} {major} 知乎 本科就业 和 硕士就业 差异`
- `{school} {major} 知乎 自动化 就业 方向 选择 哪个好`
- `{school} {major} 知乎 军工 出来 好 找工作吗`
- `{school} {major} 知乎 丢掉 了应届生 身份 怎么办`
- `{school} {major} 知乎 考研失败 春招 还 有 机会吗`

#### 8.3 知乎-学业与课程 (10条)
- `{school} {major} 知乎 课程 难吗 挂科`
- `{school} {major} 知乎 考试 周 什么 感受`
- `{school} {major} 知乎 哪门课 最 难 怎么 过`
- `{school} {major} 知乎 学习 资料 推荐 教材`
- `{school} {major} 知乎 考了 多少 分 GPA 怎么 算`
- `{school} {major} 知乎 学习 方法 怎么 高效 学`
- `{school} {major} 知乎 要不要 翘课 自学`
- `{school} {major} 知乎 买了 什么 电脑 配置`
- `{school} {major} 知乎 软件 推荐 MATLAB Python`
- `{school} {major} 知乎 竞赛 经历 电子设计 智能车`

#### 8.4 知乎-保研考研 (8条)
- `{school} {major} 知乎 保研 经历 分享 全过程`
- `{school} {major} 知乎 保研 失败 怎么办`
- `{school} {major} 知乎 考研 本校 还是 外校`
- `{school} {major} 知乎 考研 准备 多久 每天学多久`
- `{school} {major} 知乎 保研 夏令营 面经`
- `{school} {major} 知乎 保研外校 和保本校 怎么选`
- `{school} {major} 知乎 双非 考研 南理工 歧视吗`
- `{school} {major} 知乎 二战 考研 还 是 工作`

#### 8.5 知乎-劝退与风险 (8条)
- `{school} {major} 知乎 劝退 不要报 原因`
- `{school} {major} 知乎 这个专业 的 缺点`
- `{school} {major} 知乎 为什么不建议 报这个专业`
- `{school} {major} 知乎 最坑 的 地方`
- `{school} {major} 知乎 避雷 什么 人 千万别 来`
- `{school} {major} 知乎 后悔 报这个 原因`
- `{school} {major} 知乎 天坑 专业 是 天坑吗`
- `{school} {major} 知乎 毕业 找不到 工作 真实 吗`

#### 8.6 知乎-对比 (6条)
- `{school} {major} 知乎 和南航比 哪个好`
- `{school} {major} 知乎 和合工大 自动化 怎么选`
- `{school} {major} 知乎 和东南大学 自动化 差距 多大`
- `{school} {major} 知乎 和北理工 南理工 自动化 哪个更强`
- `{school} {major} 知乎 和哈工程比 自动化 谁好`
- `{school} {major} 知乎 同分数段 有什么 替代 选择`

#### 8.7 贴吧 (12条)
- `{school} {major} 贴吧 怎么样 真实 评价`
- `{school} 贴吧 新生 入学 要注意什么`
- `{school} 贴吧 食堂 哪个窗口 好吃`
- `{school} 贴吧 宿舍 哪个 楼 好 选宿舍`
- `{school} 贴吧 军训 水吗 累不累 准备什么`
- `{school} 贴吧 学长学姐 对新生 有什么建议`
- `{school} 贴吧 考证 报班 有必要吗`
- `{school} 贴吧 找对象 好找吗 男女比例 恋爱`
- `{school} 贴吧 有没有什么 兼职 可以做`
- `{school} 贴吧 跳蚤市场 二手 便宜`
- `{school} 贴吧 外卖 推荐 哪家好`
- `{school} 贴吧 社团 推荐 哪个 有意思`

#### 8.8 小红书 (14条)
- `{school} {major} 小红书 真实 体验 分享`
- `{school} {major} 小红书 录取 通知书 晒`
- `{school} {major} 小红书 考研 上岸 经验`
- `{school} {major} 小红书 保研 成功 经验`
- `{school} {major} 小红书 offer 晒 三方 签约`
- `{school} {major} 小红书 毕业 毕业照`
- `{school} {major} 小红书 宿舍 好物 推荐`
- `{school} 小红书 校园 环境 打卡 风景`
- `{school} 小红书 食堂 美食 推荐`
- `{school} {major} 小红书 实习 vlog 上班日常`
- `{school} {major} 小红书 考试周 通宵 自习`
- `{school} {major} 小红书 省钱 技巧 生活费 多少`
- `{school} {major} 小红书 考研 失败 找 工作`
- `{school} {major} 小红书 国奖 获得者 经验`

#### 8.9 B站 (10条)
- `{school} {major} B站 介绍 评价 探校`
- `{school} B站 校园 环境 寝室 食堂 vlog`
- `{school} {major} B站 课程 讲解 网课 资源`
- `{school} {major} B站 毕业 设计 展示`
- `{school} B站 新生 一定要知道的 事`
- `{school} {major} B站 大一到大四 变化 记录`
- `{school} {major} B站 就业 年薪 晒 offer`
- `{school} {major} B站 考研 复习 经验`
- `{school} B站 我为什么选择 这所 学校`
- `{school} {major} B站 避雷 劝退 吐槽`

#### 8.10 微博/抖音/综合 (8条)
- `{school} {major} 微博 超话 讨论 怎么样`
- `{school} 微博 最新 动态 新闻 讨论`
- `{school} {major} 抖音 探校 视频 真实`
- `{school} {major} 抖音 学长 学姐 有什么 建议`
- `{school} {major} 在校生 评价 好与不好 NGA`
- `{school} {major} 过来人 经验 忠告 建议 志愿`
- `{school} {major} 真实口碑 到底好不好 学生评价`
- `{school} {major} 什么 样 的 人 适合 什么 不适合`

#### 8.11 深度追问 (12条)
- `{school} {major} 读了这个专业 最大的改变是什么`
- `{school} {major} 如果高中 知道这些 还会选吗`
- `{school} {major} 哪些人 特别 适合 来 哪些 千万别来`
- `{school} {major} 这个专业 能 改变命运吗 对 普通家庭`
- `{school} {major} 学生 自杀 心理健康 压力`
- `{school} {major} 最 让人 崩溃 的 时刻`
- `{school} {major} 最 让人 骄傲 的 时刻`
- `{school} {major} 毕业十年后 的看法 回访`
- `{school} {major} 给 学弟学妹 的一封信`
- `{school} {major} 父母 不理解 这个专业 怎么办`
- `{school} {major} 选 这个专业 亏了吗 还是赚了`
- `{school} {major} 如果 给志愿填报 打一个分数 几分`

#### 8.12 特定平台深度 (12条)
- `{school} {major} site:zhihu.com 自动化 怎么样 评价`
- `{school} {major} site:douban.com 就读 体验`
- `{school} site:xiaohongshu.com 南理工 自动化`
- `{school} {major} site:csdn.net 课程 学习 经验`
- `{school} {major} site:jianshu.com 就读 体验`
- `{school} {major} site:zhihu.com 就业 薪资 offer`
- `{school} {major} site:zhihu.com 考研 保研 经验 2024`
- `{school} {major} site:zhihu.com 劝退 避雷 后悔`
- `{school} {major} site:zhihu.com 课程 考试 难度 挂科`
- `{school} {major} site:zhihu.com 宿舍 食堂 校园 生活`
- `{school} {major} site:zhihu.com 实验室 导师 科研`
- `{school} {major} site:zhihu.com 转专业 经验`

---

### 9. 校园生活 (60条)

#### 9.1 宿舍条件 (10条)
- `{school} 宿舍条件 几人间 上床下桌 空调`
- `{school} 宿舍 有独卫吗 阳台 热水 淋浴`
- `{school} 南区 宿舍 北区 宿舍 哪个好`
- `{school} 最好的宿舍 是什么 楼 怎么选`
- `{school} 最差 的宿舍 是哪个 吐槽`
- `{school} 宿舍 限电 多少W 能 用什么 电器`
- `{school} 宿舍 网络 校园网 速度 怎么样`
- `{school} 宿舍 卫生 检查 查寝 频率 严吗`
- `{school} 宿舍 收费 一年 多少钱 空调费`
- `{school} 可以在外面 租房 吗 什么时候可以`

#### 9.2 食堂饮食 (8条)
- `{school} 食堂 好吃吗 哪个食堂 最好吃`
- `{school} 食堂 价格 贵不贵 一个月 伙食费`
- `{school} 食堂 窗口 推荐 什么 好吃`
- `{school} 食堂 最难吃 的 避雷 吐槽`
- `{school} 清真食堂 有吗 少数民族 吃饭`
- `{school} 外卖 方便吗 能送进 学校吗`
- `{school} 周边 小吃 有什么 推荐`
- `{school} 食堂 几点 开门 晚上 有夜宵吗`

#### 9.3 校园环境 (8条)
- `{school} 校园 环境 怎么样 漂亮吗 紫金山`
- `{school} 校园 大不大 走路 多久 需要 骑车`
- `{school} 图书馆 怎么样 座位 够吗 占座`
- `{school} 自习室 哪里 有 可以 通宵吗`
- `{school} 教室 有 空调吗 夏天 热不热`
- `{school} 体育场 操场 体育馆 条件`
- `{school} 游泳馆 有吗 健身房 有吗`
- `{school} 春天 樱花 秋天 银杏 有没有 美景`

#### 9.4 地理位置 (6条)
- `{school} 地理位置 交通 方便吗 几号线 地铁`
- `{school} 离市中心 多远 逛街 方便吗`
- `{school} 周边 有什么 商场 购物 电影院`
- `{school} 离高铁站 多远 回家 方便吗`
- `{school} 在市区 还是 郊区 偏僻吗`
- `{school} 周边 租房 价格 多少钱`

#### 9.5 管理制度 (8条)
- `{school} 大一 管理 严格 早晚自习 有吗`
- `{school} 军训 多久 什么 时候 严格吗`
- `{school} 门禁 几点 能 出去 吗 晚归`
- `{school} 晚上 熄灯 断网 吗 几点`
- `{school} 辅导员 管得多吗 请假 好请吗`
- `{school} 行政 办事 效率 怎么样 吐槽`
- `{school} 校风 严谨 军工 特色 具体 体现`
- `{school} 和普通 综合大学 比 管理 差异`

#### 9.6 课余生活 (6条)
- `{school} 社团 有哪些 推荐 哪个 有意思`
- `{school} 运动会 文艺晚会 活动 多吗`
- `{school} 可以 做兼职 吗 校内岗位`
- `{school} 志愿者 活动 社会实践 多吗`
- `{school} 学生组织 学生会 团委 社团 联合会`
- `{school} 周末 去哪玩 南京 周边 一日游`

#### 9.7 费用 (6条)
- `{school} 学费 一年 多少钱 自动化 专业`
- `{school} 住宿费 一年 多少 元`
- `{school} 生活费 一个月 大概 多少 够用`
- `{school} 教材费 医保费 其他 杂费`
- `{school} 奖助学金 助学金 能拿多少`
- `{school} 四年 大学 总共 花费 多少钱`

#### 9.8 气候与环境 (4条)
- `南京 气候 怎么样 夏天 热不热 冬天 冷不冷`
- `南京 梅雨季 潮湿 适应吗 北方人`
- `南京 空气质量 雾霾 严重吗`
- `南京 生活成本 怎么样 一线城市 还是 二线`

#### 9.9 校园心理 (4条)
- `{school} 心理 健康 咨询中心 条件 怎么样`
- `{school} 学生 压力大 吗 焦虑 普遍 吗`
- `{school} 有 心理 问题 怎么办 求助 渠道`
- `{school} 校园 氛围 压抑 还是 轻松 评价`

---

### 10. 风险与推荐 (50条)

#### 10.1 风险分析 (10条)
- `{school} {major} 最大的坑 是什么 需要注意`
- `{school} {major} 为什么有人劝退 真实原因`
- `{school} {major} 不适合 什么人 什么样的人不该来`
- `{school} {major} 被调剂 来 了 怎么办 怎么学`
- `{school} {major} 毕不了业 的 多吗 什么原因`
- `{school} {major} 延毕 正常吗 多少比例`
- `{school} {major} 心理健康 跳楼 自杀 有没有`
- `{school} {major} 毕业 即失业 的 多不多`
- `{school} {major} 换专业 转行 了 的 比例`
- `{school} {major} 哪些方向 是 天坑 不能选`

#### 10.2 决策分析 (8条)
- `{school} {major} 到底值不值得报 结论 知乎`
- `{school} {major} 报考 前 一定要知道的 事`
- `{school} {major} 如果 回到高考那年 会选 吗`
- `{school} {major} 这个专业 的 性价比 分析`
- `{school} {major} 普通家庭 农村家庭 值得读吗`
- `{school} {major} 女生适合吗 就业 歧视 有吗`
- `{school} {major} 文科 转 工科 能读自动化吗`
- `{school} {major} 分数 刚好 够 要冲吗`

#### 10.3 对比分析 (8条)
- `{school} {major} 和 南航 自动化 哪个好 全维度对比`
- `{school} {major} 和 南京邮电 自动化 怎么选`
- `{school} {major} 和 河海大学 自动化 怎么选`
- `{school} {major} 和 合肥工业大学 自动化 怎么选`
- `{school} {major} 和 哈工程 自动化 哪个好`
- `{school} {major} 和 武汉理工大学 自动化 对比`
- `{school} {major} 和 西南交大 自动化 对比`
- `{school} {major} 和 华东理工 自动化 选哪个`

#### 10.4 报考建议 (8条)
- `{school} {major} 高考 志愿填报 建议 攻略`
- `{school} {major} 冲稳保 怎么填 志愿 排序`
- `{school} {major} 要不要 放第一志愿 还是 后面`
- `{school} {major} 分数 不够 好 专业 怎么选`
- `{school} {major} 大类招生 怎么选 小专业`
- `{school} {major} 学校重要 还是 专业重要 案例`
- `{school} {major} 高考 失利 差几分 能去 更好的吗`
- `{school} {major} 填报 志愿 最容易忽略的 问题`

#### 10.5 家长视角 (5条)
- `{school} {major} 家长 应该 怎么帮孩子 选`
- `{school} {major} 家长 不同意 选这个 专业 怎么办`
- `{school} {major} 家长 眼中 的 南理工 自动化 看法`
- `{school} {major} 家庭 经济一般 供得起吗`
- `{school} {major} 让孩子 一个人 去外省 读 放心吗`

#### 10.6 反事实推理 (5条)
- `{school} {major} 去了 比这个 更差 的 学校 现在呢`
- `{school} {major} 去了 比这个 更好 的 学校 现在呢`
- `{school} {major} 读了 这个专业 vs 读了计算机 对比`
- `{school} {major} 没有上这个 学校 去了 双非 结局 不一样`
- `{school} {major} 如果选了 南航 自动化 会不会 更好`

#### 10.7 最终判断 (6条)
- `{school} {major} 一句话 总结 值不值得 报考`
- `{school} {major} 综合评分 打几分 满分十分`
- `{school} {major} 未来十年 前景 预测`
- `{school} {major} 30年以后 这个学校 这个专业 还在吗`
- `{school} {major} 读这个 专业 会成为 什么样的人`
- `{school} {major} 给 即将 报考 的 你一封信`

---

## 执行说明

### 搜索执行策略（强制执行）

**🚫 Claude 禁止行为**：
- 禁止以"节省时间""提高效率""结果已足够"为由自行减少搜索量
- 禁止跳过某个维度（即使该维度暂时无结果）
- 禁止在搜索中途评估"信息已经够了"并提前终止
- 禁止将高强度自动降级为中/低强度

**✅ 正确行为**：
1. Phase 0 让用户选强度 → 锁定强度 → 执行全部查询
2. 每批8-10条搜索，执行完一批后：
   - 保存原始结果到 `reports/raw_search_{school}_{major}_batch{N}.json`
   - 立即从搜索摘要中提取关键 Claim，追加到 `reports/claims_{school}_{major}.json`
3. 保存格式：每条搜索结果记录 `{dimension, query, title, url, snippet}`
4. 每完成 50 条搜索保存一个 batch JSON，Claim 直接追加到同一文件
5. 每批完成后必须输出进度："已完成 N/总量（X%），当前维度：XXXX"
4. 搜索 JSON 结构：
```json
{
  "school": "{school}",
  "major": "{major}",
  "search_date": "ISO日期",
  "search_results": [
    {
      "dimension": "school_info",
      "query": "原始查询文本",
      "results": [
        {"title": "结果标题", "url": "URL", "snippet": "摘要内容"}
      ]
    }
  ]
}
```

### 速率控制
- WebSearch 每批之间间隔 2-3 秒
- 如果某次搜索失败（无结果），记录后继续下一条
- 每完成 50 条搜索后暂停 1 分钟，再继续下一轮

### ⚠️ 内容安全过滤处理 (400 Content Exists Risk)

部分查询关键词可能触发内容安全过滤（常见于"军工""兵器""武器""涉密"等），**不要因此中断整个搜索流程**：

**策略：跳过 + 换词重试**

1. **遇到 400 错误立即跳过**，记录到 `reports/skipped_queries_{school}_{major}.json`，继续下一条
2. **换近义词重试**：
   - `军工` → `国防特色` / `工信部背景`
   - `兵器` → `装备制造` / `国防科研`
   - `武器系统` → `控制系统` / `自动化装备`
   - `火力控制` → `运动控制` / `导航制导`
   - `涉密` → `保密要求` / `特殊管理`
   - `军事化管理` → `严格管理` / `半军事化`
3. **每条敏感查询最多换词重试 2 次**，仍失败则永久跳过
4. **被跳过的查询不影响 Phase 3 分析**，Claude 会在"缺失信息"章节标注哪些维度因过滤导致数据不足

**心态**：600+ 条查询中被过滤 10-30 条是正常的，不影响整体分析质量。严禁因为几条查询失败就放弃整个搜索任务。

### 分析管线（全部由 Claude 完成，零外部 API）
搜索全部完成后：
1. 读取全部 Claim 文件 `reports/claims_{school}_{major}.json`
2. 运行 scoring.py 规则引擎（纯 Python，计算共识/争议/风险）
3. Claude 对全部 Claim 做交叉验证 + 可信度校准
4. Claude 撰写完整报告（15,000-25,000字）
5. 输出到 `reports/{school}_{major}_报告.md`

---

## Output Format (报告格式要求)

报告必须以以下结构输出 `reports/{school}_{major}_报告.md`：

### 必须包含的章节

1. **总体结论** (600-800字 — 最重要！)
   - 一句话核心总结
   - 核心优势 (5-8条)
   - 核心劣势/风险 (5-8条)
   - 适合/不适合人群
   - 最终报考建议 (明确：推荐/可考虑/不推荐，及条件)

2. **录取分析** — 多省分数线/位次/趋势/策略
3. **专业含金量** — 学科实力/课程/师资/方向
4. **保研与升学** — 保研率/去向/条件/考研
5. **就业质量** — 薪资/去向/行业/长线
6. **行业趋势** — 前景/细分/转型
7. **实验室与科研** — 平台/方向/导师/本科参与
8. **★社媒反馈共识** — 知乎/贴吧/小红书/B站 共识/争议/孤证 分类
9. **校园生活** — 宿舍/食堂/环境/管理
10. **风险雷达** — 风险等级/类型/描述/应对
11. **对比分析** — 与同类院校专业的多维度对比表
12. **证据墙** — 关键结论→来源→可信度映射表
13. **缺失信息清单** — 本次搜索未获取的内容
14. **关键问答** — 3-5个最重要问题的针对性回答

### 格式要求
- 每个结论必须标注：**可信度**(高/中/低) + **证据来源**(搜索URL或平台)
- 严禁编造数据，不确定的用"数据缺失"标注
- 社媒反馈须标注"共识"(≥3个独立来源)/"争议"(正反各半)/"孤证"(仅1个来源)
- 数值必须标注时间（如"2024届数据"）
- 报告总字数目标: **15000-25000字** — 这不是玩具，要能决定命运

---

## 附录: 纯 Claude 方案说明

本 Skill 不依赖任何外部 LLM API。以下是方案中使用的文件说明：

### 保留文件（纯规则逻辑，零 API）

| 文件 | 用途 |
|------|------|
| `packages/ranking/scoring.py` | 共识分析、风险检测、反证查找（纯规则，无网络调用） |
| `packages/config.py` | 路径配置 |
| `packages/nlp/pii_cleaner.py` | PII 清理（合规需要） |

### 不需要的文件

| 文件 | 原因 |
|------|------|
| `packages/nlp/llm_service.py` | DeepSeek API 封装，纯 Claude 方案不需要 |
| `apikey.txt.example` | 不再需要外部 API Key |
| `openai`/`tiktoken` 依赖 | 不再调用 OpenAI 兼容 API |

### README 注意

README 应同步更新：移除 DeepSeek API Key 配置步骤，移除 `openai` 依赖说明。
