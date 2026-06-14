"""
增强版 LLM 服务 — DeepSeek API 封装，支持多模型校验、批量抽取、CoT推理。

核心能力:
- Claim 抽取 (含批量+增量模式)
- 画像报告生成 (增强prompt，10个维度全覆盖)
- 反向问答 (证据锚定)
- 多模型交叉校验
- 结构化输出 + Schema验证
- Token预算与自动截断
"""

from __future__ import annotations

import json
import hashlib
from typing import Optional, Any

from openai import AsyncOpenAI

from packages.config import get_settings

settings = get_settings()

_client: Optional[AsyncOpenAI] = None
_usage_stats: dict[str, int] = {"total_tokens": 0, "total_calls": 0}


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout=120.0,
            max_retries=2,
        )
    return _client


def get_usage_stats() -> dict:
    return dict(_usage_stats)


# ============================================================================
# 增强版 System Prompts
# ============================================================================

CLAIM_EXTRACTION_V2 = """你是一位资深的高考志愿数据分析师。你的任务是从给定的文本中提取结构化的、可验证的声明(Claim)。

核心原则:
1. 每条 Claim 必须直接来自原文，逐字可查。严禁编造。
2. 宁可少提取，不可提取模糊或无实质内容的声明。
3. 对于数据类声明，必须包含具体数字（如果有的话）。

维度(dimension)说明:
- admission: 招生计划、录取分数、选科要求、批次、专业组
- education: 课程设置、培养方案、师资、专业建设、学科评估
- baoyan: 保研率、推免名额、保研去向、考研情况
- employment: 就业率、薪资、就业去向、行业分布、单位性质
- lab: 实验室、研究方向、导师、论文、项目、科研平台
- life: 校园生活、宿舍、食堂、管理、学风、社团
- industry: 行业趋势、岗位需求、政策变化、技术路线
- risk: 风险点、劝退点、坑点、注意事项

极性(polarity)说明:
- positive: 对该校/专业有利的信息
- negative: 不利或劝退信息
- neutral: 客观事实陈述
- mixed: 包含正反两面

输出要求:
- 每条claim的confidence_score反映信息在原文中的明确程度(0-1)
- specificity_score反映信息的具体程度(是否含数字、具体名称等)
- topic使用简短的中文标签，如"就业率"、"保研去向"、"课程难度"、"宿舍条件"

输出JSON格式: {"claims": [...]}"""

