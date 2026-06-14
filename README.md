# 🎓 Gaokao Real Evidence Advisor

<p align="center">
  <b>证据驱动的高考志愿推荐系统</b><br>
  <sub>一个 Claude Code Skill — 零基础设施，零外部 API，即插即用</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/platform-Claude%20Code-orange.svg" alt="Claude Code">
  <img src="https://img.shields.io/badge/API-none-brightgreen.svg" alt="No API">
</p>

---

> **"每个推荐结论必须能追溯到证据。"**
>
> 高考志愿是能改变人生轨迹的决策。本系统用 **600+ 条跨维度搜索 + Claude 原生推理** 抹平信息差。
> **不需要任何外部 API Key。**

---

## ⚡ 2 分钟上手

```bash
# 克隆到 Claude Code skills 目录
# macOS / Linux:
git clone https://github.com/WYZAAACCC/gaokao-evidence-skill.git \
  ~/.claude/skills/gaokao-evidence/
cd ~/.claude/skills/gaokao-evidence

# Windows (PowerShell):
git clone https://github.com/WYZAAACCC/gaokao-evidence-skill.git \
  $env:USERPROFILE\.claude\skills\gaokao-evidence\
cd $env:USERPROFILE\.claude\skills\gaokao-evidence\

# 安装（仅需 Python 标准库，无外部依赖）
pip install -e .
```

然后在 Claude Code 中直接说：

```
帮我分析 南京理工大学 自动化专业
```

---

## 🏗️ 工作流程

```
用户输入 "XX学校 XX专业 怎么样"
         │
         ▼
┌─────────────────────────────────────┐
│  Phase 1: 生成查询                  │
│  从 600+ 模板生成搜索查询列表        │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Phase 2: 大规模搜索 + Claim 提取   │
│  Claude WebSearch × 600+ 条查询     │
│  每批 8-10 条，搜完即提取 Claim     │
│  10维度: 院校/专业/录取/保研/就业/  │
│  行业/实验室/社媒/校园/风险         │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Phase 3: Claude 原生分析           │
│  规则引擎(纯Python) → 共识/风险     │
│  Claude 交叉验证 + 可信度校准       │
│  反证检测 + 缺失维度识别            │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Phase 4: 报告撰写                  │
│  总体结论 + 14章节 + 证据墙 + QA    │
│  15,000-25,000 字 深度分析          │
└─────────────────────────────────────┘
```

---

## 📊 报告结构

| # | 章节 | 内容 |
|---|------|------|
| 1 | **总体结论** | 一句话总结 + 5-8优/劣 + 报考建议 |
| 2 | 录取分析 | 各省分数线/位次/趋势/策略 |
| 3 | 专业含金量 | 学科评估/课程/师资/方向 |
| 4 | 保研与升学 | 保研率/去向/考研难度 |
| 5 | 就业质量 | 薪资/行业/央企比例/长线 |
| 6 | 行业趋势 | 前景/细分/转型风险 |
| 7 | 实验室与科研 | 平台/方向/导师推荐 |
| 8 | ★社媒共识 | 知乎/贴吧/小红书/B站 |
| 9 | 校园生活 | 宿舍/食堂/管理/费用 |
| 10 | 风险雷达 | 13种风险分级 + 应对策略 |
| 11 | 对比分析 | 同类院校多维度对比表 |
| 12 | 证据墙 | 结论→来源→可信度映射 |
| 13 | 缺失信息 | 搜索未覆盖内容 |
| 14 | 关键问答 | 核心问题的针对性回答 |

---

## 📁 仓库结构

```
gaokao-evidence-skill/
├── SKILL.md                  # Skill 定义 (600+ 搜索查询模板 + 完整工作流)
├── packages/
│   ├── config.py             # 路径配置
│   ├── ranking/
│   │   └── scoring.py       # 评分/风险/共识分析（纯规则引擎）
│   └── nlp/
│       └── pii_cleaner.py   # PII 清理
├── tests/
│   └── test_scoring.py      # 15 个单元测试
├── pyproject.toml            # Python 项目配置
├── reports/                  # 报告输出目录
├── LICENSE
└── README.md
```

---

## 🔑 依赖

- **Claude Code** — 提供 WebSearch + 原生推理能力
- **Python 3.11+** — 运行规则引擎（`scoring.py`）
- **零 Python 依赖** — 规则引擎仅用标准库
- **零外部 API** — 不需要 DeepSeek/OpenAI/任何 API Key

---

## 🧪 测试

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## ⚠️ 合规

- ✅ 只采集公开可访问数据
- ✅ 社媒内容 PII 去标识化
- ✅ 社媒标注"反馈证据"而非事实断言
- ❌ 不绕过登录/验证码/付费墙

---

## 📄 License

MIT — 详见 [LICENSE](LICENSE)
