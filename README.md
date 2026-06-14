# 🎓 Gaokao Real Evidence Advisor

<p align="center">
  <b>证据驱动的高考志愿推荐系统</b><br>
  <sub>一个 Claude Code Skill — 零基础设施，即插即用</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/LLM-DeepSeek-brightgreen.svg" alt="DeepSeek">
  <img src="https://img.shields.io/badge/platform-Claude%20Code-orange.svg" alt="Claude Code">
</p>

---

> **"每个推荐结论必须能追溯到证据。"**
>
> 高考志愿是能改变人生轨迹的决策。本系统用 **600+ 条跨维度搜索 + LLM 交叉验证** 抹平信息差。

---

## ⚡ 5 分钟上手

### 1. 安装

```bash
# 克隆到 Claude Code skills 目录
git clone https://github.com/YOUR_USER/gaokao-evidence-skill.git \
  ~/.claude/skills/gaokao-evidence/

# Windows:
git clone https://github.com/YOUR_USER/gaokao-evidence-skill.git \
  %USERPROFILE%\.claude\skills\gaokao-evidence\

# 放入 DeepSeek API Key
echo "sk-your-api-key" > ~/.claude/skills/gaokao-evidence/apikey.txt
```

### 2. 使用

在 Claude Code 对话中直接说：

```
帮我分析 南京理工大学 自动化专业
```

Claude 将自动执行：
1. **10 维度 × 600+ 条搜索** — 使用 Claude 内建 WebSearch
2. **结构化 Claim 抽取** — 调用 DeepSeek API
3. **交叉验证 & 风险分析** — 共识/争议/反证检测
4. **生成深度报告** — 15,000+ 字，14 个章节

### 3. 查看报告

报告输出到 `reports/南京理工大学_自动化_报告.md`

---

## 🏗️ 工作流程

```
用户输入 "XX学校 XX专业 怎么样"
         │
         ▼
┌─────────────────────────────────────┐
│  Phase 1: 大规模搜索                │
│  Claude WebSearch × 600+ 条查询     │
│  院校/专业/录取/保研/就业/行业/     │
│  实验室/社媒/校园/风险/对比         │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Phase 2: Claim 抽取                │
│  DeepSeek API 批量处理              │
│  搜索文本 → 结构化声明              │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Phase 3: 交叉验证 & 评分           │
│  共识/争议/孤证 · 13种风险 · 反证  │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Phase 4: 报告生成                  │
│  总体结论 + 12章节 + 证据墙 + QA    │
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

## 📁 文件说明

```
gaokao-evidence-skill/
├── SKILL.md              # Skill 定义 (600+ 搜索查询模板)
├── analyze.py            # 分析引擎 (搜索→Claim→报告)
├── quick_test.py         # 快速验证脚本
├── packages/
│   ├── config.py         # 配置 (从 apikey.txt 读 API Key)
│   ├── nlp/
│   │   └── llm_service.py   # DeepSeek API 封装
│   └── ranking/
│       └── scoring.py       # 评分/风险/共识分析
├── apikey.txt.example    # API Key 模板
├── pyproject.toml        # Python 依赖
├── reports/              # 报告输出目录
└── README.md
```

---

## 🔑 依赖

- **Claude Code** — 提供 WebSearch 能力
- **DeepSeek API** — Claim 抽取 + 报告生成
- **Python 3.11+** — 运行分析脚本
- `openai` + `tiktoken` — Python 依赖 (`pip install -e .`)

不需要 Docker、PostgreSQL、SearXNG 或任何其他基础设施。

---

## 🧪 测试

```bash
pip install -e ".[dev]"
python quick_test.py "南京理工大学" "自动化" reports/raw_search_南京理工大学_自动化.json
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