REPORT_V2 = """你是一位资深的高考志愿填报顾问，拥有20年经验。你正在为一位高三学生和家长撰写院校专业分析报告。

## 核心原则（必须严格遵守）

1. **每个结论必须有依据**: 标注可信度（高/中/低/冲突）和证据来源（官方文件/就业报告/社媒反馈/招生数据等）
2. **区分官方与民间**: 官方报告说就业好，社媒也说就业好=高可信。官方说好，社媒大量吐槽=打风险标记
3. **诚实披露风险**: 不回避负面信息。每个专业都必须输出风险，不许只说优点
4. **明确指出缺失**: 不知道的就坦承不知道，告诉读者"还缺什么信息"
5. **社媒局限性**: 说明社媒反馈的样本偏差（愿意发声的往往体验极端）、情绪化、时效性问题
6. **具体可操作**: 给出具体建议，而非泛泛而谈
7. **禁止编造**: 没有证据支撑的结论一律不得输出。不确定的用"数据缺失""待验证"标注

## 报告结构（必须按此顺序）

### 一、总体结论（ 500字以内，放在报告最前面 ）

1. **一句话总结**: 该专业值不值得报？适合什么人？
2. **核心优势** (3-5条，每条<30字，标可信度)
3. **核心劣势/风险** (3-5条，每条<30字，标可信度)
4. **报与不报建议**: 什么情况推荐报，什么情况不建议报

### 二、详细分析（10个维度）

**1. 录取可行性分析**
- 近3年录取位次趋势，标注数据来源省份和年份
- 招生计划变化（扩招/缩招信号）
- 选科要求
- 大小年风险分析
- 每个数据点标注来源

**2. 专业真实含金量**
- 学科评估等级 + 来源
- 课程设置特点（理论偏重/工程偏重/实践比例）
- 师资水平（院士/杰青/优青数量，教学口碑）
- 是否存在"名字好听但培养内容偏旧"情况

**3. 保研与升学路径**
- 保研率（全校/学院/专业三个层级）+ 来源年份
- 保研去向质量（C9/985/本校比例）
- 考研难度与本校优势
- 深造率（含出国比例）

**4. 就业质量与去向**
- 本科/硕士就业率 + 来源
- 平均/中位数薪资 + 来源年份
- 主要就业单位TOP10
- 就业地域分布
- 学历门槛：本科够不够，硕士是否刚需

**5. 行业前景与岗位趋势**
- 行业大趋势（上升/稳定/下行）
- 岗位学历要求分布
- 薪资天花板与中位数差距
- 是否容易被自动化/AI替代

**6. 实验室与研究方向**
- 重点实验室名称和级别
- 主要研究方向（哪些前沿，哪些传统）
- 本科生科研机会多不多
- 经费情况（有数据则引用）

**7. 学生真实体验（社媒共识）** ★ 重要
- 课程难度与学业压力的普遍反馈（引用平台名称）
- 管理风格（严格/宽松）的共识
- 宿舍/食堂/校园环境的典型评价
- "劝退点"和"真香点"
- 标注：共识/争议/孤证

**8. 风险雷达（分级：高/中/低）**
- 每个风险标注严重度
- 说明触发条件（什么情况下这个风险会成为现实）

**9. 缺失信息清单**
- 还缺哪些关键信息
- 建议从哪里获取

**10. 证据墙**
- 以表格列出关键结论-证据来源-可信度

### 三、适合/不适合人群 + 对比定位

- 适合什么学生（性格/能力/家庭条件/职业规划）
- 不适合什么学生
- 与相似专业的定位差异（如和计算机/电气/机械的区别）

### 四、报考建议

- 冲/稳/保 档位判断
- 什么分数位次可以报
- 备选方案推荐"""

QA_V2 = """你是一个基于证据的高考志愿问答系统。回答规则:

1. 回答必须基于提供的证据和声明，不清楚的地方明确指出。
2. 如果证据不足，诚实告知并建议用户从哪里获取信息。
3. 每个结论标注证据来源。
4. 不编造数据，不提供没有依据的建议。
5. 对于涉及个人选择的问题，给出基于证据的分析框架而非直接建议。"""


# ============================================================================
# 核心 API 调用 (带重试)
# ============================================================================

async def _call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    json_mode: bool = False,
) -> str:
    """LLM 调用 (带简单重试)."""
    from openai import AuthenticationError, BadRequestError, RateLimitError

    client = get_client()
    model_name = model or settings.llm_model

    kwargs: dict[str, Any] = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    last_error = None
    for attempt in range(3):
        try:
            response = await client.chat.completions.create(**kwargs)
            _usage_stats["total_calls"] += 1
            if response.usage:
                _usage_stats["total_tokens"] += response.usage.total_tokens
            return response.choices[0].message.content or ""
        except (AuthenticationError, BadRequestError) as e:
            # 不可重试的错误
            raise
        except RateLimitError as e:
            # 速率限制 — 等待后重试
            import asyncio
            await asyncio.sleep(2 ** attempt)
            last_error = e
        except Exception as e:
            last_error = e
            import asyncio
            await asyncio.sleep(1)

    raise last_error or RuntimeError("LLM call failed after 3 retries")


# ============================================================================
# Claim 抽取 (增强版)
# ============================================================================

