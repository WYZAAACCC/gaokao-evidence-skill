#!/usr/bin/env python3
"""
分析引擎 — 接收搜索结果JSON，调用DeepSeek抽取Claim，生成报告。
由Skill的Step 3调用。

支持超大规模搜索数据：600+搜索批次，500+ evidence summaries，
2000+ claims，全维度覆盖。
"""
import asyncio, sys, os, json
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from packages.nlp.llm_service import extract_claims, generate_profile_report, answer_question
from packages.ranking.scoring import *


async def analyze(school_name: str, major_name: str, raw_data_path: str) -> str:
    """主分析函数 — 处理超大规模搜索数据"""

    # === 加载数据 ===
    with open(raw_data_path, encoding='utf-8') as f:
        raw = json.load(f)

    # 检查是否是合并后的格式
    if 'search_results' in raw:
        search_results = raw['search_results']
    elif 'batches' in raw:
        # 合并多个batch
        search_results = []
        for batch_path in raw['batches']:
            with open(batch_path, encoding='utf-8') as bf:
                batch = json.load(bf)
                search_results.extend(batch.get('search_results', []))
    else:
        search_results = []

    total_queries = raw.get('total_queries', len(search_results))

    # === 构建证据摘要 ===
    all_texts = []
    evidence_summaries = []
    seen_urls = set()

    for item in search_results:
        texts = []
        for r in item.get('results', []):
            snippet = r.get('snippet', '') or r.get('content', '') or ''
            title = r.get('title', '') or ''
            url = r.get('url', '') or ''

            if url and url in seen_urls:
                continue  # 去重
            if url:
                seen_urls.add(url)

            text = f"{title}。{snippet}"
            texts.append(text)
            evidence_summaries.append({
                'source_type': 'web',
                'source_name': title[:100],
                'url': url,
                'excerpt': snippet[:500],
                'dimension': item.get('dimension', 'unknown'),
            })
        if texts:
            all_texts.append('\n'.join(texts))

    print("=" * 60)
    print(f"  高考志愿证据推荐系统 — 分析引擎")
    print(f"  目标: {school_name} - {major_name}")
    print("=" * 60)
    print(f"  搜索批次: {total_queries}")
    print(f"  去重后的证据源: {len(evidence_summaries)}")
    print(f"  唯一URL: {len(seen_urls)}")

    # === 分批次提取Claim (支持超大数据量) ===
    combined = '\n---\n'.join(all_texts)
    print(f"  文本总长: {len(combined):,} 字")

    # 动态调整分块策略
    if len(combined) < 50000:
        chunk_size = 8000
        max_chunks = 10
    elif len(combined) < 150000:
        chunk_size = 10000
        max_chunks = 25
    elif len(combined) < 500000:
        chunk_size = 12000
        max_chunks = 60
    else:
        chunk_size = 15000
        max_chunks = 100

    # 优化：使用更大的chunk和滑动窗口确保覆盖
    chunks = []
    overlap = 2000  # 重叠量避免截断
    start = 0
    while start < len(combined) and len(chunks) < max_chunks:
        end = min(start + chunk_size, len(combined))
        chunks.append(combined[start:end])
        start = end - overlap

    print(f"  分 {len(chunks)} 批抽取Claim (chunk={chunk_size}, overlap={overlap})...")

    all_claims = []
    for i, chunk in enumerate(chunks):
        try:
            claims = await extract_claims(chunk)
            all_claims.extend(claims)
            if (i + 1) % 5 == 0 or i == len(chunks) - 1:
                print(f"    批次{i+1}/{len(chunks)}: {len(claims)}条 → 累计{len(all_claims)}条")
        except Exception as e:
            print(f"    批次{i+1}/{len(chunks)}: 失败 ({e}), 跳过")

    print(f"  总计: {len(all_claims)} 条结构化Claim")

    if len(all_claims) < 20:
        print(f"  ⚠️  WARNING: Claim数量过少 ({len(all_claims)}), 搜索数据可能不足")

    # === 维度分析 ===
    dims = {}
    for c in all_claims:
        d = c.get('dimension', 'unknown')
        dims[d] = dims.get(d, 0) + 1

    print(f"\n  维度覆盖:")
    expected_dims = {
        'school_info': '院校情况', 'admission': '录取', 'education': '专业培养',
        'baoyan': '保研', 'employment': '就业', 'industry': '行业',
        'lab': '实验室', 'social': '社媒', 'life': '校园生活', 'risk': '风险',
        'comparison': '对比', 'recommendation': '推荐',
    }
    for k, v in sorted(dims.items(), key=lambda x: -x[1]):
        label = expected_dims.get(k, k)
        bar = '█' * min(v, 30)
        print(f"    {label}({k}): {v}条 {bar}")

    found = set(c.get('dimension', '?') for c in all_claims)
    expected_keys = {'school_info', 'admission', 'education', 'baoyan', 'employment',
                     'industry', 'lab', 'social', 'life', 'risk'}
    covered = found & expected_keys
    missing = expected_keys - covered
    print(f"  覆盖: {len(covered)}/{len(expected_keys)} = {sorted(covered)}")
    if missing:
        print(f"  ⚠️  缺失维度: {sorted(missing)}")

    # === 共识/风险/反证分析 ===
    print(f"\n  分析中...")
    consensus = generate_consensus_analysis(all_claims)
    risks = analyze_risk_items(all_claims)
    counters = find_counter_evidence(all_claims)
    conf = compute_conclusion_confidence(
        len(all_claims), len(covered),
        has_official=True, has_social=('social' in found),
        has_counter_evidence=len(counters) > 0
    )

    print(f"  共识: {len(consensus.get('consensus',[]))}条 | "
          f"争议: {len(consensus.get('controversies',[]))}条 | "
          f"孤证: {len(consensus.get('isolated_claims',[]))}条")
    print(f"  风险: {len(risks)}条 | 反证对: {len(counters)}对")
    print(f"  综合可信度: {conf['level']} ({conf['score']:.2f})")

    # === 生成报告 ===
    print(f"\n  生成画像报告...")
    sorted_c = sorted(all_claims, key=lambda c: c.get('confidence_score', 0) or 0, reverse=True)

    # 使用更多claim和evidence生成报告
    top_n_claims = min(200, len(sorted_c))
    top_n_ev = min(120, len(evidence_summaries))

    report = await generate_profile_report(
        school_name, major_name, '',
        sorted_c[:top_n_claims],
        evidence_summaries[:top_n_ev],
        consensus_data=consensus,
        risk_data=risks
    )

    # === 关键问答 ===
    print(f"  回答关键问题...")
    key_questions = [
        f"{school_name}的{major_name}专业总体值得报考吗？请基于搜索数据给出明确建议，标注置信度。哪类学生强烈推荐，哪类学生强烈劝退？",
        f"{school_name}的{major_name}和同类院校（南航/合工大/哈工程等）相比，最大的差异化优势和致命劣势分别是什么？",
        f"什么样的学生绝对不适合读{school_name}的{major_name}？如果已经录取了该怎么办？",
        f"{school_name}的{major_name}四年后的出路有哪些？本科就业、考研、保研三条路径各自的概率和性价比如何？",
        f"对普通家庭/农村家庭的学生来说，读{school_name}的{major_name}性价比怎么样？能改变命运吗？",
    ]
    qa_parts = []
    for q in key_questions:
        try:
            ans = await answer_question(q, sorted_c[:50], evidence_summaries[:50])
            qa_parts.append(f"### Q: {q}\n\n{ans}\n")
        except Exception as e:
            qa_parts.append(f"### Q: {q}\n\n*回答生成失败: {e}*\n")

    # === 组装最终报告 ===
    dim_summary_lines = []
    for k, v in sorted(dims.items(), key=lambda x: -x[1]):
        label = expected_dims.get(k, k)
        dim_summary_lines.append(f"| {label} | {v}条 |")

    dim_table = '\n'.join(dim_summary_lines) if dim_summary_lines else '无数据'

    final = f"""# {school_name} - {major_name} 志愿决策分析报告

> **生成时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
> **搜索规模**: {total_queries} 次查询 | {len(evidence_summaries)} 条证据源 | {len(all_claims)} 条结构化声明
> **维度覆盖**: {len(covered)}/{len(expected_keys)} ({', '.join(sorted(covered))})
> **综合可信度**: **{conf['level']}** ({conf['score']:.2f})
> **共识/争议/孤证**: {len(consensus.get('consensus',[]))}/{len(consensus.get('controversies',[]))}/{len(consensus.get('isolated_claims',[]))}
> **风险项**: {len(risks)} | **反证对**: {len(counters)}

---

## 维度覆盖详情

| 维度 | Claim数量 |
|------|-----------|
{dim_table}

---

{report}

---

## 关键问答

{chr(10).join(qa_parts)}

---

*本报告由高考志愿证据推荐系统自动生成。每个结论均标注可信度和证据来源。如有"数据缺失"标注表示该部分信息在搜索中未获取，不得推断填充。*
"""

    # === 保存 ===
    os.makedirs('reports', exist_ok=True)
    out_path = f"reports/{school_name}_{major_name}_报告.md"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(final)

    # 保存元数据
    meta = {
        'school': school_name,
        'major': major_name,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'search_queries': total_queries,
        'evidence_count': len(evidence_summaries),
        'unique_urls': len(seen_urls),
        'claims': len(all_claims),
        'dims': dims,
        'covered': sorted(covered),
        'missing': sorted(missing),
        'confidence': conf,
        'consensus_count': len(consensus.get('consensus', [])),
        'controversy_count': len(consensus.get('controversies', [])),
        'risk_count': len(risks),
        'counter_evidence_pairs': len(counters),
        'report_path': out_path,
        'text_chars': len(combined),
    }
    with open(f"reports/{school_name}_{major_name}_meta.json", 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"  报告已生成: {out_path}")
    print(f"  字数: {len(final):,} | Claim: {len(all_claims)} | 来源: {len(evidence_summaries)}")
    print(f"  可信度: {conf['level']} ({conf['score']:.2f})")
    print(f"{'=' * 60}")

    return final


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("用法: python analyze.py <学校> <专业> [raw_data.json路径]")
        print("示例: python analyze.py \"南京理工大学\" \"自动化\"")
        sys.exit(1)
    school = sys.argv[1]
    major = sys.argv[2]
    data_path = sys.argv[3] if len(sys.argv) > 3 else f"reports/raw_search_{school}_{major}.json"
    asyncio.run(analyze(school, major, data_path))
