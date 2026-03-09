from __future__ import annotations

import re
from dataclasses import dataclass


_SENSITIVE_PATTERNS = [
    re.compile(r"(验证码|sms|otp)", re.IGNORECASE),
    re.compile(r"(cvv|cvc|卡号|银行卡)", re.IGNORECASE),
    re.compile(r"(私钥|seed|mnemonic)", re.IGNORECASE),
    re.compile(r"\b(usdt|btc|eth)\b", re.IGNORECASE),
]


def moderate_text(text: str) -> tuple[bool, str | None]:
    """Return (allowed, reason)."""
    for pat in _SENSITIVE_PATTERNS:
        if pat.search(text or ""):
            return False, "内容包含高风险敏感信息"
    return True, None


def suggest_tags(title: str, body: str) -> list[str]:
    text = f"{title} {body}".lower()
    tags: list[str] = []
    if any(k in text for k in ["吃", "饭", "dinner", "lunch"]):
        tags.append("eat")
    if any(k in text for k in ["coffee", "咖啡"]):
        tags.append("coffee")
    if any(k in text for k in ["画", "art", "project", "创作"]):
        tags.append("art")
    if any(k in text for k in ["丢", "lost", "找不到", "手机", "钱包", "卡包"]):
        tags.append("lost")
    if any(k in text for k in ["捡", "found", "拾到"]):
        tags.append("found")
    if any(k in text for k in ["求助", "help", "互助"]):
        tags.append("help")
    # de-dup while keeping order
    seen = set()
    out: list[str] = []
    for t in tags:
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out


@dataclass(frozen=True)
class SimilaritySuggestion:
    post_id: str
    score: float


def _tokenize(s: str) -> set[str]:
    s = re.sub(r"\s+", " ", s.strip().lower())
    # very small tokenizer: keep CJK chars & latin words
    tokens = set(re.findall(r"[\u4e00-\u9fff]{1,2}|[a-z0-9]{2,}", s))
    return {t for t in tokens if t}


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    uni = len(ta | tb)
    return inter / uni if uni else 0.0


def public_hint_agent(prefs: list[str], items: list[dict]) -> list[dict]:
    """
    轻量“agent”：从公共信息池里按偏好挑选，并生成 1 行提示。
    返回元素结构：{category, tip, item:{title,url,source,publishedAt}}
    """
    allowed = {"outdoor", "health", "entertainment", "fashion", "tech"}
    p = [x for x in (prefs or []) if str(x) in allowed]
    if not p:
        p = ["outdoor", "health"]

    kw = {
        "outdoor": [
            "weather",
            "storm",
            "climate",
            "wildfire",
            "flood",
            "heat",
            "rain",
            "snow",
            "typhoon",
            "hurricane",
            "earthquake",
            "天气",
            "气象",
            "暴雨",
            "台风",
            "高温",
            "寒潮",
            "地震",
            "洪水",
            "山火",
            "灾害",
        ],
        "health": [
            "flu",
            "influenza",
            "outbreak",
            "disease",
            "virus",
            "who",
            "health",
            "vaccine",
            "流感",
            "疫情",
            "传染",
            "卫生",
            "疫苗",
        ],
        "entertainment": ["entertainment", "music", "film", "movie", "tv", "celebrity", "娱乐", "影视", "电影", "综艺"],
        "fashion": ["fashion", "style", "runway", "luxury", "时尚", "穿搭", "秀场", "奢侈"],
        "tech": ["ai", "chip", "tech", "space", "nasa", "rocket", "startup", "科技", "航天", "芯片", "人工智能"],
    }
    label = {
        "outdoor": "户外/天气",
        "health": "健康",
        "entertainment": "娱乐",
        "fashion": "时尚",
        "tech": "科技",
    }

    def score(cat: str, it: dict) -> int:
        t = f"{it.get('title','')} {it.get('quote','')} {it.get('source','')}".lower()
        s = 0
        for k in kw.get(cat, []):
            kk = str(k).lower()
            if kk and kk in t:
                s += 2
        return s

    out: list[dict] = []
    pool = items or []
    for cat in p:
        best = None
        best_s = -1
        for it in pool:
            s = score(cat, it)
            if s > best_s:
                best_s = s
                best = it
        if best and best_s > 0:
            tip = f"【{label.get(cat, cat)}】{best.get('title','')}"
        else:
            best = (pool[0] if pool else None)
            tip = f"【{label.get(cat, cat)}】暂无明确匹配，给你一条最新公共信息"
        if best:
            out.append(
                {
                    "category": cat,
                    "tip": tip[:220],
                    "item": {
                        "title": str(best.get("title") or "")[:240],
                        "url": str(best.get("url") or "")[:600],
                        "source": str(best.get("source") or "")[:80],
                        "publishedAt": str(best.get("publishedAt") or ""),
                    },
                }
            )
        if len(out) >= 4:
            break
    return out

