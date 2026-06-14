"""Tests for scoring and ranking module."""

import pytest
from packages.ranking.scoring import (
    compute_evidence_score,
    compute_conclusion_confidence,
    analyze_risk_items,
    generate_consensus_analysis,
    EvidenceScore,
    SchoolMajorScores,
    SOURCE_WEIGHTS,
)


class TestComputeEvidenceScore:
    def test_official_source_high_weight(self):
        score = compute_evidence_score("government", publish_year=2025)
        assert score.source_weight == 0.95
        assert score.timeliness_weight == 1.0

    def test_marketing_low_weight(self):
        score = compute_evidence_score("marketing")
        assert score.source_weight == 0.05

    def test_old_data_penalty(self):
        score = compute_evidence_score("employment_report", publish_year=2010)
        assert score.timeliness_weight < 0.3

    def test_corroboration_boost(self):
        score = compute_evidence_score("zhihu_detailed", corroboration_count=5)
        assert score.corroboration_weight == 1.0

    def test_score_ranges(self):
        score = compute_evidence_score("official_website")
        assert 0.0 <= score.total <= 1.0


class TestComputeConclusionConfidence:
    def test_high_confidence(self):
        result = compute_conclusion_confidence(
            evidence_count=10,
            source_diversity=3,
            has_official=True,
            has_social=True,
            has_counter_evidence=False,
        )
        assert result["level"] == "高可信"
        assert result["score"] >= 0.7

    def test_conflict(self):
        result = compute_conclusion_confidence(
            evidence_count=2,
            source_diversity=1,
            has_counter_evidence=True,
        )
        assert result["level"] == "冲突"

    def test_low_confidence(self):
        result = compute_conclusion_confidence(
            evidence_count=1,
            source_diversity=1,
        )
        assert result["level"] in ("低可信", "中可信")


class TestAnalyzeRiskItems:
    def test_risk_detected(self):
        claims = [
            {"claim_text": "本科就业差，必须读研才能找到好工作", "polarity": "negative", "claim_id": "1"},
            {"claim_text": "校区偏远，交通不便", "polarity": "negative", "claim_id": "2"},
        ]
        risks = analyze_risk_items(claims)
        assert len(risks) >= 1

    def test_no_risk_in_positive(self):
        claims = [
            {"claim_text": "专业很好，就业前景广阔", "polarity": "positive", "claim_id": "1"},
        ]
        risks = analyze_risk_items(claims)
        # Positive claims shouldn't trigger risk keywords
        assert all(r["risk_type"] != "本科就业弱" for r in risks)


class TestGenerateConsensusAnalysis:
    def test_consensus_detected(self):
        claims = [
            {"dimension": "employment", "topic": "就业", "polarity": "positive"},
            {"dimension": "employment", "topic": "就业", "polarity": "positive"},
            {"dimension": "employment", "topic": "就业", "polarity": "positive"},
        ]
        result = generate_consensus_analysis(claims)
        assert len(result["consensus"]) >= 1

    def test_controversy_detected(self):
        claims = [
            {"dimension": "employment", "topic": "就业", "polarity": "positive"},
            {"dimension": "employment", "topic": "就业", "polarity": "negative"},
            {"dimension": "employment", "topic": "就业", "polarity": "positive"},
        ]
        result = generate_consensus_analysis(claims)
        assert len(result["controversies"]) >= 1

    def test_isolated_detected(self):
        claims = [
            {"dimension": "lab", "topic": "实验室", "polarity": "negative"},
        ]
        result = generate_consensus_analysis(claims)
        assert len(result["isolated_claims"]) >= 1


class TestSchoolMajorScores:
    def test_total_calculation(self):
        scores = SchoolMajorScores(
            admission_feasibility=15,
            major_quality=12,
            education_path=10,
            employment_quality=8,
            industry_outlook=5,
            research_fit=3,
            student_preference_fit=5,
            risk_penalty=3,
            uncertainty_penalty=2,
        )
        assert scores.total == 15 + 12 + 10 + 8 + 5 + 3 + 5 - 3 - 2

    def test_tier_classification(self):
        high = SchoolMajorScores(admission_feasibility=80)
        assert high.tier == "冲"

        mid = SchoolMajorScores(admission_feasibility=60)
        assert mid.tier == "稳"

        low = SchoolMajorScores(admission_feasibility=40)
        assert low.tier == "保"
