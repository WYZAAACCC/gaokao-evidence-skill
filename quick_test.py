#!/usr/bin/env python3
"""
快速验证脚本 — 用已有的搜索结果JSON跑分析管线，验证报告质量。

用法:
  # 从WebSearch保存的JSON运行完整分析
  python .claude/skills/gaokao-evidence/quick_test.py "南京理工大学" "自动化"

  # 指定JSON路径
  python .claude/skills/gaokao-evidence/quick_test.py "南京理工大学" "自动化" reports/raw_search_南京理工大学_自动化.json
"""
import asyncio, sys, json, os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from packages.nlp.llm_service import extract_claims, generate_profile_report, answer_question
from packages.ranking.scoring import *


async def quick_test(school_name: str, major_name: str, json_path: str | None = None):
    """快速分析 — 从JSON加载搜索结果，跑完整分析管线"""

    if json_path is None:
        json_path = f"reports/raw_search_{school_name}_{major_name}.json"

    if not os.path.exists(json_path):
        print(f"ERROR: 找不到 {json_path}")
        print("请先执行 Phase 2 (WebSearch) 或将搜索结果保存为上述文件")
        return

    with open(json_path, encoding='utf-8') as f:
        raw = json.load(f)

    # === 提取数据 ===
    all_texts = []
    evidence_summaries = []
    seen_urls = set()

    search_results = raw.get('search_results', [])
    for item in search_results:
        texts = []
        for r in item.get('results', []):
            snippet = r.get('snippet', '') or r.get('content', '') or ''
            title = r.get('title', '') or ''
            url = r.get('url', '') or ''

            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)

            texts.append(f"{title}。{snippet}")
            evidence_summaries.append({
                'source_type': 'web',
                'source_name': title[:100],
                'url': url,
                'excerpt': snippet[:500],
                'dimension': item.get('dimension', 'unknown'),
            })
        if texts:
            all_texts.append('\n'.join(texts))

    print(f"搜索批次: {len(search_results)}")
    print(f"去重证据: {len(evidence_summaries)} 条")
    print(f"唯一URL: {len(seen_urls)} 个")

    # === 提取Claim ===
    combined = '\n---\n'.join(all_texts)
    print(f"文本总量: {len(combined):,} 字")

    # 智能分块
    chunk_size = 10000
    overlap = 2000
    chunks = []
    start = 0
    max_chunks = 80
    while start < len(combined) and len(chunks) < max_chunks:
        end = min(start + chunk_size, len(combined))
        chunks.append(combined[start:end])
        start = end - overlap

    print(f"分 {len(chunks)} 批抽取...")
    all_claims = []
    for i, chunk in enumerate(chunks):
        try:
            claims = await extract_claims(chunk)
            all_claims.extend(claims)
            if (i + 1) % 5 == 0 or i == 0:
                print(f"  [{i+1}/{len(chunks)}] +{len(claims)} = {len(all_claims)} 条")
        except Exception as e:
            print(f"  [{i+1}/{len(chunks)}] 失败: {e}")

    if not all_claims:
        print("ERROR: 未提取到任何Claim!")
        return

    print(f"\n总计: {len(all_claims)} 条Claim")

    # === 维度统计 ===
    dims = {}
    for c in all_claims:
        d = c.get('dimension', '?')
        dims[d] = dims.get(d, 0) + 1
    for k, v in sorted(dims.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}条")

    # === 分析 ===
    print(f"\n共识/风险/反证分析...")
    consensus = generate_consensus_analysis(all_claims)
    risks = analyze_risk_items(all_claims)
    counters = find_counter_evidence(all_claims)

    expected_keys = {'school_info', 'admission', 'education', 'baoyan', 'employment',
                     'industry', 'lab', 'social', 'life', 'risk'}
    found = set(c.get('dimension', '?') for c in all_claims)
    covered = found & expected_keys
    conf = compute_conclusion_confidence(
        len(all_claims), len(covered),
        has_official=True,
        has_social=('social' in found),
        has_counter_evidence=len(counters) > 0
    )

    print(f"  共识: {len(consensus.get('consensus',[]))} | "
          f"争议: {len(consensus.get('controversies',[]))} | "
          f"风险: {len(risks)} | 反证: {len(counters)}对")
    print(f"  维度覆盖: {len(covered)}/10 = {sorted(covered)}")
    print(f"  可信度: {conf['level']} ({conf['score']:.2f})")

    # === 报告 ===
    print(f"\n生成报告...")
    sorted_c = sorted(all_claims, key=lambda c: c.get('confidence_score', 0) or 0, reverse=True)
    top_n = min(200, len(sorted_c))
    top_ev = min(120, len(evidence_summaries))

    report = await generate_profile_report(
        school_name, major_name, '',
        sorted_c[:top_n], evidence_summaries[:top_ev],
        consensus_data=consensus, risk_data=risks
    )

    # === 关键QA ===
    questions = [
        f"{school_name}的{major_name}专业总体值得报考吗？给出明确结论和建议。",
        f"{school_name}的{major_name}最大的优势和最大的风险分别是什么？",
        f"什么样的学生适合读{school_name}的{major_name}，什么样的不适合？",
    ]
    qa_parts = []
    for q in questions:
        try:
            ans = await answer_question(q, sorted_c[:50], evidence_summaries[:50])
            qa_parts.append(f"### Q: {q}\n\n{ans}\n")
        except Exception as e:
            qa_parts.append(f"### Q: {q}\n\n*错误: {e}*\n")

    # === 保存 ===
    dim_table_lines = []
    for k, v in sorted(dims.items(), key=lambda x: -x[1]):
        dim_table_lines.append(f"| {k} | {v}条 |")

    final = f"""# {school_name} - {major_name} 志愿决策分析报告

> 搜索批次: {len(search_results)} | 证据: {len(evidence_summaries)}条 | Claim: {len(all_claims)}条
> 维度覆盖: {len(covered)}/10 | 可信度: **{conf['level']}** ({conf['score']:.2f})
> 共识{len(consensus.get('consensus',[]))}/争议{len(consensus.get('controversies',[]))}/风险{len(risks)}/反证{len(counters)}对

---

## 维度覆盖

| 维度 | Claim数 |
|------|---------|
{chr(10).join(dim_table_lines)}

---

{report}

---

## 关键问答

{chr(10).join(qa_parts)}

---

*本报告由高考志愿证据推荐系统自动生成。每个结论标注可信度和证据来源。*
"""
    os.makedirs('reports', exist_ok=True)
    out_path = f"reports/{school_name}_{major_name}_报告.md"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(final)

    print(f"\n{'='*60}")
    print(f"  报告: {out_path} ({len(final):,}字)")
    print(f"  Claim: {len(all_claims)} | 可信度: {conf['level']} ({conf['score']:.2f})")
    print(f"{'='*60}")

    # 快速摘要
    print(f"\n📊 快速摘要:")
    print(f"  ────────────────────────")
    for k, v in sorted(dims.items(), key=lambda x: -x[1]):
        bar = '█' * min(v, 30)
        print(f"  {k:20s} {v:4d} {bar}")
    print(f"  ────────────────────────")
    print(f"  覆盖: {len(covered)}/10 维度, 缺失: {sorted(expected_keys - covered) if expected_keys - covered else '无'}")


if __name__ == '__main__':
    school = sys.argv[1] if len(sys.argv) > 1 else '南京理工大学'
    major = sys.argv[2] if len(sys.argv) > 2 else '自动化'
    json_path = sys.argv[3] if len(sys.argv) > 3 else None
    asyncio.run(quick_test(school, major, json_path))