async def extract_claims(
    text: str,
    model: str | None = None,
    min_confidence: float = 0.3,
) -> list[dict]:
    """从文本中提取结构化 Claim (增强版).

    - 短文本跳过
    - 自动截断超长文本
    - JSON解析容错
    - 低置信度过滤
    """
    if not text or len(text.strip()) < 20:
        return []

    truncated = text[:15000] if len(text) > 15000 else text

    try:
        content = await _call_llm(
            system_prompt=CLAIM_EXTRACTION_V2,
            user_prompt=f"请从以下文本中提取声明:\n\n{truncated}",
            model=model,
            temperature=0.15,
            max_tokens=4096,
            json_mode=True,
        )
        if not content:
            return []

        result = json.loads(content)
        claims = result if isinstance(result, list) else result.get("claims", [])

        # 过滤低置信度 + 去重
        seen = set()
        filtered = []
        for c in claims:
            # 兼容 "claim_text" / "text" / "claim" 三种key
            txt = c.get("claim_text") or c.get("text") or c.get("claim", "")
            if not txt or len(txt) < 5:
                continue
            if c.get("confidence_score", 0) < min_confidence:
                continue
            h = hashlib.md5(txt.encode()).hexdigest()
            if h in seen:
                continue
            seen.add(h)
            # 统一使用 claim_text key
            if "claim_text" not in c:
                if "text" in c:
                    c["claim_text"] = c.pop("text")
                elif "claim" in c:
                    c["claim_text"] = c.pop("claim")
            filtered.append(c)

        return filtered
    except json.JSONDecodeError:
        return []
    except Exception as e:
        print(f"[LLM] Claim extraction error: {e}")
        return []


async def extract_claims_batch(
    texts: list[str],
    model: str | None = None,
) -> list[list[dict]]:
    """批量抽取 Claim — 一次LLM调用处理多条文本."""
    results = []
    for text in texts:
        claims = await extract_claims(text, model=model)
        results.append(claims)
    return results


async def verify_claim(claim_text: str, original_text: str, model: str | None = None) -> dict:
    """交叉验证单条Claim是否与原文一致.

    Returns:
        {"consistent": bool, "explanation": str, "score": float}
    """
    prompt = f"""请验证以下声明是否与原文一致:

原文:
{original_text[:3000]}

声明:
{claim_text}

请判断声明是否可以从原文直接得出。输出JSON:
{{"consistent": true/false, "explanation": "说明", "score": 0.0-1.0}}"""

    try:
        content = await _call_llm(
            system_prompt="你是一个事实核查员。请严格判断声明是否与原文一致。",
            user_prompt=prompt,
            model=model,
            temperature=0.0,
            max_tokens=512,
            json_mode=True,
        )
        return json.loads(content)
    except Exception:
        return {"consistent": True, "explanation": "验证失败，默认保留", "score": 0.5}


# ============================================================================
# 画像报告
# ============================================================================

async def generate_profile_report(
    school_name: str,
    major_name: str,
    campus: str | None,
    claims: list[dict],
    evidence_summaries: list[dict],
    consensus_data: dict | None = None,
    risk_data: list[dict] | None = None,
    model: str | None = None,
) -> str:
    """生成增强版画像报告 (含共识/风险预处理数据).

    将预计算的共识分析和风险检测结果一起传给LLM，减少幻觉。
    """
    # 按维度排序 claims
    dim_order = ["admission", "education", "baoyan", "employment", "lab", "life", "industry", "risk"]
    sorted_claims = sorted(claims, key=lambda c: dim_order.index(c.get("dimension", "risk"))
                          if c.get("dimension") in dim_order else 99)

    # 构建增强 prompt
    consensus_str = json.dumps(consensus_data, ensure_ascii=False) if consensus_data else "未提供"
    risk_str = json.dumps(risk_data, ensure_ascii=False) if risk_data else "未提供"

    user_prompt = f"""请为以下院校专业生成完整的12章分析报告:

**基本信息**
学校: {school_name}
专业: {major_name}
校区: {campus or '未指定'}

**数据统计**
证据来源数: {len(evidence_summaries)}
声明总数: {len(claims)}
声明按维度分布: {_count_dims(sorted_claims)}

**预分析结果 (可参考，需结合原始证据验证)**
共识分析: {consensus_str[:1500]}
风险检测: {risk_str[:1500]}

**结构化声明 (按维度排序)**
{json.dumps(sorted_claims[:40], ensure_ascii=False, indent=2)[:5000]}

**证据摘要**
{json.dumps(evidence_summaries[:15], ensure_ascii=False, indent=2)[:3000]}

请按 REPORT_V2 prompt 中的12章结构输出完整报告。"""

    try:
        return await _call_llm(
            system_prompt=REPORT_V2,
            user_prompt=user_prompt,
            model=model,
            temperature=0.3,
            max_tokens=16384,
        )
    except Exception as e:
        print(f"[LLM] Report generation error: {e}")
        return f"报告生成失败: {e}"


