"""
增强版评分与排序模块 — 可解释规则模型 + LLM辅助。

v2新增:
- 风险严重度分级 (critical/high/medium/low)
- 反证加权分析
- 加权评分 (从config加载权重)
- 类LLM证据强度评估
- 去重风险聚合
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ============================================================================
# 来源权重
# ============================================================================

SOURCE_WEIGHTS: dict[str, float] = {
    "government": 0.95,
    "employment_report": 0.85,
    "official_website": 0.80,
    "official": 0.80,
    "advisor_homepage": 0.75,
    "zhihu_detailed": 0.65,
    "xiaohongshu_detailed": 0.60,
    "social": 0.50,
    "report": 0.75,
    "comment_short": 0.35,
    "no_source_forward": 0.15,
    "marketing": 0.05,
    "manual": 0.40,
}

# 风险严重度关键词
RISK_SEVERITY_KEYWORDS = {
    "critical": ["无法就业", "毕业即失业", "找不到工作", "大面积", "严重", "极差"],
    "high": ["必须读研", "建议考研", "不读研没法", "很难", "困难", "严格", "严苛"],
    "medium": ["较难", "比较难", "压力大", "竞争激烈", "不太好", "一般"],
    "low": ["稍差", "有待改善", "不足", "欠缺", "偏少"],
}

RISK_KEYWORDS = {
    "必须读研": ["必须读研", "不读研", "没法就业", "找不到工作", "必须考研", "必须深造",
                "建议考研", "建议读研", "读研深造", "要读研"],
    "本科就业弱": ["本科就业差", "不好找", "就业难", "待遇不会高", "就业满意度",
                  "工资表示一般", "薪资天花板", "起薪低"],
    "专业名误导": ["名字好听", "实际不如预期", "和想象不一样", "专业名误导", "挂羊头"],
    "行业周期差": ["行业下行", "行业衰退", "就业形势差", "饱和", "需求下降", "行业萎缩"],
    "校区偏远": ["校区偏", "交通不便", "离市区远", "在郊区", "位置偏僻", "荒凉"],
    "转专业难": ["转专业难", "转专业竞争", "不容易转", "转不了", "转入竞争"],
    "课程脱节": ["课程老", "学不到东西", "课程脱节", "内容落后", "水课", "不够深入"],
    "隐形门槛": ["歧视", "门槛", "限制", "只要985", "只要211", "学历歧视"],
    "大类分流": ["大类招生", "专业分流", "按成绩分流", "分流到", "成绩不理想"],
    "管理严格": ["管理非常严格", "管理严格", "严格管理", "不能带电脑", "早晚自习", "军训严苛"],
    "学业压力": ["课程压力", "学业压力", "都难学", "很累", "压力大", "卷", "竞争激烈"],
    "宿舍条件差": ["宿舍差", "宿舍条件", "没独卫", "没阳台", "老宿舍", "住宿条件"],
    "食堂难吃": ["食堂难吃", "食堂差", "伙食差", "饭难吃", "饭菜差"],
}


# ============================================================================
# Data classes
# ============================================================================

@dataclass
class EvidenceScore:
    source_weight: float = 0.5
    timeliness_weight: float = 0.5
    specificity_weight: float = 0.5
    corroboration_weight: float = 0.5
    extraction_confidence: float = 0.5
    bias_correction: float = 1.0

    @property
    def total(self) -> float:
        return (
            self.source_weight * self.timeliness_weight *
            self.specificity_weight * self.corroboration_weight *
            self.extraction_confidence * self.bias_correction
        )

    @property
    def level(self) -> str:
        if self.total >= 0.7: return "高可信"
        elif self.total >= 0.4: return "中可信"
        elif self.total >= 0.2: return "低可信"
        return "极低可信"


@dataclass
class SchoolMajorScores:
    admission_feasibility: float = 0.0
    major_quality: float = 0.0
    education_path: float = 0.0
    employment_quality: float = 0.0
    industry_outlook: float = 0.0
    research_fit: float = 0.0
    student_preference_fit: float = 0.0
    risk_penalty: float = 0.0
    uncertainty_penalty: float = 0.0

    @property
    def total(self) -> float:
        return (self.admission_feasibility + self.major_quality +
                self.education_path + self.employment_quality +
                self.industry_outlook + self.research_fit +
                self.student_preference_fit -
                self.risk_penalty - self.uncertainty_penalty)

    @property
    def tier(self) -> str:
        if self.total >= 70: return "冲"
        elif self.total >= 50: return "稳"
        elif self.total >= 30: return "保"
        return "不建议"


@dataclass
class RecommendationOutput:
    school_name: str
    major_name: str
    campus: str = ""
    tier: str = ""
    score: float = 0.0
    suitable_for: list[str] = field(default_factory=list)
    not_suitable_for: list[str] = field(default_factory=list)
    max_benefit: str = ""
    max_risk: str = ""
    key_evidence: list[str] = field(default_factory=list)
    counter_evidence: list[str] = field(default_factory=list)
    missing_info: list[str] = field(default_factory=list)


# ============================================================================
# 证据评分
# ============================================================================

def compute_evidence_score(
    source_type: str,
    publish_year: int | None = None,
    specificity: float = 0.5,
    corroboration_count: int = 0,
    extraction_confidence: float = 0.5,
) -> EvidenceScore:
    import datetime
    score = EvidenceScore()
    score.source_weight = SOURCE_WEIGHTS.get(source_type, 0.3)

    current_year = datetime.datetime.now(datetime.timezone.utc).year
    if publish_year is None:
        score.timeliness_weight = 0.5
    else:
        age = current_year - publish_year
        score.timeliness_weight = {0: 1.0, 1: 1.0}.get(age, 1.0) if age <= 1 else \
                                  0.8 if age <= 3 else 0.5 if age <= 5 else 0.3 if age <= 10 else 0.1

    score.specificity_weight = max(0.1, specificity)
    score.corroboration_weight = 1.0 if corroboration_count >= 5 else \
                                  0.8 if corroboration_count >= 3 else \
                                  0.6 if corroboration_count >= 1 else 0.3
    score.extraction_confidence = max(0.1, extraction_confidence)
    return score


def compute_conclusion_confidence(
    evidence_count: int,
    source_diversity: int,
    has_official: bool = False,
    has_social: bool = False,
    has_counter_evidence: bool = False,
    time_consistency: bool = True,
) -> dict:
    score = 0.2
    score += 0.3 if evidence_count >= 10 else 0.2 if evidence_count >= 5 else 0.1 if evidence_count >= 2 else 0
    score += 0.2 if source_diversity >= 3 else 0.1 if source_diversity >= 2 else 0
    score += 0.2 if has_official and has_social else 0.1 if has_official or has_social else 0
    score -= 0.3 if has_counter_evidence else 0
    score -= 0.1 if not time_consistency else 0
    score = max(0.0, min(1.0, score))

    if has_counter_evidence and evidence_count < 5:
        level, desc = "冲突", "官方与民间反馈存在明显矛盾"
    elif score >= 0.7:
        level, desc = "高可信", "多源一致，来源质量高"
    elif score >= 0.4:
        level, desc = "中可信", "有多个反馈，但官方数据不足"
    else:
        level, desc = "低可信", "孤证或来源不稳定"

    return {"level": level, "score": score, "description": desc}


# ============================================================================
# 风险分析 (增强版)
# ============================================================================

def get_risk_severity(claim_text: str) -> str:
    """根据关键词判断风险严重度."""
    for level, keywords in RISK_SEVERITY_KEYWORDS.items():
        if any(kw in claim_text for kw in keywords):
            return level
    return "medium"


def analyze_risk_items(claims: list[dict]) -> list[dict]:
    """增强版风险分析 — 含严重度分级和去重聚合."""
    raw_risks = []
    for claim in claims:
        text = claim.get("claim_text", "")
        for risk_type, keywords in RISK_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                raw_risks.append({
                    "risk_type": risk_type,
                    "description": text,
                    "source_claim_id": claim.get("claim_id", ""),
                    "polarity": claim.get("polarity", ""),
                    "severity": get_risk_severity(text),
                })

    # 按risk_type去重聚合
    seen_types = set()
    deduped = []
    for r in sorted(raw_risks, key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x["severity"], 2)):
        if r["risk_type"] not in seen_types:
            seen_types.add(r["risk_type"])
            deduped.append(r)

    return deduped


# ============================================================================
# 共识分析
# ============================================================================

def cluster_claims_by_topic(claims: list[dict]) -> dict[str, list[dict]]:
    clusters: dict[str, list[dict]] = {}
    for claim in claims:
        dim = claim.get("dimension", "other")
        clusters.setdefault(dim, []).append(claim)
    return clusters


def generate_consensus_analysis(claims: list[dict]) -> dict:
    topic_groups = cluster_claims_by_topic(claims)
    consensus, controversies, isolated_claims = [], [], []

    for topic, group in topic_groups.items():
        positive = sum(1 for c in group if c.get("polarity") == "positive")
        negative = sum(1 for c in group if c.get("polarity") == "negative")

        if len(group) >= 3:
            if positive > 0 and negative > 0:
                controversies.append({
                    "topic": topic, "claim_count": len(group),
                    "positive_count": positive, "negative_count": negative,
                    "summary": f"存在争议，{positive}条正面 vs {negative}条负面",
                })
            else:
                consensus.append({
                    "topic": topic, "claim_count": len(group),
                    "dominant_polarity": "positive" if positive > negative else "negative",
                    "summary": f"多源一致（{len(group)}条）",
                })
        else:
            isolated_claims.append({
                "topic": topic, "claim_count": len(group),
                "summary": "孤证",
            })

    return {"consensus": consensus, "controversies": controversies, "isolated_claims": isolated_claims}


# ============================================================================
# 反证检测
# ============================================================================

def find_counter_evidence(claims: list[dict]) -> list[dict]:
    """查找互相矛盾的Claim对."""
    counters = []
    for i, c1 in enumerate(claims):
        for j, c2 in enumerate(claims):
            if j <= i:
                continue
            if (c1.get("dimension") == c2.get("dimension") and
                c1.get("polarity") != c2.get("polarity") and
                c1.get("polarity") in ("positive", "negative") and
                c2.get("polarity") in ("positive", "negative")):
                counters.append({
                    "dimension": c1.get("dimension"),
                    "claim_a": c1.get("claim_text", "")[:100],
                    "claim_b": c2.get("claim_text", "")[:100],
                    "polarity_a": c1.get("polarity"),
                    "polarity_b": c2.get("polarity"),
                })
    return counters
