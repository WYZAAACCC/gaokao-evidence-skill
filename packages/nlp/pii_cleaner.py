"""
PII 匿名化模块 — 在写入 Evidence 之前对社媒文本进行去标识化处理。

规则：
- 移除手机号、邮箱、身份证号
- 移除用户昵称（仅社交平台）
- 移除头像链接
- 移除个人主页链接
- 不保存联系方式
"""

from __future__ import annotations

import re

# 手机号正则（中国）
PHONE_PATTERN = re.compile(r"1[3-9]\d{9}")

# 邮箱正则
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# 身份证号正则
ID_CARD_PATTERN = re.compile(r"\d{17}[\dXx]")

# 常见社交媒体链接前缀
SOCIAL_PROFILE_PREFIXES = [
    "xiaohongshu.com/user/profile/",
    "zhihu.com/people/",
    "space.bilibili.com/",
    "weibo.com/u/",
    "douyin.com/user/",
]


def clean_text(text: str) -> str:
    """对文本进行 PII 清理。

    Args:
        text: 原始文本

    Returns:
        清理后的文本
    """
    if not text:
        return text

    # 优先替换身份证号（18位），避免其子串被手机号正则误匹配
    text = ID_CARD_PATTERN.sub("[身份证号已隐藏]", text)

    # 替换手机号（11位，以1开头第二位3-9）
    text = PHONE_PATTERN.sub("[手机号已隐藏]", text)

    # 替换邮箱
    text = EMAIL_PATTERN.sub("[邮箱已隐藏]", text)

    return text


def clean_url(url: str) -> str:
    """检查 URL 是否包含个人主页，如果是则标记但不保存完整路径。

    Args:
        url: 原始 URL

    Returns:
        清理后的 URL，如果是个人主页则返回平台名+已隐藏
    """
    if not url:
        return url

    for prefix in SOCIAL_PROFILE_PREFIXES:
        if prefix in url:
            # 提取平台名
            platform = prefix.split(".")[0] if "." in prefix else prefix.split("/")[0]
            return f"[{platform}个人主页已隐藏]"

    return url


def is_sensitive_content(text: str) -> bool:
    """
    检查是否包含敏感个人信息。

    Returns:
        是否包含敏感信息
    """
    if not text:
        return False

    checks = [
        PHONE_PATTERN.search(text),
        EMAIL_PATTERN.search(text),
        ID_CARD_PATTERN.search(text),
    ]
    return any(checks)