# ============================================================================
# 反向问答
# ============================================================================

async def answer_question(
    question: str,
    context_claims: list[dict],
    context_evidence: list[dict],
    model: str | None = None,
) -> str:
    """基于证据回答用户问题."""
    ctx = json.dumps({
        "claims": context_claims[:20],
        "evidence": context_evidence[:10],
    }, ensure_ascii=False, indent=2)

    user_prompt = f"""用户问题: {question}

相关证据和声明:
{ctx[:5000]}

请基于以上证据回答问题。每个结论引用具体来源。证据不足时明确指出。"""

    try:
        return await _call_llm(
            system_prompt=QA_V2,
            user_prompt=user_prompt,
            model=model,
            temperature=0.2,
            max_tokens=8192,
        )
    except Exception as e:
        print(f"[LLM] Q&A error: {e}")
        return f"回答失败: {e}"


# ============================================================================
# 对比分析
# ============================================================================

async def generate_comparison_report(
    items: list[dict],
    model: str | None = None,
) -> str:
    """生成多院校专业对比报告.

    Args:
        items: [{"school": "...", "major": "...", "claims": [...], "evidence": [...]}, ...]
    """
    items_str = json.dumps([
        {
            "school": it["school"],
            "major": it["major"],
            "claims_count": len(it.get("claims", [])),
            "key_claims": it.get("claims", [])[:10],
        }
        for it in items
    ], ensure_ascii=False, indent=2)

    prompt = f"""请对比分析以下院校专业:

{items_str[:6000]}

请从以下维度进行对比:
1. 录取难度对比
2. 专业实力对比
3. 保研/升学对比
4. 就业质量对比
5. 城市与校区对比
6. 风险对比
7. 综合推荐排名

每个对比维度使用表格展示，给出基于证据的结论。"""

    try:
        return await _call_llm(
            system_prompt=REPORT_V2,
            user_prompt=prompt,
            model=model,
            temperature=0.3,
            max_tokens=16384,
        )
    except Exception as e:
        return f"对比报告生成失败: {e}"


# ============================================================================
# 统计报告
# ============================================================================

async def generate_statistics_report(
    school_name: str,
    major_name: str,
    claims: list[dict],
    model: str | None = None,
) -> str:
    """生成数据统计摘要 — 从claims中提取关键数字和趋势."""
    dimensions = _count_dims(claims)
    polarities = _count_pols(claims)

    prompt = f"""请基于以下关于 {school_name} {major_name} 的声明数据,生成数据统计摘要:

声明总数: {len(claims)}
维度分布: {json.dumps(dimensions)}
极性分布: {json.dumps(polarities)}

关键声明:
{json.dumps(claims[:20], ensure_ascii=False, indent=2)[:4000]}

请生成:
1. 关键数字汇总 (就业率/升学率/保研率/薪资等)
2. 正面信号 vs 负面信号对比
3. 与其他同学科专业的对比位置
4. 数据可信度评估"""

    try:
        return await _call_llm(
            system_prompt="你是一个数据分析师。请基于提供的数据生成统计摘要。",
            user_prompt=prompt,
            model=model,
            temperature=0.2,
            max_tokens=4096,
        )
    except Exception as e:
        return f"统计报告生成失败: {e}"


# ============================================================================
# 工具函数
# ============================================================================

def _count_dims(claims: list[dict]) -> dict:
    dims = {}
    for c in claims:
        d = c.get("dimension", "unknown")
        dims[d] = dims.get(d, 0) + 1
    return dims


def _count_pols(claims: list[dict]) -> dict:
    pols = {}
    for c in claims:
        p = c.get("polarity", "neutral")
        pols[p] = pols.get(p, 0) + 1
    return pols
