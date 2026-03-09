from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import email.utils
import json
import hashlib
import html
import math
import os
import re
import socket
import io
import zipfile
from pathlib import Path
import secrets
from typing import Any, Literal
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from sqlalchemy import select, or_
from starlette.applications import Starlette
from starlette.datastructures import FormData, UploadFile
from starlette.endpoints import WebSocketEndpoint
from starlette.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.ai import jaccard, moderate_text, suggest_tags, public_hint_agent
from app.db import make_engine, make_sessionmaker, session_scope
from app.models import (
    Base,
    BillboardItem,
    CardEntry,
    Creator,
    EmergencyCase,
    EmergencyUpdate,
    PresenceSetting,
    InviteProof,
    LegalTicket,
    Order,
    PersonIdentity,
    PersonPrivacy,
    Post,
    PlanNote,
    RewardNote,
    RealNameRecord,
    SafetyReport,
    SafetyOpinion,
    SafetyOpinionVote,
    MeetInvite,
    MeetInviteComplaint,
    NextQuestion,
    NextQuestionReply,
    SellListing,
    SupportListing,
    Tip,
    UserPreference,
    UserCard,
    Venue,
    VenueGeo,
    Work,
)

DB_PATH = "abang.sqlite3"
engine = make_engine(DB_PATH)
SessionLocal = make_sessionmaker(engine)

UPLOAD_DIR = Path("app/static/uploads").resolve()


@asynccontextmanager
async def lifespan(_: Starlette):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # lightweight migration: add PersonPrivacy.visibility if missing
        try:
            res = await conn.exec_driver_sql("PRAGMA table_info(person_privacy)")
            cols = [str(r[1]) for r in res.fetchall()]  # (cid, name, type, notnull, dflt_value, pk)
            if "visibility" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE person_privacy ADD COLUMN visibility TEXT NOT NULL DEFAULT 'public'"
                )
            # backfill (older rows using is_public)
            await conn.exec_driver_sql(
                "UPDATE person_privacy SET visibility='private' WHERE is_public=0 AND (visibility IS NULL OR visibility='public')"
            )
        except Exception:
            pass

        # lightweight migration: add Post.scope if missing
        try:
            res = await conn.exec_driver_sql("PRAGMA table_info(posts)")
            cols = [str(r[1]) for r in res.fetchall()]
            if "scope" not in cols:
                await conn.exec_driver_sql("ALTER TABLE posts ADD COLUMN scope TEXT NOT NULL DEFAULT 'keep'")
            await conn.exec_driver_sql("UPDATE posts SET scope='keep' WHERE scope IS NULL OR scope=''")
        except Exception:
            pass

        # lightweight migration: add SafetyReport.evidence_path if missing
        try:
            res = await conn.exec_driver_sql("PRAGMA table_info(safety_reports)")
            cols = [str(r[1]) for r in res.fetchall()]
            if "evidence_path" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE safety_reports ADD COLUMN evidence_path TEXT NOT NULL DEFAULT ''"
                )
            if "user_key" not in cols:
                await conn.exec_driver_sql("ALTER TABLE safety_reports ADD COLUMN user_key TEXT NOT NULL DEFAULT ''")
            if "publish_request" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE safety_reports ADD COLUMN publish_request INTEGER NOT NULL DEFAULT 0"
                )
            if "author_display" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE safety_reports ADD COLUMN author_display TEXT NOT NULL DEFAULT 'anon'"
                )
        except Exception:
            pass

        # lightweight migration: emergency_cases add reason/risk/start_at/end_at if missing
        try:
            res = await conn.exec_driver_sql("PRAGMA table_info(emergency_cases)")
            cols = [str(r[1]) for r in res.fetchall()]
            if "reason" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE emergency_cases ADD COLUMN reason TEXT NOT NULL DEFAULT 'witness'"
                )
            if "risk_level" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE emergency_cases ADD COLUMN risk_level TEXT NOT NULL DEFAULT 'medium'"
                )
            if "start_at" not in cols:
                await conn.exec_driver_sql("ALTER TABLE emergency_cases ADD COLUMN start_at TEXT NOT NULL DEFAULT ''")
            if "end_at" not in cols:
                await conn.exec_driver_sql("ALTER TABLE emergency_cases ADD COLUMN end_at TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass

        # lightweight migration: emergency_updates add photo_sha256 if missing
        try:
            res = await conn.exec_driver_sql("PRAGMA table_info(emergency_updates)")
            cols = [str(r[1]) for r in res.fetchall()]
            if "photo_sha256" not in cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE emergency_updates ADD COLUMN photo_sha256 TEXT NOT NULL DEFAULT ''"
                )
        except Exception:
            pass

        # lightweight migration: RealNameRecord table (create_all covers new table)
        try:
            await conn.exec_driver_sql("SELECT 1")
        except Exception:
            pass

        # lightweight migration: PlanNote table exists via create_all; keep here for future columns
        try:
            await conn.exec_driver_sql("SELECT 1")
        except Exception:
            pass

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    async with session_scope(SessionLocal) as s:
        # Seed/Upsert venues (demo values; safe to run multiple times)
        venue_seed = [
            Venue(id="v_hk_001", name="Central_ExampleCafe", city="HongKong"),
            Venue(id="v_us_001", name="SF_ExampleDiner", city="SanFrancisco"),
            Venue(id="v_cn_001", name="SZ_ExampleMall", city="Shenzhen"),
            Venue(id="v_cn_sh_001", name="SH_ExampleFoodCourt", city="Shanghai"),
            Venue(id="v_cn_nj_001", name="NJ_ExampleNoodleShop", city="Nanjing"),
        ]
        for v in venue_seed:
            res = await s.execute(select(Venue).where(Venue.id == v.id))
            existing = res.scalar_one_or_none()
            if not existing:
                s.add(v)

        # Seed/Upsert venue geofence (demo values; safe to run multiple times)
        geo_seed = [
            # Central, Hong Kong (approx)
            ("v_hk_001", 22.2819, 114.1589, 400),
            # San Francisco (approx downtown)
            ("v_us_001", 37.7749, -122.4194, 800),
            # Shenzhen (approx city center)
            ("v_cn_001", 22.5431, 114.0579, 800),
            # Shanghai (People's Square approx)
            ("v_cn_sh_001", 31.2304, 121.4737, 900),
            # Nanjing (Xinjiekou approx)
            ("v_cn_nj_001", 32.0603, 118.7969, 1200),
        ]
        now = _now()
        for venue_id, lat, lng, radius_m in geo_seed:
            res = await s.execute(select(VenueGeo).where(VenueGeo.venue_id == venue_id))
            existing = res.scalar_one_or_none()
            if not existing:
                s.add(VenueGeo(venue_id=venue_id, lat=lat, lng=lng, radius_m=radius_m, updated_at=now))

        # Seed posts if empty
        res = await s.execute(select(Post.id).limit(1))
        if res.first() is None:
            now = _now()
            s.add_all(
                [
                    Post(
                        id="p1",
                        type="invite",
                        scope="keep",
                        title="在Central一起吃饭",
                        body="现在在附近，想找1-2个人一起吃饭聊天。",
                        venue_id="v_hk_001",
                        start_at=now - timedelta(minutes=10),
                        end_at=now + timedelta(hours=1),
                        tags="eat,help",
                        created_at=now,
                    ),
                    Post(
                        id="p2",
                        type="lost",
                        scope="keep",
                        title="手机丢了（黑色壳）",
                        body="大概在咖啡店门口附近丢的，壳子上有贴纸。",
                        venue_id="v_hk_001",
                        start_at=now - timedelta(hours=1),
                        end_at=now + timedelta(hours=6),
                        tags="lost",
                        created_at=now,
                    ),
                ]
            )

        # Seed creators/works if empty
        res = await s.execute(select(Creator.id).limit(1))
        if res.first() is None:
            now = _now()
            s.add_all(
                [
                    Creator(
                        id="c1",
                        display_name="学生_小一",
                        story="我在读书，白天上课，晚上画画。想靠作品把生活费补上来，也想把公益互动画成系列。",
                        recognition="candidate",
                        created_at=now,
                    ),
                    Creator(
                        id="c2",
                        display_name="街头摄影_小岚",
                        story="手机拍照记录城市角落。希望有人支持我继续拍下去，做一套‘同场所故事卡’。",
                        recognition="none",
                        created_at=now,
                    ),
                ]
            )
            s.add_all(
                [
                    Work(
                        id="w1",
                        creator_id="c1",
                        title="作品卡 1：湖水绿的晚餐搭子",
                        description="灵感来自同场所的Coffee Chat。",
                        media_hint="image_placeholder",
                        created_at=now,
                    ),
                    Work(
                        id="w2",
                        creator_id="c1",
                        title="作品卡 2：失物招领的温柔",
                        description="每一次归还都是一次文明的修复。",
                        media_hint="image_placeholder",
                        created_at=now,
                    ),
                    Work(
                        id="w3",
                        creator_id="c2",
                        title="照片卡：街角咖啡杯",
                        description="手机随手拍，想做成卡包系列。",
                        media_hint="photo_placeholder",
                        created_at=now,
                    ),
                ]
            )

    # optional: daily billboard refresh (disabled by default)
    auto = str(os.environ.get("BILLBOARD_AUTO_REFRESH", "") or "").strip().lower()
    task: asyncio.Task | None = None
    if auto in ("1", "on", "true", "yes"):
        task = asyncio.create_task(_billboard_daemon())

    yield

    if task:
        task.cancel()
        try:
            await task
        except Exception:
            pass


templates = Jinja2Templates(directory="app/templates")
templates.env.auto_reload = True
try:
    templates.env.cache.clear()
except Exception:
    pass


# ---- Shared helpers ----

PostType = Literal["invite", "lost", "found"]

DOCS_DIR = Path("docs").resolve()


def _now() -> datetime:
    return datetime.utcnow()


def _today_str() -> str:
    return _now().date().isoformat()


def _lan_ipv4() -> str:
    """
    Best-effort local LAN IPv4 for share links/QR.
    Avoids placeholders like "你的ip" causing ERR_NAME_NOT_RESOLVED.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # no packets are actually sent; used to pick outbound interface
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        if ip and re.fullmatch(r"\d+\.\d+\.\d+\.\d+", ip or ""):
            return ip
    except Exception:
        pass
    return "127.0.0.1"


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    if not text:
        return ""
    t = html.unescape(text)
    t = _TAG_RE.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _fetch_bytes(url: str, timeout_s: int = 8) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AhelpisBillboard/1.0 (+https://ahelpis.example)",
            "Accept": "application/xml, text/xml, application/rss+xml, application/atom+xml, */*",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return resp.read()


def _parse_feed(xml_bytes: bytes) -> list[dict[str, Any]]:
    """
    Minimal RSS2/Atom parser without extra dependencies.
    Returns: [{title,url,summary,publishedAt,source}]
    """
    try:
        raw = xml_bytes.decode("utf-8", errors="ignore")
    except Exception:
        raw = ""
    raw = raw.lstrip("\ufeff").strip()
    if not raw:
        return []
    try:
        root = ET.fromstring(raw)
    except Exception:
        return []

    def text_of(el: Any) -> str:
        if el is None:
            return ""
        return str(el.text or "").strip()

    out: list[dict[str, Any]] = []
    tag = str(root.tag or "")
    is_rss = ("rss" in tag.lower()) or (root.find("channel") is not None)
    if is_rss:
        ch = root.find("channel") or root.find("./channel")
        src = _strip_html(text_of(ch.find("title")) if ch is not None else "")
        items = (ch.findall("item") if ch is not None else []) or root.findall(".//item")
        for it in items[:30]:
            title = _strip_html(text_of(it.find("title")))
            url = _strip_html(text_of(it.find("link")))
            summary = _strip_html(text_of(it.find("description")) or text_of(it.find("summary")))
            pub_raw = _strip_html(text_of(it.find("pubDate")))
            published = _now()
            if pub_raw:
                try:
                    published = email.utils.parsedate_to_datetime(pub_raw).replace(tzinfo=None)
                except Exception:
                    published = _now()
            if title and url:
                out.append({"title": title, "url": url, "summary": summary, "publishedAt": published, "source": src})
        return out

    # Atom
    ns = ""
    if tag.startswith("{") and "}" in tag:
        ns = tag.split("}")[0] + "}"
    src = _strip_html(text_of(root.find(f"{ns}title")))
    entries = root.findall(f"{ns}entry")
    for e in entries[:30]:
        title = _strip_html(text_of(e.find(f"{ns}title")))
        # find alternate link
        url = ""
        for lk in e.findall(f"{ns}link"):
            rel = (lk.attrib.get("rel") or "alternate").lower()
            href = (lk.attrib.get("href") or "").strip()
            if rel == "alternate" and href:
                url = href
                break
            if not url and href:
                url = href
        summary = _strip_html(text_of(e.find(f"{ns}summary")) or text_of(e.find(f"{ns}content")))
        pub_raw = _strip_html(text_of(e.find(f"{ns}published")) or text_of(e.find(f"{ns}updated")))
        published = _now()
        if pub_raw:
            try:
                published = datetime.fromisoformat(pub_raw.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                published = _now()
        if title and url:
            out.append({"title": title, "url": url, "summary": summary, "publishedAt": published, "source": src})
    return out


def _billboard_feeds(mode: str) -> list[tuple[str, str]]:
    m = str(mode or "global").strip().lower()
    if m == "hk":
        return [
            ("HK Gov", "https://www.info.gov.hk/gia/rss/general.xml"),
            ("HKO Weather", "https://rss.weather.gov.hk/rss/CurrentWeather_uc.xml"),
            ("HKO Warnings", "https://rss.weather.gov.hk/rss/WeatherWarningSummaryv2.xml"),
            ("UN News", "https://news.un.org/feed/subscribe/en/news/all/rss.xml"),
        ]
    if m == "cn":
        return [
            ("ChinaDaily CN", "https://www.chinadaily.com.cn/rss/china_rss.xml"),
            ("ChinaDaily World", "https://www.chinadaily.com.cn/rss/world_rss.xml"),
            ("UN News", "https://news.un.org/feed/subscribe/en/news/all/rss.xml"),
        ]
    return [
        ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("UN News", "https://news.un.org/feed/subscribe/en/news/all/rss.xml"),
        ("WHO", "https://www.who.int/rss-feeds/news-english.xml"),
        ("NASA", "https://www.nasa.gov/rss/dyn/breaking_news.rss"),
    ]


async def _refresh_billboard(mode: str, day: str | None = None, limit: int = 10) -> dict[str, Any]:
    day_str = day or _today_str()
    m = str(mode or "global").strip().lower()
    feeds = _billboard_feeds(m)

    # load existing urls for de-dup
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(BillboardItem.url).where(BillboardItem.mode == m, BillboardItem.day == day_str))
        existing_urls = {str(x[0] or "") for x in (res.all() or [])}
        res = await s.execute(
            select(BillboardItem.id).where(BillboardItem.mode == m, BillboardItem.day == day_str).order_by(BillboardItem.id.desc()).limit(1)
        )
        last = res.first()
        next_num = 1
        if last and isinstance(last[0], str) and "_" in last[0]:
            try:
                next_num = int(last[0].split("_")[-1]) + 1
            except Exception:
                next_num = 1

    items: list[dict[str, Any]] = []
    errors: list[str] = []
    for src_name, url in feeds:
        try:
            b = _fetch_bytes(url, timeout_s=8)
            parsed = _parse_feed(b)
            for it in parsed:
                it["source"] = it.get("source") or src_name
            items.extend(parsed)
        except urllib.error.URLError as e:
            errors.append(f"{src_name}: {getattr(e, 'reason', e)}")
        except Exception as e:
            errors.append(f"{src_name}: {e}")

    # sort + de-dup
    items.sort(key=lambda x: x.get("publishedAt") or _now(), reverse=True)
    picked: list[dict[str, Any]] = []
    seen = set(existing_urls)
    for it in items:
        u = str(it.get("url") or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        picked.append(it)
        if len(picked) >= max(3, min(20, int(limit or 10))):
            break

    now = _now()
    created = 0
    async with session_scope(SessionLocal) as s:
        for it in picked:
            bbid = f"bb{day_str.replace('-', '')}_{next_num}"
            next_num += 1
            title = str(it.get("title") or "").strip()[:240]
            url = str(it.get("url") or "").strip()[:600]
            src = str(it.get("source") or "").strip()[:80]
            quote = str(it.get("summary") or "").strip()
            quote = quote[:600]
            published = it.get("publishedAt") if isinstance(it.get("publishedAt"), datetime) else now
            s.add(
                BillboardItem(
                    id=bbid,
                    mode=m,
                    day=day_str,
                    title=title,
                    source=src,
                    url=url,
                    quote=quote,
                    ai_note="",
                    published_at=published,
                    created_at=now,
                )
            )
            created += 1
    return {"mode": m, "day": day_str, "created": created, "errors": errors[:6]}


async def _billboard_daemon() -> None:
    # refresh once on boot then every 24h
    try:
        await _refresh_billboard("global", limit=10)
        await _refresh_billboard("cn", limit=10)
        await _refresh_billboard("hk", limit=6)
    except Exception:
        pass
    while True:
        await asyncio.sleep(24 * 3600)
        try:
            await _refresh_billboard("global", limit=10)
            await _refresh_billboard("cn", limit=10)
            await _refresh_billboard("hk", limit=6)
        except Exception:
            pass


def _user_key(request: Request) -> str:
    return getattr(request.state, "user_key", "") or "anon"

def _mode(request: Request) -> str:
    return getattr(request.state, "mode", "") or "global"


def _norm_prefs(v: Any) -> list[str]:
    """
    Normalize preferences list from user input.
    """
    allowed = {"outdoor", "health", "entertainment", "fashion", "tech"}
    prefs: list[str] = []
    if isinstance(v, str):
        prefs = [x.strip().lower() for x in v.split(",") if x.strip()]
    elif isinstance(v, list):
        prefs = [str(x).strip().lower() for x in v if str(x).strip()]
    prefs = [x for x in prefs if x in allowed]
    # de-dup keep order
    seen = set()
    out: list[str] = []
    for x in prefs:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out[:6]


async def _get_user_prefs(user_key: str) -> list[str]:
    if not user_key:
        return []
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(UserPreference).where(UserPreference.user_key == user_key))
        row = res.scalar_one_or_none()
    if not row:
        return []
    return _norm_prefs(getattr(row, "prefs", "") or "")


async def api_prefs_set(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("prefs_set", ip, limit=80, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_json")
    prefs = _norm_prefs(payload.get("prefs"))
    uk = _user_key(request)
    now = _now()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(UserPreference).where(UserPreference.user_key == uk))
        row = res.scalar_one_or_none()
        if row:
            row.prefs = ",".join(prefs)
            row.updated_at = now
        else:
            s.add(UserPreference(user_key=uk, prefs=",".join(prefs), updated_at=now))
    return JSONResponse({"ok": True, "prefs": prefs})


async def api_public_hints(request: Request) -> Response:
    mode = _mode(request)
    uk = _user_key(request)
    prefs = await _get_user_prefs(uk)
    day = _today_str()
    items: list[dict[str, Any]] = []
    async with session_scope(SessionLocal) as s:
        q = (
            select(BillboardItem)
            .where(BillboardItem.mode == mode, BillboardItem.day == day)
            .order_by(BillboardItem.published_at.desc())
            .limit(30)
        )
        res = await s.execute(q)
        rows = res.scalars().all()
        if not rows:
            try:
                y = (_now().date() - timedelta(days=1)).isoformat()
            except Exception:
                y = day
            q = (
                select(BillboardItem)
                .where(BillboardItem.mode == mode, BillboardItem.day == y)
                .order_by(BillboardItem.published_at.desc())
                .limit(30)
            )
            res = await s.execute(q)
            rows = res.scalars().all()
            day = y
        for r in rows:
            items.append(
                {
                    "title": r.title,
                    "source": r.source,
                    "url": r.url,
                    "quote": r.quote,
                    "publishedAt": r.published_at.isoformat() if getattr(r, "published_at", None) else "",
                }
            )

    hints = public_hint_agent(prefs, items)
    return JSONResponse({"mode": mode, "day": day, "prefs": prefs, "hints": hints})


def _new_id(prefix: str) -> str:
    d = _today_str().replace("-", "")
    tok = secrets.token_hex(3)
    return f"{prefix}{d}_{tok}"


def _save_upload_image(raw: bytes, content_type: str, prefix: str, ref: str) -> str:
    if content_type not in ("image/jpeg", "image/jpg", "image/png"):
        raise HTTPException(status_code=400, detail="invalid_photo_type")
    if not raw or len(raw) > 2_800_000:
        raise HTTPException(status_code=400, detail="photo_too_large")
    ext = "jpg" if content_type.startswith("image/j") else "png"
    tok = secrets.token_hex(3)
    fname = f"{prefix}_{ref}_{tok}.{ext}"
    (UPLOAD_DIR / fname).write_bytes(raw)
    return f"uploads/{fname}"


def _save_upload_evidence(raw: bytes, content_type: str, filename: str, prefix: str, ref: str) -> str:
    """
    Save optional evidence files for reports: images / pdf / ppt / pptx.
    """
    ct = (content_type or "").strip().lower()
    name = str(filename or "").strip().lower()
    # tolerate generic upload content-type
    if ct in ("application/octet-stream", "binary/octet-stream", ""):
        ct = ""

    # Determine ext by content-type or filename
    ext = ""
    if ct in ("image/jpeg", "image/jpg"):
        ext = "jpg"
    elif ct == "image/png":
        ext = "png"
    elif ct == "application/pdf" or name.endswith(".pdf"):
        ext = "pdf"
    elif ct == "application/vnd.openxmlformats-officedocument.presentationml.presentation" or name.endswith(".pptx"):
        ext = "pptx"
    elif ct == "application/vnd.ms-powerpoint" or name.endswith(".ppt"):
        ext = "ppt"

    if ext not in ("jpg", "png", "pdf", "ppt", "pptx"):
        raise HTTPException(status_code=400, detail="invalid_evidence_type")

    # size limits
    if not raw:
        raise HTTPException(status_code=400, detail="empty_evidence")
    max_bytes = 2_800_000 if ext in ("jpg", "png") else 8_000_000
    if len(raw) > max_bytes:
        raise HTTPException(status_code=400, detail="evidence_too_large")

    tok = secrets.token_hex(3)
    safe_ref = re.sub(r"[^a-zA-Z0-9]+", "", str(ref or ""))[:16] or "r"
    fname = f"{prefix}_{safe_ref}_{tok}.{ext}"
    (UPLOAD_DIR / fname).write_bytes(raw)
    return f"uploads/{fname}"


async def emergency_list(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    async with session_scope(SessionLocal) as s:
        res = await s.execute(
            select(EmergencyCase)
            .where(EmergencyCase.venue_id == venue_obj["id"])
            .order_by(EmergencyCase.created_at.desc())
            .limit(40)
        )
        cases = res.scalars().all()
        # prefetch updates (recent)
        ids = [c.id for c in cases]
        upd_map: dict[str, list[EmergencyUpdate]] = {cid: [] for cid in ids}
        if ids:
            res = await s.execute(
                select(EmergencyUpdate)
                .where(EmergencyUpdate.case_id.in_(ids))
                .order_by(EmergencyUpdate.created_at.desc())
                .limit(120)
            )
            ups = res.scalars().all()
            for u in ups:
                if u.case_id in upd_map and len(upd_map[u.case_id]) < 3:
                    upd_map[u.case_id].append(u)
    view = [
        {
            "id": c.id,
            "kind": c.kind,
            "title": _redact_public_text(c.title),
            "status": c.status,
            "createdAt": c.created_at.isoformat(),
            "desc": (
                _redact_public_text(str(c.description or "").strip())[:140]
                + ("…" if str(c.description or "").strip()[140:] else "")
            ),
            "recent": [
                {
                    "message": (
                        _redact_public_text(str(u.message or "").strip())[:120]
                        + ("…" if str(u.message or "").strip()[120:] else "")
                    ),
                    "hasPhoto": bool(u.photo_path),
                    "createdAt": u.created_at.isoformat(),
                }
                for u in (upd_map.get(c.id) or [])
            ],
        }
        for c in cases
    ]
    return templates.TemplateResponse(
        request,
        "emergency.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request), "cases": view},
    )


async def emergency_new(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    return templates.TemplateResponse(
        request,
        "emergency_new.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request)},
    )


async def emergency_new_post(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("emergency_new", ip, limit=12, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    form: FormData = await request.form()
    venue_id = str(form.get("venueId") or "").strip()
    if not venue_id:
        raise HTTPException(status_code=400, detail="venueId_required")
    kind = str(form.get("kind") or "missing").strip().lower()
    if kind not in ("missing_child", "missing_elder", "missing"):
        kind = "missing"
    reason_key = str(form.get("reason") or "witness").strip().lower()
    if reason_key not in ("witness", "self", "proxy", "online_lead"):
        reason_key = "witness"
    risk_level = str(form.get("risk") or "medium").strip().lower()
    if risk_level not in ("low", "medium", "high"):
        risk_level = "medium"
    title = str(form.get("title") or "").strip()[:160]
    if not title:
        raise HTTPException(status_code=400, detail="title_required")
    desc = str(form.get("description") or "").strip()
    if len(desc) > 1200:
        desc = desc[:1200]
    ok, reason = moderate_text(f"{title}\n{desc}")
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    photo_path = ""
    photo_sha = ""
    photo = form.get("photo")
    if isinstance(photo, UploadFile):
        raw = await photo.read()
        photo_path = _save_upload_image(raw, (photo.content_type or ""), "emg_case", title[:12].replace(" ", "") or "case")
        photo_sha = _sha256_hex(raw)

    uk = _user_key(request)
    now = _now()
    start_at = now.isoformat()
    end_at = (now + timedelta(hours=1)).isoformat()
    case_id = _new_id("ec")
    upd_id = _new_id("eu")
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(Venue).where(Venue.id == venue_id))
        v = res.scalar_one_or_none()
        if not v:
            raise HTTPException(status_code=404, detail="venue_not_found")
        s.add(
            EmergencyCase(
                id=case_id,
                venue_id=venue_id,
                user_key=uk,
                kind=kind,
                reason=reason_key,
                risk_level=risk_level,
                title=title,
                description=desc,
                status="open",
                start_at=start_at,
                end_at=end_at,
                created_at=now,
            )
        )
        # create first update as seed
        seed_msg = desc or "（求助发起）"
        s.add(
            EmergencyUpdate(
                id=upd_id,
                case_id=case_id,
                user_key=uk,
                message=seed_msg,
                photo_path=photo_path,
                photo_sha256=photo_sha,
                created_at=now,
            )
        )
    return RedirectResponse(url=f"/emergency/{case_id}?venue={venue_id}", status_code=303)


async def emergency_case(request: Request) -> Response:
    case_id = request.path_params["caseId"]
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(EmergencyCase).where(EmergencyCase.id == case_id))
        c = res.scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail="not_found")
        res = await s.execute(
            select(EmergencyUpdate)
            .where(EmergencyUpdate.case_id == case_id)
            .order_by(EmergencyUpdate.created_at.desc())
            .limit(120)
        )
        ups = res.scalars().all()
    viewer_uk = _user_key(request)
    can_view_evidence = bool(viewer_uk and (viewer_uk == getattr(c, "user_key", "")))
    case_view = {
        "id": c.id,
        "venueId": c.venue_id,
        "kind": c.kind,
        "reason": getattr(c, "reason", "witness"),
        "risk": getattr(c, "risk_level", "medium"),
        "title": (c.title if can_view_evidence else _redact_public_text(c.title)),
        "description": (c.description if can_view_evidence else _redact_public_text(c.description)),
        "status": c.status,
        "createdAt": c.created_at.isoformat(),
    }
    updates = [
        {
            "id": u.id,
            "message": (_redact_public_text(u.message) if not can_view_evidence else u.message),
            "photoUrl": ((f"/static/{u.photo_path}") if (can_view_evidence and u.photo_path) else ""),
            "hasPhoto": bool(u.photo_path),
            "createdAt": u.created_at.isoformat(),
        }
        for u in ups
    ]
    return templates.TemplateResponse(
        request,
        "emergency_case.html",
        {
            "venues": venues,
            "venue": venue_obj,
            "mode": _mode(request),
            "case": case_view,
            "updates": updates,
            "canViewEvidence": can_view_evidence,
        },
    )


async def emergency_update_post(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("emergency_update", ip, limit=80, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    case_id = request.path_params["caseId"]
    form: FormData = await request.form()
    msg = str(form.get("message") or "").strip()
    if len(msg) > 1200:
        msg = msg[:1200]
    ok, reason = moderate_text(msg)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    photo_path = ""
    photo_sha = ""
    photo = form.get("photo")
    if isinstance(photo, UploadFile):
        raw = await photo.read()
        photo_path = _save_upload_image(raw, (photo.content_type or ""), "emg_upd", case_id[-8:])
        photo_sha = _sha256_hex(raw)
    if not msg and not photo_path:
        raise HTTPException(status_code=400, detail="message_or_photo_required")
    uk = _user_key(request)
    now = _now()
    upd_id = _new_id("eu")
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(EmergencyCase).where(EmergencyCase.id == case_id))
        c = res.scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail="not_found")
        s.add(
            EmergencyUpdate(
                id=upd_id,
                case_id=case_id,
                user_key=uk,
                message=msg,
                photo_path=photo_path,
                photo_sha256=photo_sha,
                created_at=now,
            )
        )
    # keep venue in url if provided
    venue_id = str(form.get("venueId") or "").strip()
    qp = f"?venue={venue_id}" if venue_id else ""
    return RedirectResponse(url=f"/emergency/{case_id}{qp}", status_code=303)


async def emergency_export(request: Request) -> Response:
    """
    导出“官方数据包”（zip）：case.json + hash.txt + attachments/
    Demo 规则：仅事件发起者可导出。
    """
    case_id = request.path_params["caseId"]
    uk = _user_key(request)
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(EmergencyCase).where(EmergencyCase.id == case_id))
        c = res.scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail="not_found")
        if str(getattr(c, "user_key", "") or "") != str(uk or ""):
            raise HTTPException(status_code=403, detail="forbidden")
        res = await s.execute(select(Venue).where(Venue.id == c.venue_id))
        v = res.scalar_one_or_none()
        res = await s.execute(
            select(EmergencyUpdate)
            .where(EmergencyUpdate.case_id == case_id)
            .order_by(EmergencyUpdate.created_at.asc())
            .limit(240)
        )
        ups = res.scalars().all()
        res = await s.execute(select(RealNameRecord.user_key).where(RealNameRecord.user_key == uk))
        has_realname = (res.first() is not None)

    venue_label = f"{v.name} · {v.city}" if v else str(c.venue_id)
    now = _now()
    start_at = str(getattr(c, "start_at", "") or "").strip() or (getattr(c, "created_at", None) or now).isoformat()
    end_at = str(getattr(c, "end_at", "") or "").strip()
    if not end_at:
        try:
            base = getattr(c, "created_at", None) or now
            end_at = (base + timedelta(hours=1)).isoformat()
        except Exception:
            end_at = now.isoformat()
    payload: dict[str, Any] = {
        "schemaVersion": "1.0",
        "generatedAt": now.isoformat(),
        "app": {"name": "Universal", "build": "demo"},
        "case": {
            "caseId": c.id,
            "type": str(getattr(c, "kind", "missing") or "missing"),
            "reason": str(getattr(c, "reason", "witness") or "witness"),
            "status": str(getattr(c, "status", "open") or "open"),
            "timeWindow": {"startAt": start_at, "endAt": end_at},
            "location": {
                "country": ("CN" if _mode(request) == "cn" else ""),
                "venueId": str(c.venue_id),
                "venueLabel": venue_label,
                "geoPolicy": "NO_GPS_STORED",
            },
            "summary": _redact_public_text(str(getattr(c, "title", "") or ""))[:240],
            "details": {
                "structured": {"riskLevel": str(getattr(c, "risk_level", "medium") or "medium")},
                "freeText": str(getattr(c, "description", "") or ""),
            },
        },
        "evidence": {"items": [], "onSiteVerification": {"method": "none", "accuracyM": 0, "venueDistanceM": -1}},
        "submitter": {
            "accountability": "traceable",
            "userKeyHash": hashlib.sha256((uk or "anon").encode("utf-8", errors="ignore")).hexdigest()[:24],
            "realNameRecord": ("on_file" if has_realname else "none"),
        },
        "moderation": {"publicExposure": "private_by_default", "redactionVersion": "cn-1.0", "flags": []},
    }

    attach_entries: list[tuple[str, bytes, str]] = []
    for i, u in enumerate(ups, start=1):
        p = str(getattr(u, "photo_path", "") or "").strip()
        if not p:
            continue
        try:
            fpath = (UPLOAD_DIR / Path(p).name).resolve()
            raw = fpath.read_bytes()
        except Exception:
            continue
        sha = str(getattr(u, "photo_sha256", "") or "") or _sha256_hex(raw)
        rel = f"attachments/{Path(p).name}"
        payload["evidence"]["items"].append(
            {
                "id": f"att{i}",
                "kind": "photo",
                "file": rel,
                "sha256": sha,
                "capturedAt": (getattr(u, "created_at", None) or now).isoformat(),
                "watermark": {"present": False, "nonce": ""},
            }
        )
        attach_entries.append((rel, raw, sha))

    case_json = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    hashes: list[str] = [f"{_sha256_hex(case_json)}  case.json"]
    for rel, _raw, sha in attach_entries:
        hashes.append(f"{sha}  {rel}")
    hash_txt = ("\n".join(hashes) + "\n").encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("case.json", case_json)
        z.writestr("hash.txt", hash_txt)
        for rel, raw, _sha in attach_entries:
            z.writestr(rel, raw)
    out = buf.getvalue()

    fname = f"official-package-{case_id}.zip"
    headers = {"Content-Disposition": f'attachment; filename="{fname}"', "Cache-Control": "no-store"}
    return Response(out, media_type="application/zip", headers=headers)


def _default_venue_id(mode: str, venues: list[dict[str, Any]]) -> str:
    prefer = {"global": "v_cn_001", "cn": "v_cn_001", "hk": "v_hk_001"}
    preferred = prefer.get(mode)
    if preferred and any(v["id"] == preferred for v in venues):
        return preferred
    return venues[0]["id"]


class ModeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        q_mode = request.query_params.get("mode")
        cookie_mode = request.cookies.get("abang_mode")
        mode = (q_mode or cookie_mode or "global").lower()
        if mode not in ("global", "cn", "hk"):
            mode = "global"
        request.state.mode = mode
        response = await call_next(request)
        # persist mode
        if q_mode or ("abang_mode" not in request.cookies):
            response.set_cookie("abang_mode", mode, httponly=True, samesite="lax")
        return response


class UserKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        uid = request.cookies.get("abang_uid")
        if not uid:
            uid = secrets.token_urlsafe(12)
        request.state.user_key = uid
        response = await call_next(request)
        if "abang_uid" not in request.cookies:
            response.set_cookie("abang_uid", uid, httponly=True, samesite="lax")
        return response


async def _get_venues() -> list[dict[str, Any]]:
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(Venue))
        venues = res.scalars().all()
    return [{"id": v.id, "name": v.name, "city": v.city} for v in venues]


async def _get_posts(venue_id: str, types: set[str] | None = None) -> list[dict[str, Any]]:
    async with session_scope(SessionLocal) as s:
        q = select(Post).where(Post.venue_id == venue_id).order_by(Post.created_at.desc())
        if types:
            q = q.where(Post.type.in_(types))
        res = await s.execute(q)
        posts = res.scalars().all()
    out: list[dict[str, Any]] = []
    for p in posts:
        out.append(
            {
                "id": p.id,
                "type": p.type,
                "scope": getattr(p, "scope", "keep"),
                "title": p.title,
                "body": p.body,
                "venueId": p.venue_id,
                "startAt": p.start_at.isoformat(),
                "endAt": p.end_at.isoformat(),
                "tags": [t for t in (p.tags or "").split(",") if t],
            }
        )
    return out


async def _get_invites_with_proof(venue_id: str) -> list[dict[str, Any]]:
    now = _now()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(
            select(Post)
            .where(Post.venue_id == venue_id, Post.type == "invite", Post.end_at >= now)
            .order_by(Post.created_at.desc())
        )
        posts = res.scalars().all()
        ids = [p.id for p in posts]
        proof_map: dict[str, InviteProof] = {}
        if ids:
            res = await s.execute(select(InviteProof).where(InviteProof.post_id.in_(ids)))
            for pr in res.scalars().all():
                proof_map[pr.post_id] = pr

    out: list[dict[str, Any]] = []
    for p in posts:
        pr = proof_map.get(p.id)
        out.append(
            {
                "id": p.id,
                "type": p.type,
                "scope": getattr(p, "scope", "keep"),
                "title": p.title,
                "body": p.body,
                "venueId": p.venue_id,
                "startAt": p.start_at.isoformat(),
                "endAt": p.end_at.isoformat(),
                "tags": [t for t in (p.tags or "").split(",") if t],
                "verified": bool(pr),
                "photoUrl": (f"/static/{pr.photo_path}" if pr and pr.photo_path else ""),
                "addressLabel": (pr.address_label if pr else ""),
                "accuracyM": (pr.accuracy_m if pr else 0),
                "verification": (pr.verification if pr else ""),
            }
        )
    return out


# ---- Simple realtime chat (room-based) ----


class RoomHub:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = {}
        self._ws_user: dict[int, str] = {}
        self._presence: dict[str, dict[str, int]] = {}  # room -> user_key -> conn_count
        self._events: dict[str, list[dict[str, Any]]] = {}  # room -> events
        self._pings: dict[str, dict[str, float]] = {}  # room -> user_key -> last_ts

    async def join(self, room: str, ws: WebSocket, user_key: str) -> None:
        await ws.accept()
        self._rooms.setdefault(room, set()).add(ws)
        uk = user_key or "anon"
        self._ws_user[id(ws)] = uk
        bucket = self._presence.setdefault(room, {})
        bucket[uk] = int(bucket.get(uk, 0)) + 1

    def leave(self, room: str, ws: WebSocket) -> None:
        conns = self._rooms.get(room)
        if not conns:
            return
        conns.discard(ws)
        uk = self._ws_user.pop(id(ws), "anon")
        bucket = self._presence.get(room)
        if bucket and uk in bucket:
            bucket[uk] = int(bucket.get(uk, 0)) - 1
            if bucket[uk] <= 0:
                bucket.pop(uk, None)
            if not bucket:
                self._presence.pop(room, None)
        if not conns:
            self._rooms.pop(room, None)

    async def broadcast(self, room: str, payload: dict[str, Any]) -> None:
        try:
            ptype = str(payload.get("type") or "")
            if ptype in ("system", "event"):
                text = payload.get("text") or payload.get("event") or ""
                if text:
                    evs = self._events.setdefault(room, [])
                    evs.append({"ts": datetime.utcnow().isoformat(), "type": ptype, "text": str(text)[:240]})
                    if len(evs) > 60:
                        del evs[:-60]
        except Exception:
            pass
        conns = list(self._rooms.get(room, set()))
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.leave(room, ws)

    def ping(self, room: str, user_key: str, ttl_s: int = 25) -> None:
        uk = user_key or "anon"
        now = datetime.utcnow().timestamp()
        bucket = self._pings.setdefault(room, {})
        bucket[uk] = now
        cutoff = now - ttl_s
        stale = [k for k, ts in bucket.items() if ts < cutoff]
        for k in stale:
            bucket.pop(k, None)
        if not bucket:
            self._pings.pop(room, None)

    def presence_names(self, room: str) -> list[str]:
        keys: list[str] = []
        for k in (self._presence.get(room, {}) or {}).keys():
            if k and k != "anon":
                keys.append(k)
        for k in (self._pings.get(room, {}) or {}).keys():
            if k and k != "anon":
                keys.append(k)
        seen: set[str] = set()
        out: list[str] = []
        for k in keys:
            if k in seen:
                continue
            seen.add(k)
            out.append(_anon_name(k))
        return out[:18]

    def presence_keys(self, room: str) -> list[str]:
        keys: list[str] = []
        for k in (self._presence.get(room, {}) or {}).keys():
            if k and k != "anon":
                keys.append(k)
        for k in (self._pings.get(room, {}) or {}).keys():
            if k and k != "anon":
                keys.append(k)
        seen: set[str] = set()
        out: list[str] = []
        for k in keys:
            if k in seen:
                continue
            seen.add(k)
            out.append(k)
        return out[:40]

    def presence_count(self, room: str) -> int:
        keys: set[str] = set()
        for k in (self._presence.get(room, {}) or {}).keys():
            if k and k != "anon":
                keys.add(k)
        for k in (self._pings.get(room, {}) or {}).keys():
            if k and k != "anon":
                keys.add(k)
        return int(len(keys))

    def recent_events(self, room: str, limit: int = 12) -> list[dict[str, Any]]:
        evs = self._events.get(room, [])
        return list(reversed(evs[-limit:]))


hub = RoomHub()


def _public_person_id(user_key: str) -> str:
    """
    对外公开的“名片ID”：稳定、不可逆，不暴露站内 user_key。
    """
    uk = (user_key or "anon").encode("utf-8", errors="ignore")
    return f"p_{hashlib.sha256(uk).hexdigest()[:12]}"


_PLANETS = ["水星", "金星", "地球", "火星", "木星", "土星", "天王星", "海王星", "冥王星"]


def _planet_code(person_id: str) -> str:
    s = (person_id or "p_000000000000").replace("p_", "")
    try:
        a = int(s[0:2], 16)
        b = int(s[2:4], 16)
    except Exception:
        a, b = 0, 0
    planet = _PLANETS[a % len(_PLANETS)]
    num = (b % 99) + 1
    return f"{num:02d}·{planet}"


def _sha256_hex(raw: bytes) -> str:
    try:
        return hashlib.sha256(raw).hexdigest()
    except Exception:
        return ""


_RE_PHONE = re.compile(r"\b1\d{10}\b")
_RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_RE_COORD = re.compile(r"(-?\d{1,3}\.\d{4,})")
_RE_IDCARD = re.compile(r"\b\d{17}[\dXx]\b")


def _redact_public_text(text: str) -> str:
    """
    CN 模式公开展示的最低配脱敏：
    - 屏蔽手机号/邮箱/身份证/经纬度样式
    """
    t = str(text or "")
    if not t:
        return ""
    t = _RE_PHONE.sub("[PHONE]", t)
    t = _RE_EMAIL.sub("[EMAIL]", t)
    t = _RE_IDCARD.sub("[ID]", t)
    t = _RE_COORD.sub("[COORD]", t)
    t = t.replace("经度", "[COORD]").replace("纬度", "[COORD]")
    return t


async def _presence_mode(user_key: str) -> str:
    if not user_key or user_key == "anon":
        return "online"
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(PresenceSetting).where(PresenceSetting.user_key == user_key))
        row = res.scalar_one_or_none()
    mode = str(getattr(row, "mode", "") or "").strip().lower() if row else "online"
    return mode if mode in ("online", "offline") else "online"


async def presence_set_post(request: Request) -> Response:
    form: FormData = await request.form()
    mode = str(form.get("presence") or "").strip().lower()
    if mode not in ("online", "offline"):
        mode = "online"
    uk = _user_key(request)
    now = _now()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(PresenceSetting).where(PresenceSetting.user_key == uk))
        row = res.scalar_one_or_none()
        if row:
            row.mode = mode
            row.updated_at = now
        else:
            s.add(PresenceSetting(user_key=uk, mode=mode, updated_at=now))
    return RedirectResponse(url="/profile", status_code=303)


def _normalize_person_id(raw: str) -> str:
    """
    兼容旧链接：
    - 新版公开ID：p_xxxxxxxxxxxx
    - 旧版内部ID（user_key）：<token>  -> 自动映射到公开ID
    """
    v = (raw or "").strip()
    if not v:
        return v
    if v.startswith("p_") and len(v) >= 5:
        return v
    return _public_person_id(v)


async def _privacy_vis_map(person_ids: list[str]) -> dict[str, str]:
    """
    person_ids: list of public ids (p_xxx...)
    default: public
    """
    ids = [x for x in person_ids if x]
    if not ids:
        return {}
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(PersonPrivacy).where(PersonPrivacy.person_id.in_(ids)))
        rows = res.scalars().all()
    out: dict[str, str] = {}
    for r in rows:
        vis = str(getattr(r, "visibility", "") or "").strip().lower()
        if vis not in ("public", "private", "venue_verified"):
            vis = "private" if (int(getattr(r, "is_public", 1) or 1) == 0) else "public"
        out[r.person_id] = vis
    return out


async def _viewer_verified_in_venue(user_key: str, venue_id: str) -> bool:
    """
    “同场所验证”MVP：该用户在该场所最近发布过 geofence 证明（现场拍照邀约）。
    """
    uk = (user_key or "").strip()
    vid = (venue_id or "").strip()
    if not uk or not vid:
        return False
    since = _now() - timedelta(hours=6)
    async with session_scope(SessionLocal) as s:
        res = await s.execute(
            select(InviteProof.id)
            .where(
                InviteProof.user_key == uk,
                InviteProof.venue_id == vid,
                InviteProof.verification == "geofence",
                InviteProof.created_at >= since,
            )
            .limit(1)
        )
        return res.first() is not None

# ---- Minimal anti-abuse (in-memory) ----

_rate: dict[str, list[float]] = {}


def _allow(action: str, key: str, limit: int, window_s: int) -> bool:
    now = datetime.utcnow().timestamp()
    bucket = _rate.setdefault(f"{action}:{key}", [])
    cutoff = now - window_s
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


# ---- One-time challenges (in-memory, short-lived) ----

_challenges: dict[str, dict[str, Any]] = {}


def _challenge_new(kind: str, user_key: str, ttl_s: int = 90) -> dict[str, Any]:
    nonce = secrets.token_urlsafe(18)
    exp = datetime.utcnow().timestamp() + ttl_s
    _challenges[nonce] = {"kind": kind, "user_key": user_key, "exp": exp, "used": False}
    stamp = f"ABANG {nonce[:6].upper()} {datetime.utcnow().strftime('%H:%M:%S')}"
    return {"nonce": nonce, "stamp": stamp, "expiresIn": ttl_s}


def _challenge_consume(kind: str, nonce: str, user_key: str) -> None:
    rec = _challenges.get(nonce)
    if not rec:
        raise HTTPException(status_code=400, detail="invalid_nonce")
    if rec.get("used"):
        raise HTTPException(status_code=400, detail="nonce_used")
    if rec.get("kind") != kind:
        raise HTTPException(status_code=400, detail="invalid_nonce_kind")
    if rec.get("user_key") != user_key:
        raise HTTPException(status_code=400, detail="invalid_nonce_user")
    if float(rec.get("exp") or 0) < datetime.utcnow().timestamp():
        raise HTTPException(status_code=400, detail="nonce_expired")
    rec["used"] = True


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---- "摆烂" mini-game (in-memory) ----

_bailan_score: dict[str, dict[str, int]] = {}  # room -> user_key -> score


def _bailan_add(room: str, user_key: str, delta: int = 1) -> list[dict[str, Any]]:
    room = room.strip()[:80]
    if not room:
        room = "global"
    bucket = _bailan_score.setdefault(room, {})
    bucket[user_key] = int(bucket.get(user_key, 0)) + int(delta)
    top = sorted(bucket.items(), key=lambda x: x[1], reverse=True)[:10]
    return [{"name": _anon_name(k), "score": int(v)} for k, v in top]


def _anon_name(user_key: str) -> str:
    if not user_key or user_key == "anon":
        return "Name"
    return f"玩家{user_key[-4:].upper()}"


def _region_def(region_id: str) -> dict[str, Any]:
    """
    大范围互动大厅（首版：硬编码 1 个示例 region）。
    """
    if region_id == "cn_ys":
        # 南京-上海（长三角）示例中心点/半径
        return {"id": "cn_ys", "name": "南京↔上海城市圈", "center": (31.65, 120.15), "radiusM": 260_000}
    return {"id": "cn_ys", "name": "南京↔上海城市圈", "center": (31.65, 120.15), "radiusM": 260_000}


async def _venues_in_region(region_id: str) -> list[dict[str, Any]]:
    cfg = _region_def(region_id)
    clat, clng = cfg["center"]
    radius_m = int(cfg["radiusM"])
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(VenueGeo))
        geos = res.scalars().all()
        ids: list[str] = []
        for g in geos:
            d = _haversine_m(float(g.lat), float(g.lng), float(clat), float(clng))
            if d <= radius_m:
                ids.append(g.venue_id)
        if not ids:
            return []
        res = await s.execute(select(Venue).where(Venue.id.in_(ids)))
        venues = res.scalars().all()
    by_id = {v.id: v for v in venues}
    out: list[dict[str, Any]] = []
    for vid in ids:
        v = by_id.get(vid)
        if v:
            out.append({"id": v.id, "name": v.name, "city": v.city})
    return out


async def _get_invites_with_proof_multi(venue_ids: list[str]) -> list[dict[str, Any]]:
    if not venue_ids:
        return []
    async with session_scope(SessionLocal) as s:
        res = await s.execute(
            select(Post)
            .where(Post.type == "invite", Post.venue_id.in_(venue_ids))
            .order_by(Post.created_at.desc())
            .limit(80)
        )
        posts = res.scalars().all()
        ids = [p.id for p in posts]
        proof_map: dict[str, InviteProof] = {}
        if ids:
            res = await s.execute(select(InviteProof).where(InviteProof.post_id.in_(ids)))
            for pr in res.scalars().all():
                proof_map[pr.post_id] = pr

        res = await s.execute(select(Venue).where(Venue.id.in_(venue_ids)))
        venues = res.scalars().all()
        venue_map = {v.id: v for v in venues}

    out: list[dict[str, Any]] = []
    for p in posts:
        pr = proof_map.get(p.id)
        v = venue_map.get(p.venue_id)
        out.append(
            {
                "id": p.id,
                "type": p.type,
                "title": p.title,
                "body": p.body,
                "venueId": p.venue_id,
                "venueName": (v.name if v else p.venue_id),
                "venueCity": (v.city if v else ""),
                "startAt": p.start_at.isoformat(),
                "endAt": p.end_at.isoformat(),
                "tags": [t for t in (p.tags or "").split(",") if t],
                "verified": bool(pr),
                "photoUrl": (f"/static/{pr.photo_path}" if pr and pr.photo_path else ""),
                "addressLabel": (pr.address_label if pr else ""),
                "accuracyM": (pr.accuracy_m if pr else 0),
                "verification": (pr.verification if pr else ""),
            }
        )
    return out


async def _get_posts_tagged(venue_id: str, tag: str, limit: int = 60) -> list[dict[str, Any]]:
    tag = tag.strip().lower()
    if not tag:
        return []
    async with session_scope(SessionLocal) as s:
        res = await s.execute(
            select(Post)
            .where(Post.venue_id == venue_id, Post.type == "invite", Post.tags.like(f"%{tag}%"))
            .order_by(Post.created_at.desc())
            .limit(limit)
        )
        posts = res.scalars().all()
    out: list[dict[str, Any]] = []
    for p in posts:
        out.append(
            {
                "id": p.id,
                "type": p.type,
                "title": p.title,
                "body": p.body,
                "venueId": p.venue_id,
                "startAt": p.start_at.isoformat(),
                "endAt": p.end_at.isoformat(),
                "tags": [t for t in (p.tags or "").split(",") if t],
            }
        )
    return out


# ---- Pages ----


def _docs_items() -> list[str]:
    if not DOCS_DIR.exists():
        return []
    items: list[str] = []
    for p in sorted(DOCS_DIR.rglob("*.md")):
        try:
            items.append(p.relative_to(DOCS_DIR).as_posix())
        except Exception:
            continue
    return items


async def docs_index(_: Request) -> Response:
    items = _docs_items()
    li = "\n".join(
        [
            f'<li><a href="/docs/{html.escape(x)}">{html.escape(x.removesuffix(".md"))}</a></li>'
            for x in items
        ]
    )
    body = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <title>Docs</title>
        <style>
          body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 24px; }}
          a {{ color: #0b5fff; text-decoration: none; }}
          a:hover {{ text-decoration: underline; }}
        </style>
      </head>
      <body>
        <h1>Docs</h1>
        <p><a href="/">返回主页</a></p>
        <ul>
          {li or "<li>(no docs found)</li>"}
        </ul>
      </body>
    </html>
    """
    return HTMLResponse(body)


async def docs_view(request: Request) -> Response:
    raw = str(request.path_params.get("docPath") or "").strip().lstrip("/").rstrip("/")
    if not raw:
        return RedirectResponse(url="/docs", status_code=302)
    if not raw.endswith(".md"):
        raw = f"{raw}.md"

    target = (DOCS_DIR / raw).resolve()
    if target != DOCS_DIR and DOCS_DIR not in target.parents:
        raise HTTPException(status_code=400, detail="invalid_path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="not_found")

    text = target.read_text(encoding="utf-8", errors="replace")
    safe = html.escape(text)
    title = html.escape(raw.removesuffix(".md"))
    body = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <title>{title}</title>
        <style>
          body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 24px; }}
          pre {{ white-space: pre-wrap; line-height: 1.45; background: #0b1220; color: #e6edf3; padding: 16px; border-radius: 12px; }}
          a {{ color: #0b5fff; text-decoration: none; }}
          a:hover {{ text-decoration: underline; }}
        </style>
      </head>
      <body>
        <p><a href="/docs">← Docs</a> · <a href="/">主页</a></p>
        <h1>{title}</h1>
        <pre>{safe}</pre>
      </body>
    </html>
    """
    return HTMLResponse(body)


async def hub_post(request: Request) -> Response:
    # Post 内容已并入 Helpis（/help#helpis），保留旧路径做兼容跳转
    qp = []
    mode = request.query_params.get("mode") or _mode(request)
    if mode:
        qp.append(f"mode={mode}")
    venue = request.query_params.get("venue")
    if venue:
        qp.append(f"venue={venue}")
    p = request.query_params.get("p")
    if p:
        qp.append(f"p={p}")
    scope = request.query_params.get("scope")
    if scope:
        qp.append(f"scope={scope}")
    q = ("?" + "&".join(qp)) if qp else ""
    return RedirectResponse(url=f"/help{q}#helpis", status_code=302)


async def hub_coffeechat(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    return templates.TemplateResponse(
        request,
        "hub_coffeechat.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request)},
    )


async def hub_public(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    open_cnt = 0
    try:
        since = _now() - timedelta(hours=24)
        async with session_scope(SessionLocal) as s:
            res = await s.execute(
                select(EmergencyCase.id)
                .where(
                    EmergencyCase.venue_id == venue_obj["id"],
                    EmergencyCase.status == "open",
                    EmergencyCase.created_at >= since,
                )
                .limit(50)
            )
            open_cnt = len(res.all() or [])
    except Exception:
        open_cnt = 0
    return templates.TemplateResponse(
        request,
        "hub_public.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request), "emergencyOpen": open_cnt},
    )


async def hub_help(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    return templates.TemplateResponse(
        request,
        "hub_help.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request)},
    )


async def support_sell(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    return templates.TemplateResponse(
        request,
        "support_sell.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request)},
    )


async def robot4s(request: Request) -> Response:
    """
    机器人4S店：机器人相关聚合入口（购买/二手/维修/配件/教程）。
    Demo 规则：按 venue 粒度聚合 posts，关键词/标签匹配 “机器人/robot”。
    """
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    vid = venue_obj["id"]
    async with session_scope(SessionLocal) as s:
        q = (
            select(Post)
            .where(
                Post.venue_id == vid,
                or_(
                    Post.tags.like("%robot%"),
                    Post.tags.like("%机器人%"),
                    Post.title.like("%robot%"),
                    Post.title.like("%机器人%"),
                    Post.body.like("%robot%"),
                    Post.body.like("%机器人%"),
                ),
            )
            .order_by(Post.created_at.desc())
            .limit(60)
        )
        res = await s.execute(q)
        rows = res.scalars().all()
    posts = [
        {
            "id": r.id,
            "scope": getattr(r, "scope", "keep") or "keep",
            "title": str(r.title or "").strip()[:200],
            "body": (str(r.body or "").strip()[:180] + ("…" if str(r.body or "").strip()[180:] else "")) if r.body else "",
            "createdAt": r.created_at.isoformat() if getattr(r, "created_at", None) else "",
        }
        for r in rows
    ]
    return templates.TemplateResponse(
        request,
        "robot4s.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request), "posts": posts},
    )


async def support_page(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    async with session_scope(SessionLocal) as s:
        res = await s.execute(
            select(SupportListing)
            .where(SupportListing.venue_id == venue_obj["id"], SupportListing.status == "active")
            .order_by(SupportListing.created_at.desc())
            .limit(80)
        )
        rows = res.scalars().all()
    items = [
        {
            "id": r.id,
            "title": r.title,
            "story": (str(r.story or "").strip()[:160] + ("…" if str(r.story or "").strip()[160:] else "")) if r.story else "",
            "contactPublic": int(r.contact_public or 0) == 1,
            "createdAt": r.created_at.isoformat(),
        }
        for r in rows
    ]
    return templates.TemplateResponse(
        request,
        "support.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request), "items": items},
    )

async def support_new(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    return templates.TemplateResponse(
        request,
        "support_new.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request)},
    )


async def support_new_post(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("support_new", ip, limit=20, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    form: FormData = await request.form()
    venues = await _get_venues()
    venue_id = str(form.get("venueId") or venues[0]["id"]).strip()
    title = str(form.get("title") or "").strip()[:160]
    story = str(form.get("story") or "").strip()[:2000]
    need_help = str(form.get("needHelp") or "").strip()[:2000]
    contact = str(form.get("contact") or "").strip()[:160]
    pub = str(form.get("contactPublic") or "").strip().lower() in ("1", "on", "true", "yes")
    if not title:
        raise HTTPException(status_code=400, detail="title_required")
    ok, reason = moderate_text(f"{title}\n{story}\n{need_help}")
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    uk = _user_key(request)
    now = _now()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(SupportListing.id).order_by(SupportListing.id.desc()).limit(1))
        last = res.first()
        next_num = 1
        if last and isinstance(last[0], str) and last[0].startswith("sp"):
            try:
                next_num = int(last[0][2:]) + 1
            except Exception:
                next_num = 1
        sid = f"sp{next_num}"
        s.add(
            SupportListing(
                id=sid,
                user_key=uk,
                venue_id=venue_id,
                title=title,
                story=story,
                need_help=need_help,
                contact=contact,
                contact_public=1 if pub else 0,
                status="active",
                created_at=now,
            )
        )
    return RedirectResponse(url=f"/support/{sid}?venue={venue_id}", status_code=303)


async def support_detail(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    sid = str(request.path_params.get("sid") or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="sid_required")
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(SupportListing).where(SupportListing.id == sid))
        r = res.scalar_one_or_none()
    if not r or str(r.status or "") != "active":
        raise HTTPException(status_code=404, detail="not_found")
    owner_pid = _public_person_id(str(r.user_key or ""))
    item = {
        "id": r.id,
        "title": r.title,
        "story": r.story or "",
        "needHelp": r.need_help or "",
        "contact": r.contact or "",
        "contactPublic": int(r.contact_public or 0) == 1,
    }
    return templates.TemplateResponse(
        request,
        "support_detail.html",
        {
            "venues": venues,
            "venue": venue_obj,
            "mode": _mode(request),
            "item": item,
            "ownerCardUrl": f"/card/{owner_pid}?venue={venue_obj['id']}",
        },
    )

async def support_project(request: Request) -> Response:
    venue = request.query_params.get("venue") or ""
    return RedirectResponse(url=f"/support?venue={venue}", status_code=302)


async def support_story(request: Request) -> Response:
    venue = request.query_params.get("venue") or ""
    return RedirectResponse(url=f"/support?venue={venue}", status_code=302)


async def support_crowd(request: Request) -> Response:
    venue = request.query_params.get("venue") or ""
    return RedirectResponse(url=f"/support?venue={venue}", status_code=302)


async def sell_page(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    async with session_scope(SessionLocal) as s:
        res = await s.execute(
            select(SellListing)
            .where(SellListing.venue_id == venue_obj["id"], SellListing.status != "hidden")
            .order_by(SellListing.created_at.desc())
            .limit(80)
        )
        rows = res.scalars().all()
    items = [
        {
            "id": r.id,
            "title": r.title,
            "description": (str(r.description or "").strip()[:160] + ("…" if str(r.description or "").strip()[160:] else "")) if r.description else "",
            "price": int(r.price or 0),
            "currency": str(r.currency or "CNY"),
            "contactPublic": int(r.contact_public or 0) == 1,
            "createdAt": r.created_at.isoformat(),
        }
        for r in rows
    ]
    return templates.TemplateResponse(
        request,
        "sell.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request), "items": items},
    )

async def sell_new(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    return templates.TemplateResponse(
        request,
        "sell_new.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request)},
    )


async def sell_new_post(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("sell_new", ip, limit=30, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    form: FormData = await request.form()
    venues = await _get_venues()
    venue_id = str(form.get("venueId") or venues[0]["id"]).strip()
    title = str(form.get("title") or "").strip()[:160]
    description = str(form.get("description") or "").strip()[:2500]
    currency = str(form.get("currency") or "CNY").strip().upper()[:8]
    try:
        price = int(form.get("price") or 0)
    except Exception:
        price = 0
    price = max(0, price)
    contact = str(form.get("contact") or "").strip()[:160]
    pub = str(form.get("contactPublic") or "").strip().lower() in ("1", "on", "true", "yes")
    if not title:
        raise HTTPException(status_code=400, detail="title_required")
    ok, reason = moderate_text(f"{title}\n{description}")
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    uk = _user_key(request)
    now = _now()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(SellListing.id).order_by(SellListing.id.desc()).limit(1))
        last = res.first()
        next_num = 1
        if last and isinstance(last[0], str) and last[0].startswith("si"):
            try:
                next_num = int(last[0][2:]) + 1
            except Exception:
                next_num = 1
        iid = f"si{next_num}"
        s.add(
            SellListing(
                id=iid,
                user_key=uk,
                venue_id=venue_id,
                title=title,
                description=description,
                price=price,
                currency=currency or "CNY",
                contact=contact,
                contact_public=1 if pub else 0,
                status="active",
                created_at=now,
            )
        )
    return RedirectResponse(url=f"/sell/{iid}?venue={venue_id}", status_code=303)


async def sell_detail(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    iid = str(request.path_params.get("iid") or "").strip()
    if not iid:
        raise HTTPException(status_code=400, detail="iid_required")
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(SellListing).where(SellListing.id == iid))
        r = res.scalar_one_or_none()
    if not r or str(r.status or "") == "hidden":
        raise HTTPException(status_code=404, detail="not_found")
    owner_pid = _public_person_id(str(r.user_key or ""))
    item = {
        "id": r.id,
        "title": r.title,
        "description": r.description or "",
        "price": int(r.price or 0),
        "currency": str(r.currency or "CNY"),
        "contact": r.contact or "",
        "contactPublic": int(r.contact_public or 0) == 1,
        "status": str(r.status or "active"),
    }
    return templates.TemplateResponse(
        request,
        "sell_detail.html",
        {
            "venues": venues,
            "venue": venue_obj,
            "mode": _mode(request),
            "item": item,
            "ownerCardUrl": f"/card/{owner_pid}?venue={venue_obj['id']}",
        },
    )

async def sell_arts(request: Request) -> Response:
    venue = request.query_params.get("venue") or ""
    return RedirectResponse(url=f"/sell?venue={venue}", status_code=302)


async def sell_product(request: Request) -> Response:
    venue = request.query_params.get("venue") or ""
    return RedirectResponse(url=f"/sell?venue={venue}", status_code=302)


async def sell_vintage(request: Request) -> Response:
    venue = request.query_params.get("venue") or ""
    return RedirectResponse(url=f"/sell?venue={venue}", status_code=302)


async def map_page(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    return templates.TemplateResponse(
        request,
        "map.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request)},
    )


async def invite_new(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])

    uk = _user_key(request)
    now = _now()

    # Build share URL using LAN IPv4 if host is localhost/127.0.0.1
    host = str(request.headers.get("host") or "127.0.0.1:8000")
    port = "8000"
    try:
        if ":" in host:
            port = host.split(":")[-1]
    except Exception:
        port = "8000"
    lan = _lan_ipv4()
    share_origin = f"http://{lan}:{port}"
    local_origin = f"http://127.0.0.1:{port}"

    # State for two flows
    blocked = False
    quota_left = 1
    realtime_ready = False
    open_inv = None
    open_q = None
    q_replies: list[dict[str, Any]] = []

    async with session_scope(SessionLocal) as s:
        # ---- Flow A: ask-only (no realname required)
        res = await s.execute(
            select(NextQuestion)
            .where(NextQuestion.asker_key == uk, NextQuestion.venue_id == venue_obj["id"], NextQuestion.expires_at >= now)
            .order_by(NextQuestion.created_at.desc())
            .limit(1)
        )
        open_q = res.scalar_one_or_none()
        if open_q:
            res = await s.execute(
                select(NextQuestionReply)
                .where(NextQuestionReply.token == open_q.token)
                .order_by(NextQuestionReply.created_at.desc())
                .limit(12)
            )
            rs = res.scalars().all()
            q_replies = [
                {
                    "by": _anon_name(str(getattr(r, "user_key", "") or "")),
                    "choice": str(getattr(r, "choice", "maybe") or "maybe"),
                    "message": str(getattr(r, "message", "") or ""),
                    "createdAt": getattr(r, "created_at").isoformat() if getattr(r, "created_at", None) else "",
                }
                for r in rs
            ]

        # ---- Flow B: realtime meet invite (requires realname + agreement)
        res = await s.execute(select(RealNameRecord).where(RealNameRecord.user_key == uk))
        rn = res.scalar_one_or_none()
        realtime_ready = rn is not None

        # If any complaint in last 7 days, block realtime flow
        since = now - timedelta(days=7)
        res = await s.execute(
            select(MeetInviteComplaint.id).where(MeetInviteComplaint.inviter_key == uk, MeetInviteComplaint.created_at >= since).limit(1)
        )
        blocked = res.first() is not None

        # Daily limit: 1 realtime invite per day (UTC day)
        day_start = datetime(now.year, now.month, now.day)
        res = await s.execute(
            select(MeetInvite.token)
            .where(MeetInvite.inviter_key == uk, MeetInvite.created_at >= day_start)
            .order_by(MeetInvite.created_at.desc())
            .limit(2)
        )
        created_today = len(res.all() or [])
        quota_left = 0 if created_today >= 1 else 1

        res = await s.execute(
            select(MeetInvite)
            .where(
                MeetInvite.inviter_key == uk,
                MeetInvite.venue_id == venue_obj["id"],
                MeetInvite.status == "open",
                MeetInvite.expires_at >= now,
            )
            .order_by(MeetInvite.created_at.desc())
            .limit(1)
        )
        open_inv = res.scalar_one_or_none()

        if request.method == "POST":
            form: FormData = await request.form()
            flow = str(form.get("flow") or "ask").strip().lower()
            if flow == "ask":
                if not _allow("next_ask", f"{venue_obj['id']}:{uk}", limit=12, window_s=3600):
                    raise HTTPException(status_code=429, detail="too_fast")
                q = str(form.get("question") or "").strip()[:240]
                if not q:
                    raise HTTPException(status_code=400, detail="question_required")
                ok, reason = moderate_text(q)
                if not ok:
                    raise HTTPException(status_code=400, detail=reason)
                token = secrets.token_urlsafe(18)
                exp = now + timedelta(minutes=10)
                s.add(NextQuestion(token=token, venue_id=venue_obj["id"], asker_key=uk, question=q, created_at=now, expires_at=exp))
                return RedirectResponse(url=f"/invite/new?venue={venue_obj['id']}", status_code=303)

            # realtime flow
            if not realtime_ready:
                next_url = f"/invite/new?venue={venue_obj['id']}"
                return RedirectResponse(url=f"/realname?venue={venue_obj['id']}&next={urllib.parse.quote(next_url)}", status_code=303)
            agree = str(form.get("agree") or "").strip().lower()
            if agree not in ("1", "true", "yes", "on"):
                raise HTTPException(status_code=400, detail="agreement_required")
            if blocked:
                raise HTTPException(status_code=403, detail="invite_blocked_by_complaint")
            if quota_left <= 0:
                raise HTTPException(status_code=429, detail="daily_limit_reached")
            note = str(form.get("note") or "").strip()[:160]
            token = secrets.token_urlsafe(18)
            room = f"meet:{token}"
            exp = now + timedelta(minutes=8)
            s.add(
                MeetInvite(
                    token=token,
                    venue_id=venue_obj["id"],
                    inviter_key=uk,
                    invitee_key="",
                    room=room,
                    status="open",
                    note=note,
                    created_at=now,
                    expires_at=exp,
                )
            )
            return RedirectResponse(url=f"/invite/new?venue={venue_obj['id']}", status_code=303)

    share_url = f"{share_origin}/invite/" + (open_inv.token if open_inv else "")
    ask_url = f"{share_origin}/ask/" + (open_q.token if open_q else "")
    return templates.TemplateResponse(
        request,
        "invite_new.html",
        {
            "venues": venues,
            "venue": venue_obj,
            "mode": _mode(request),
            "quotaLeft": quota_left,
            "blocked": blocked,
            "realtimeReady": realtime_ready,
            "invite": {
                "token": open_inv.token,
                "room": open_inv.room,
                "note": open_inv.note,
                "expiresAt": open_inv.expires_at.isoformat(),
            }
            if open_inv
            else None,
            "ask": {
                "token": open_q.token,
                "question": open_q.question,
                "expiresAt": open_q.expires_at.isoformat(),
                "replies": q_replies,
            }
            if open_q
            else None,
            "shareOrigin": share_origin,
            "localOrigin": local_origin,
            "shareUrl": share_url if open_inv else "",
            "askUrl": ask_url if open_q else "",
        },
    )


async def invite_view(request: Request) -> Response:
    token = str(request.path_params.get("token") or "").strip()[:96]
    if not token:
        raise HTTPException(status_code=404, detail="not_found")
    now = _now()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(MeetInvite).where(MeetInvite.token == token))
        inv = res.scalar_one_or_none()
        if not inv:
            raise HTTPException(status_code=404, detail="not_found")
        if inv.expires_at < now or str(inv.status or "") == "expired":
            inv.status = "expired"
            raise HTTPException(status_code=410, detail="invite_expired")
        if str(inv.status or "") == "accepted":
            return RedirectResponse(url=f"/messages?room={urllib.parse.quote(inv.room)}", status_code=303)
        venue_id = str(inv.venue_id or "")
        venues = await _get_venues()
        venue_obj = next((v for v in venues if v["id"] == venue_id), venues[0])
    return templates.TemplateResponse(
        request,
        "invite_view.html",
        {
            "venues": venues,
            "venue": venue_obj,
            "mode": _mode(request),
            "token": token,
            "note": str(getattr(inv, "note", "") or ""),
            "expiresAt": getattr(inv, "expires_at").isoformat() if getattr(inv, "expires_at", None) else "",
        },
    )


async def invite_accept(request: Request) -> Response:
    token = str(request.path_params.get("token") or "").strip()[:96]
    if not token:
        raise HTTPException(status_code=404, detail="not_found")
    uk = _user_key(request)
    now = _now()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(MeetInvite).where(MeetInvite.token == token))
        inv = res.scalar_one_or_none()
        if not inv:
            raise HTTPException(status_code=404, detail="not_found")
        if inv.expires_at < now or str(inv.status or "") != "open":
            raise HTTPException(status_code=410, detail="invite_not_open")
        inv.status = "accepted"
        inv.invitee_key = uk
    return RedirectResponse(url=f"/messages?room={urllib.parse.quote(f'meet:{token}')}", status_code=303)


async def invite_decline(request: Request) -> Response:
    token = str(request.path_params.get("token") or "").strip()[:96]
    if not token:
        raise HTTPException(status_code=404, detail="not_found")
    now = _now()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(MeetInvite).where(MeetInvite.token == token))
        inv = res.scalar_one_or_none()
        if not inv:
            raise HTTPException(status_code=404, detail="not_found")
        if inv.expires_at < now or str(inv.status or "") != "open":
            raise HTTPException(status_code=410, detail="invite_not_open")
        inv.status = "declined"
    return HTMLResponse("<p>已拒绝。你可以直接关闭这个页面。</p>")


async def invite_complain(request: Request) -> Response:
    token = str(request.path_params.get("token") or "").strip()[:96]
    if not token:
        raise HTTPException(status_code=404, detail="not_found")
    ip = request.client.host if request.client else "unknown"
    if not _allow("invite_complain", ip, limit=6, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    form: FormData = await request.form()
    reason = str(form.get("reason") or "harassment").strip()[:240]
    now = _now()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(MeetInvite).where(MeetInvite.token == token))
        inv = res.scalar_one_or_none()
        if not inv:
            raise HTTPException(status_code=404, detail="not_found")
        inv.status = "complained"
        s.add(MeetInviteComplaint(token=token, inviter_key=str(inv.inviter_key or ""), ip=ip, reason=reason, created_at=now))
    return HTMLResponse("<p>已记录投诉。你可以关闭这个页面。</p>")


async def ask_view(request: Request) -> Response:
    token = str(request.path_params.get("token") or "").strip()[:96]
    if not token:
        raise HTTPException(status_code=404, detail="not_found")
    now = _now()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(NextQuestion).where(NextQuestion.token == token))
        q = res.scalar_one_or_none()
        if not q:
            raise HTTPException(status_code=404, detail="not_found")
        if q.expires_at < now:
            raise HTTPException(status_code=410, detail="ask_expired")
        venues = await _get_venues()
        venue_obj = next((v for v in venues if v["id"] == str(q.venue_id or "")), venues[0])
    return templates.TemplateResponse(
        request,
        "ask_view.html",
        {
            "venues": venues,
            "venue": venue_obj,
            "mode": _mode(request),
            "token": token,
            "question": str(q.question or ""),
            "expiresAt": getattr(q, "expires_at").isoformat() if getattr(q, "expires_at", None) else "",
        },
    )


async def ask_reply(request: Request) -> Response:
    token = str(request.path_params.get("token") or "").strip()[:96]
    if not token:
        raise HTTPException(status_code=404, detail="not_found")
    uk = _user_key(request)
    now = _now()
    if not _allow("ask_reply", f"{token}:{uk}", limit=3, window_s=60):
        raise HTTPException(status_code=429, detail="rate_limited")
    form: FormData = await request.form()
    choice = str(form.get("choice") or "maybe").strip().lower()
    if choice not in ("yes", "no", "maybe"):
        choice = "maybe"
    msg = str(form.get("message") or "").strip()[:240]
    ok, reason = moderate_text(msg) if msg else (True, "")
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(NextQuestion).where(NextQuestion.token == token))
        q = res.scalar_one_or_none()
        if not q:
            raise HTTPException(status_code=404, detail="not_found")
        if q.expires_at < now:
            raise HTTPException(status_code=410, detail="ask_expired")
        s.add(NextQuestionReply(token=token, user_key=uk, choice=choice, message=msg, created_at=now))
    return HTMLResponse("<p>已发送。你可以关闭这个页面。</p>")


async def universe_page(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    return templates.TemplateResponse(
        request,
        "universe.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request)},
    )


async def universe_wm_page(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    mode = _mode(request)
    # Prefer local embedded build at /wm/ (served by this same Starlette app).
    # If not built yet, fall back to public demo.
    repo_root = Path(__file__).resolve().parents[2]
    wm_dist = repo_root / "aabapp" / "dist"
    wm_local_ready = (wm_dist / "index.html").exists()

    force_remote = str(request.query_params.get("remote") or "").strip().lower() in ("1", "true", "yes", "on")
    force_dev = str(request.query_params.get("dev") or "").strip().lower() in ("1", "true", "yes", "on")

    if force_dev:
        wm_url = "http://127.0.0.1:3000"
    elif (not force_remote) and wm_local_ready:
        wm_url = "/wm/"
    else:
        wm_url = "https://worldmonitor.app"
    wm_blocked = (mode == "cn")
    return templates.TemplateResponse(
        request,
        "universe_wm.html",
        {
            "venues": venues,
            "venue": venue_obj,
            "mode": mode,
            "wmUrl": wm_url,
            "wmBlocked": wm_blocked,
            "wmLocalReady": wm_local_ready,
        },
    )


async def wm_reset_page(request: Request) -> Response:
    # One-click: unregister SW, clear caches + worldmonitor-* localStorage keys, then redirect to /wm/
    html_out = """<!doctype html>
<html lang="zh-Hans">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>real world · reset</title>
    <style>
      body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial; padding:24px; line-height:1.6}
      .card{max-width:720px;margin:0 auto;border:1px solid #ddd;border-radius:16px;padding:18px 18px;background:#fff}
      .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;background:#f5f5f5;padding:10px 12px;border-radius:12px;overflow:auto}
      .ok{color:#0a7a3d;font-weight:800}
    </style>
  </head>
  <body>
    <div class="card">
      <div class="ok">正在清理缓存与旧配置…</div>
      <div class="mono" id="log">working…</div>
    </div>
    <script>
      (async () => {
        const log = (m) => { const el = document.getElementById('log'); el.textContent += "\\n" + m; };
        try {
          if ('serviceWorker' in navigator) {
            const regs = await navigator.serviceWorker.getRegistrations();
            for (const r of regs) { try { await r.unregister(); } catch(e) {} }
            log('serviceWorker: unregistered');
          } else {
            log('serviceWorker: not supported');
          }
        } catch (e) { log('serviceWorker: failed'); }

        try {
          if (window.caches && caches.keys) {
            const ks = await caches.keys();
            await Promise.all(ks.map((k) => caches.delete(k)));
            log('caches: cleared');
          } else {
            log('caches: not available');
          }
        } catch (e) { log('caches: failed'); }

        try {
          const keys = [];
          for (let i=0;i<localStorage.length;i++) {
            const k = localStorage.key(i);
            if (k && k.startsWith('worldmonitor-')) keys.push(k);
          }
          keys.forEach((k) => localStorage.removeItem(k));
          log('localStorage: removed ' + keys.length + ' keys');
        } catch (e) { log('localStorage: failed'); }

        setTimeout(() => { window.location.href = '/wm/'; }, 400);
      })();
    </script>
  </body>
</html>"""
    return HTMLResponse(html_out)


 


async def interact_live(request: Request) -> Response:
    """
    现场拍照 + 当下定位发布邀约（MVP：只提供“相机实时画面”入口，不提供相册选择）。
    """
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    return templates.TemplateResponse(
        request,
        "interact_live.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request)},
    )


async def interact_region(request: Request) -> Response:
    region_id = (request.query_params.get("region") or "cn_ys").strip()
    cfg = _region_def(region_id)
    venues = await _get_venues()
    region_venues = await _venues_in_region(cfg["id"])
    venue_ids = [v["id"] for v in region_venues]
    invites = await _get_invites_with_proof_multi(venue_ids)
    room = f"region:{cfg['id']}"
    return templates.TemplateResponse(
        request,
        "interact_region.html",
        {
            "venues": venues,
            "venue": None,
            "invites": invites,
            "mode": _mode(request),
            "region": cfg,
            "regionVenues": region_venues,
            "room": room,
            "me": _anon_name(_user_key(request)),
        },
    )


async def api_challenge(request: Request) -> Response:
    kind = (request.query_params.get("kind") or "invite_photo").strip()
    if kind not in ("invite_photo",):
        raise HTTPException(status_code=400, detail="invalid_kind")
    return JSONResponse(_challenge_new(kind, _user_key(request)))


async def api_invite_live_create(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("invite_live", ip, limit=20, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")

    form: FormData = await request.form()
    venue_id = str(form.get("venueId") or "").strip()
    if not venue_id:
        raise HTTPException(status_code=400, detail="venueId_required")

    title = str(form.get("title") or "").strip()[:120] or "一起吃饭"
    body = str(form.get("body") or "").strip()[:600]
    scope = str(form.get("scope") or "now").strip().lower()
    if scope not in ("now", "keep"):
        scope = "now"

    nonce = str(form.get("nonce") or "").strip()
    if not nonce:
        raise HTTPException(status_code=400, detail="nonce_required")
    _challenge_consume("invite_photo", nonce, _user_key(request))

    try:
        lat = float(form.get("lat"))
        lng = float(form.get("lng"))
        accuracy = int(float(form.get("accuracy") or 0))
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_location")
    if accuracy <= 0 or accuracy > 1000:
        raise HTTPException(status_code=400, detail="invalid_accuracy")

    photo = form.get("photo")
    if not isinstance(photo, UploadFile):
        raise HTTPException(status_code=400, detail="photo_required")
    if (photo.content_type or "") not in ("image/jpeg", "image/jpg", "image/png"):
        raise HTTPException(status_code=400, detail="invalid_photo_type")
    raw = await photo.read()
    if not raw or len(raw) > 2_800_000:
        raise HTTPException(status_code=400, detail="photo_too_large")

    now = _now()
    uk = _user_key(request)
    ttl = timedelta(minutes=30) if scope == "now" else timedelta(hours=1)

    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(Venue).where(Venue.id == venue_id))
        v = res.scalar_one_or_none()
        if not v:
            raise HTTPException(status_code=404, detail="venue_not_found")

        res = await s.execute(select(Post.id).order_by(Post.id.desc()).limit(1))
        last = res.first()
        next_num = 3
        if last and isinstance(last[0], str) and last[0].startswith("p"):
            try:
                next_num = int(last[0][1:]) + 1
            except Exception:
                next_num = 3
        post_id = f"p{next_num}"

        # Geofence check (best-effort)
        res = await s.execute(select(VenueGeo).where(VenueGeo.venue_id == venue_id))
        vg = res.scalar_one_or_none()
        distance_m = -1
        verification = "gps_only"
        address_label = f"{v.name} · {v.city}"
        if vg:
            distance_m = int(_haversine_m(lat, lng, float(vg.lat), float(vg.lng)))
            if distance_m <= int(vg.radius_m) and accuracy <= 150:
                verification = "geofence"

        ext = "jpg" if (photo.content_type or "").startswith("image/j") else "png"
        fname = f"invite_{post_id}_{nonce[:6].lower()}.{ext}"
        (UPLOAD_DIR / fname).write_bytes(raw)
        photo_path = f"uploads/{fname}"

        s.add(
            Post(
                id=post_id,
                type="invite",
                scope=scope,
                title=title,
                body=body or "（现场拍照邀约）",
                venue_id=venue_id,
                start_at=now,
                end_at=now + ttl,
                tags="eat,live",
                created_at=now,
            )
        )

        res = await s.execute(select(InviteProof.id).order_by(InviteProof.id.desc()).limit(1))
        last = res.first()
        next_num = 1
        if last and isinstance(last[0], str) and last[0].startswith("ip"):
            try:
                next_num = int(last[0][2:]) + 1
            except Exception:
                next_num = 1
        proof_id = f"ip{next_num}"
        s.add(
            InviteProof(
                id=proof_id,
                post_id=post_id,
                user_key=uk,
                venue_id=venue_id,
                address_label=address_label,
                photo_path=photo_path,
                lat=lat,
                lng=lng,
                accuracy_m=accuracy,
                venue_distance_m=distance_m,
                verification=verification,
                challenge_nonce=nonce,
                created_at=now,
            )
        )

    await hub.broadcast(
        f"venue:{venue_id}",
        {"type": "system", "text": f"新邀约（已验证）：{title}", "ts": now.isoformat()},
    )
    # If this venue belongs to a large region, broadcast there too (demo: cn_ys)
    try:
        rvs = await _venues_in_region("cn_ys")
        if any(v["id"] == venue_id for v in rvs):
            await hub.broadcast(
                "region:cn_ys",
                {"type": "system", "text": f"新邀约（已验证）：{title}", "ts": now.isoformat()},
            )
    except Exception:
        pass
    return JSONResponse({"ok": True, "postId": post_id})


async def api_game_bailan(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("bailan", ip, limit=120, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_json")
    room = str(payload.get("room") or "region:cn_ys").strip()[:80]
    if not (room.startswith("region:") or room.startswith("venue:")):
        raise HTTPException(status_code=400, detail="invalid_room")

    uk = _user_key(request)
    if not _allow("bailan_user", f"{room}:{uk}", limit=12, window_s=30):
        raise HTTPException(status_code=429, detail="too_fast")

    top = _bailan_add(room, uk, delta=1)
    now = _now().isoformat()
    await hub.broadcast(room, {"type": "event", "event": "bailan", "by": _anon_name(uk), "top": top, "ts": now})
    my = next((x for x in top if x["name"] == _anon_name(uk)), {"name": _anon_name(uk), "score": 0})
    return JSONResponse({"ok": True, "me": my, "top": top})


async def home(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    uk = _user_key(request)
    pid = _public_person_id(uk)
    tagline = str(request.query_params.get("tagline") or "To the FUTURE YOUNG CITY").strip()
    if not tagline:
        tagline = "To the FUTURE YOUNG CITY"
    if len(tagline) > 120:
        tagline = tagline[:120]
    display_name = ""
    title_line = ""
    name_public = 0
    verified = "none"
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(PersonIdentity).where(PersonIdentity.person_id == pid))
        ident = res.scalar_one_or_none()
        if ident:
            display_name = str(ident.display_name or "").strip()
            title_line = str(ident.title or "").strip()
            try:
                name_public = 1 if int(ident.name_public or 0) == 1 else 0
            except Exception:
                name_public = 0
            verified = str(ident.verified or "none").strip().lower() or "none"
            if verified not in ("none", "pending", "verified"):
                verified = "none"
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "venues": venues,
            "venue": venue_obj,
            "mode": _mode(request),
            "bodyClass": "entry",
            "personId": pid,
            "displayName": display_name,
            "titleLine": title_line,
            "namePublic": name_public,
            "verified": verified,
            "tagline": tagline,
        },
    )


async def interact(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    invites = await _get_invites_with_proof(venue_obj["id"])
    return templates.TemplateResponse(
        request,
        "interact.html",
        {"venues": venues, "venue": venue_obj, "invites": invites, "mode": _mode(request)},
    )


async def interact_new(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    return templates.TemplateResponse(
        request,
        "interact_new.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request)},
    )


async def interact_new_post(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("post_create", ip, limit=6, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    form: FormData = await request.form()
    venues = await _get_venues()
    venue_id = str(form.get("venueId") or venues[0]["id"])
    scope = str(form.get("scope") or "keep").strip().lower()
    if scope not in ("now", "keep"):
        scope = "keep"
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(Post.id).order_by(Post.id.desc()).limit(1))
        last = res.first()
        next_num = 3
        if last and isinstance(last[0], str) and last[0].startswith("p"):
            try:
                next_num = int(last[0][1:]) + 1
            except Exception:
                next_num = 3
        post_id = f"p{next_num}"
        now = _now()
        ttl = timedelta(minutes=30) if scope == "now" else timedelta(hours=1)
        s.add(
            Post(
                id=post_id,
                type="invite",
                scope=scope,
                title=str(form.get("title") or "未命名邀约"),
                body=str(form.get("body") or ""),
                venue_id=venue_id,
                start_at=now,
                end_at=now + ttl,
                tags="eat",
                created_at=now,
            )
        )
    return RedirectResponse(url=f"/interact?venue={venue_id}", status_code=303)


async def coffee(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or venues[0]["id"]
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    invites = await _get_posts(venue_obj["id"], {"invite"})
    coffee_invites = [p for p in invites if "coffee" in (p.get("tags") or [])]
    return templates.TemplateResponse(
        request,
        "coffee.html",
        {"venues": venues, "venue": venue_obj, "invites": coffee_invites},
    )


async def coffee_new(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or venues[0]["id"]
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    return templates.TemplateResponse(
        request,
        "coffee_new.html",
        {"venues": venues, "venue": venue_obj},
    )


async def coffee_new_post(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("post_create", ip, limit=6, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    form: FormData = await request.form()
    venues = await _get_venues()
    venue_id = str(form.get("venueId") or venues[0]["id"])
    title = str(form.get("title") or "Coffee Chat")
    body = str(form.get("body") or "")
    start_at_in = str(form.get("startAt") or "").strip()
    ok, reason = moderate_text(f"{title}\n{body}")
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    now = _now()
    start_at = now
    if start_at_in:
        try:
            # datetime-local: "YYYY-MM-DDTHH:MM"
            start_at = datetime.fromisoformat(start_at_in)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_startAt")
        if start_at < now - timedelta(minutes=5):
            raise HTTPException(status_code=400, detail="startAt_in_past")
        if start_at > now + timedelta(days=3):
            raise HTTPException(status_code=400, detail="startAt_too_far")

    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(Post.id).order_by(Post.id.desc()).limit(1))
        last = res.first()
        next_num = 3
        if last and isinstance(last[0], str) and last[0].startswith("p"):
            try:
                next_num = int(last[0][1:]) + 1
            except Exception:
                next_num = 3
        post_id = f"p{next_num}"
        s.add(
            Post(
                id=post_id,
                type="invite",
                scope="keep",
                title=title,
                body=body,
                venue_id=venue_id,
                start_at=start_at,
                end_at=start_at + timedelta(hours=2),
                tags="coffee,eat",
                created_at=now,
            )
        )
    return RedirectResponse(url=f"/coffee?venue={venue_id}", status_code=303)


async def lost(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    lost_posts = await _get_posts(venue_obj["id"], {"lost", "found"})
    return templates.TemplateResponse(
        request,
        "lost.html",
        {"venues": venues, "venue": venue_obj, "posts": lost_posts, "mode": _mode(request)},
    )


async def lost_new(request: Request) -> Response:
    venue = request.query_params.get("venue")
    type = request.query_params.get("type") or "lost"
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    kind = "found" if type == "found" else "lost"
    return templates.TemplateResponse(
        request,
        "lost_new.html",
        {"venues": venues, "venue": venue_obj, "kind": kind, "mode": _mode(request)},
    )


async def lost_new_post(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("post_create", ip, limit=6, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    form: FormData = await request.form()
    venue_id = str(form.get("venueId") or (await _get_venues())[0]["id"])
    ptype = str(form.get("type") or "lost")
    if ptype not in ("lost", "found"):
        ptype = "lost"
    title = str(form.get("title") or "未命名")
    body = str(form.get("body") or "")
    ok, reason = moderate_text(f"{title}\n{body}")
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(Post.id).order_by(Post.id.desc()).limit(1))
        last = res.first()
        next_num = 1
        if last and isinstance(last[0], str) and last[0].startswith("p"):
            try:
                next_num = int(last[0][1:]) + 1
            except Exception:
                next_num = 1
        post_id = f"p{next_num}"
        now = _now()
        s.add(
            Post(
                id=post_id,
                type=ptype,
                scope="keep",
                title=title,
                body=body,
                venue_id=venue_id,
                start_at=now - timedelta(hours=1),
                end_at=now + timedelta(hours=6),
                tags=",".join(suggest_tags(title, body)),
                created_at=now,
            )
        )
    return RedirectResponse(url=f"/lost?venue={venue_id}", status_code=303)


async def pets(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    posts = await _get_posts_tagged(venue_obj["id"], "petcare")
    return templates.TemplateResponse(
        request,
        "pets.html",
        {"venues": venues, "venue": venue_obj, "posts": posts, "mode": _mode(request)},
    )


async def pets_new(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    return templates.TemplateResponse(
        request,
        "pets_new.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request)},
    )


async def pets_new_post(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("petcare_post", ip, limit=10, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    form: FormData = await request.form()
    venues = await _get_venues()
    venue_id = str(form.get("venueId") or venues[0]["id"])
    pet_type = str(form.get("petType") or "cat")
    if pet_type not in ("cat", "dog", "other"):
        pet_type = "other"
    try:
        pet_count = int(form.get("petCount") or 1)
    except Exception:
        pet_count = 1
    pet_count = max(1, min(6, pet_count))
    body = str(form.get("body") or "").strip()
    ok, reason = moderate_text(body)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    start_at_in = str(form.get("startAt") or "").strip()
    now = _now()
    start_at = now
    if start_at_in:
        try:
            start_at = datetime.fromisoformat(start_at_in)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_startAt")
        if start_at < now - timedelta(minutes=5):
            raise HTTPException(status_code=400, detail="startAt_in_past")
        if start_at > now + timedelta(days=7):
            raise HTTPException(status_code=400, detail="startAt_too_far")

    title = f"上门喂养：{'猫' if pet_type=='cat' else ('狗' if pet_type=='dog' else '宠物')} ×{pet_count}"
    if body:
        body = f"{body}\n\n（提示：不要写门牌/手机号/微信；首版仅区域可见。）"
    else:
        body = "（请补充喂养次数、是否需要铲屎、交接方式等；不要写门牌/联系方式。）"

    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(Post.id).order_by(Post.id.desc()).limit(1))
        last = res.first()
        next_num = 1
        if last and isinstance(last[0], str) and last[0].startswith("p"):
            try:
                next_num = int(last[0][1:]) + 1
            except Exception:
                next_num = 1
        post_id = f"p{next_num}"
        s.add(
            Post(
                id=post_id,
                type="invite",
                scope="keep",
                title=title,
                body=body,
                venue_id=venue_id,
                start_at=start_at,
                end_at=start_at + timedelta(days=3),
                tags="petcare,help",
                created_at=now,
            )
        )

    await hub.broadcast(f"venue:{venue_id}", {"type": "system", "text": f"新喂养需求：{title}", "ts": now.isoformat()})
    return RedirectResponse(url=f"/pets?venue={venue_id}", status_code=303)


async def companion(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    posts = await _get_posts_tagged(venue_obj["id"], "companion")
    return templates.TemplateResponse(
        request,
        "companion.html",
        {"venues": venues, "venue": venue_obj, "posts": posts, "mode": _mode(request)},
    )


async def companion_new(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    return templates.TemplateResponse(
        request,
        "companion_new.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request)},
    )


async def companion_new_post(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("companion_post", ip, limit=10, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    form: FormData = await request.form()
    venues = await _get_venues()
    venue_id = str(form.get("venueId") or venues[0]["id"])
    kind = str(form.get("kind") or "study")
    if kind not in ("study", "sport", "medical", "city", "other"):
        kind = "other"
    body = str(form.get("body") or "").strip()
    ok, reason = moderate_text(body)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    if any(k in body.lower() for k in ["约炮", "包夜", "性", "裸聊", "上门服务", "陪睡"]):
        raise HTTPException(status_code=400, detail="content_not_allowed")

    start_at_in = str(form.get("startAt") or "").strip()
    now = _now()
    start_at = now
    if start_at_in:
        try:
            start_at = datetime.fromisoformat(start_at_in)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_startAt")
        if start_at < now - timedelta(minutes=5):
            raise HTTPException(status_code=400, detail="startAt_in_past")
        if start_at > now + timedelta(days=7):
            raise HTTPException(status_code=400, detail="startAt_too_far")

    kind_cn = {
        "study": "学习陪伴",
        "sport": "运动陪伴",
        "medical": "就医陪同",
        "city": "城市同行",
        "other": "陪伴",
    }[kind]
    title = f"{kind_cn}（需求）"
    if body:
        body = f"{body}\n\n（提示：请在公共区域会面；不要写住址/联系方式；禁止成人服务与未成年人邀约。）"
    else:
        body = "（请补充时间窗口、集合点、期望边界；不要写住址/联系方式。）"

    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(Post.id).order_by(Post.id.desc()).limit(1))
        last = res.first()
        next_num = 1
        if last and isinstance(last[0], str) and last[0].startswith("p"):
            try:
                next_num = int(last[0][1:]) + 1
            except Exception:
                next_num = 1
        post_id = f"p{next_num}"
        s.add(
            Post(
                id=post_id,
                type="invite",
                scope="keep",
                title=title,
                body=body,
                venue_id=venue_id,
                start_at=start_at,
                end_at=start_at + timedelta(days=1),
                tags="companion,help",
                created_at=now,
            )
        )

    await hub.broadcast(f"venue:{venue_id}", {"type": "system", "text": f"新陪伴需求：{title}", "ts": now.isoformat()})
    return RedirectResponse(url=f"/companion?venue={venue_id}", status_code=303)


async def market(request: Request) -> Response:
    venues = await _get_venues()
    return templates.TemplateResponse(request, "market.html", {"venues": venues, "mode": _mode(request)})


async def charity(request: Request) -> Response:
    venues = await _get_venues()
    mode = _mode(request)
    day = _today_str()
    items: list[dict[str, Any]] = []
    updated_at = ""
    async with session_scope(SessionLocal) as s:
        q = (
            select(BillboardItem)
            .where(BillboardItem.mode == mode, BillboardItem.day == day)
            .order_by(BillboardItem.published_at.desc())
            .limit(16)
        )
        res = await s.execute(q)
        rows = res.scalars().all()
        if not rows:
            # fallback: show yesterday if today empty
            try:
                y = (_now().date() - timedelta(days=1)).isoformat()
            except Exception:
                y = day
            q = (
                select(BillboardItem)
                .where(BillboardItem.mode == mode, BillboardItem.day == y)
                .order_by(BillboardItem.published_at.desc())
                .limit(16)
            )
            res = await s.execute(q)
            rows = res.scalars().all()
            day = y
        for r in rows:
            items.append(
                {
                    "id": r.id,
                    "title": r.title,
                    "source": r.source,
                    "url": r.url,
                    "quote": r.quote,
                    "aiNote": r.ai_note,
                    "publishedAt": r.published_at.isoformat() if getattr(r, "published_at", None) else "",
                }
            )
        if rows:
            try:
                updated_at = max(getattr(r, "created_at") for r in rows).isoformat()
            except Exception:
                updated_at = ""
    return templates.TemplateResponse(
        request,
        "charity.html",
        {"venues": venues, "mode": mode, "items": items, "day": day, "updatedAt": updated_at},
    )


async def hours27(request: Request) -> Response:
    venues = await _get_venues()
    return templates.TemplateResponse(
        request,
        "27hours.html",
        {"venues": venues, "mode": _mode(request)},
    )


async def plan_page(request: Request) -> Response:
    venues = await _get_venues()
    uk = _user_key(request)
    content = ""
    updated_at = ""
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(PlanNote).where(PlanNote.user_key == uk))
        row = res.scalar_one_or_none()
        if row:
            content = str(getattr(row, "content", "") or "")
            try:
                updated_at = getattr(row, "updated_at").isoformat()
            except Exception:
                updated_at = ""
    return templates.TemplateResponse(
        request,
        "plan.html",
        {"venues": venues, "mode": _mode(request), "content": content, "updatedAt": updated_at},
    )


async def api_plan_get(request: Request) -> Response:
    uk = _user_key(request)
    content = ""
    updated_at = ""
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(PlanNote).where(PlanNote.user_key == uk))
        row = res.scalar_one_or_none()
        if row:
            content = str(getattr(row, "content", "") or "")
            try:
                updated_at = getattr(row, "updated_at").isoformat()
            except Exception:
                updated_at = ""
    return JSONResponse({"content": content, "updatedAt": updated_at})


async def api_plan_save(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("plan_save", ip, limit=200, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_json")
    content = str(payload.get("content") or "")
    if len(content) > 20_000:
        content = content[:20_000]
    ok, reason = moderate_text(content)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    uk = _user_key(request)
    now = _now()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(PlanNote).where(PlanNote.user_key == uk))
        row = res.scalar_one_or_none()
        if row:
            row.content = content
            row.updated_at = now
        else:
            s.add(PlanNote(user_key=uk, content=content, updated_at=now))
    return JSONResponse({"ok": True, "updatedAt": now.isoformat()})


def _currency_for_mode(mode: str) -> str:
    m = str(mode or "global").strip().lower()
    if m == "cn":
        return "CNY"
    if m == "hk":
        return "HKD"
    return "HKD"


def _reward_suggest(direction: str, scenario: str, currency: str) -> dict[str, Any]:
    """
    轻量“AI”建议：按常理/人情/工作量给一个区间与分档。
    """
    d = "ask" if str(direction or "").strip().lower() == "ask" else "give"
    s = str(scenario or "").strip()
    sl = s.lower()

    # crude complexity/urgency heuristics
    score = 0
    if any(k in sl for k in ["urgent", "asap", "马上", "紧急", "立刻", "今晚", "现在"]):
        score += 2
    if any(k in sl for k in ["1h", "2h", "3h", "小时", "赶时间", "deadline"]):
        score += 1
    if any(k in sl for k in ["photo", "拍照", "跑腿", "送", "取", "搬", "现场", "陪同", "陪诊"]):
        score += 2
    if any(k in sl for k in ["写", "整理", "ppt", "文档", "翻译", "设计", "代码", "调试"]):
        score += 3
    if any(k in sl for k in ["简单", "顺手", "举手之劳", "几分钟"]):
        score -= 1
    score = max(0, min(8, score))

    # base tiers by currency
    if currency == "CNY":
        base = [6, 12, 18, 28, 38, 58, 88, 128, 188]
    else:
        base = [5, 10, 15, 25, 35, 50, 80, 120, 180]

    idx = min(len(base) - 1, 2 + score)  # start from small tips
    suggested = base[idx]
    low = base[max(0, idx - 2)]
    high = base[min(len(base) - 1, idx + 2)]

    tiers = [low, base[max(0, idx - 1)], suggested, base[min(len(base) - 1, idx + 1)], high]
    tiers = sorted({int(x) for x in tiers if int(x) > 0})

    label = "索取报酬建议" if d == "ask" else "给与报酬建议"
    tip = (
        f"{label}：{currency} {suggested}（常见区间 {currency} {low}–{high}）。"
        f"建议写清楚边界：做什么/不做什么/时间窗口/验收标准。"
    )
    if d == "ask":
        tip += " 索取时可给 2–3 档选择（例如：基础/加急/含跑腿）。"
    else:
        tip += " 打赏时尽量在完成后给，或先给小额定金（如需）。"
    return {"suggested": suggested, "range": [low, high], "tiers": tiers, "tip": tip[:260]}


async def reward_page(request: Request) -> Response:
    venues = await _get_venues()
    venue = request.query_params.get("venue")
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    return templates.TemplateResponse(
        request,
        "reward.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request)},
    )


async def api_reward_suggest(request: Request) -> Response:
    direction = str(request.query_params.get("direction") or "give")
    scenario = str(request.query_params.get("scenario") or "")[:1200]
    cur = _currency_for_mode(_mode(request))
    return JSONResponse({"currency": cur, **_reward_suggest(direction, scenario, cur)})


async def api_reward_log(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("reward_log", ip, limit=120, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_json")
    direction = str(payload.get("direction") or "give").strip().lower()
    if direction not in ("give", "ask"):
        direction = "give"
    scenario = str(payload.get("scenario") or "")[:2000]
    ok, reason = moderate_text(scenario)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    suggested = 0
    try:
        suggested = int(payload.get("suggested") or 0)
    except Exception:
        suggested = 0
    suggested = max(0, min(99999, suggested))
    uk = _user_key(request)
    now = _now()
    rid = f"rw{_today_str().replace('-','')}_{secrets.token_hex(3)}"
    venue_id = str(payload.get("venueId") or "").strip()[:64]
    cur = _currency_for_mode(_mode(request))
    async with session_scope(SessionLocal) as s:
        s.add(
            RewardNote(
                id=rid,
                user_key=uk,
                mode=_mode(request),
                venue_id=venue_id,
                direction=direction,
                scenario=scenario,
                currency=cur,
                suggested=suggested,
                created_at=now,
            )
        )
    return JSONResponse({"ok": True, "id": rid})


async def api_billboard_refresh(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("billboard_refresh", ip, limit=8, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    mode = request.query_params.get("mode") or _mode(request)
    try:
        limit = int(request.query_params.get("limit") or "10")
    except Exception:
        limit = 10
    r = await _refresh_billboard(mode, limit=limit)
    return JSONResponse(r)


async def projects(request: Request) -> Response:
    venues = await _get_venues()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(Creator).order_by(Creator.created_at.desc()))
        creators = res.scalars().all()
        res = await s.execute(select(Work).order_by(Work.created_at.desc()))
        works = res.scalars().all()
        res = await s.execute(select(Tip).order_by(Tip.created_at.desc()).limit(20))
        tips = res.scalars().all()

    creator_list: list[dict[str, Any]] = []
    for c in creators:
        c_works = [w for w in works if w.creator_id == c.id][:6]
        creator_list.append(
            {
                "id": c.id,
                "name": c.display_name,
                "story": c.story,
                "recognition": c.recognition,
                "works": [{"id": w.id, "title": w.title, "desc": w.description} for w in c_works],
            }
        )
    tip_feed = [
        {
            "creatorId": t.creator_id,
            "amount": t.amount,
            "currency": t.currency,
            "message": t.message,
            "createdAt": t.created_at.isoformat(),
        }
        for t in tips
    ]
    return templates.TemplateResponse(
        request,
        "projects.html",
        {"venues": venues, "creators": creator_list, "tips": tip_feed, "mode": _mode(request)},
    )


async def messages(request: Request) -> Response:
    room = request.query_params.get("room") or "venue:v_hk_001"
    venues = await _get_venues()
    return templates.TemplateResponse(
        request,
        "messages.html",
        {"venues": venues, "room": room, "mode": _mode(request)},
    )


async def profile(request: Request) -> Response:
    venues = await _get_venues()
    uk = _user_key(request)
    pid = _public_person_id(uk)
    display_name = ""
    title_line = ""
    name_public = 0
    verified = "none"
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(PersonIdentity).where(PersonIdentity.person_id == pid))
        ident = res.scalar_one_or_none()
        if ident:
            display_name = str(getattr(ident, "display_name", "") or "").strip()
            title_line = str(getattr(ident, "title", "") or "").strip()
            try:
                name_public = 1 if int(getattr(ident, "name_public", 0) or 0) == 1 else 0
            except Exception:
                name_public = 0
            verified = str(getattr(ident, "verified", "none") or "none").strip().lower() or "none"
            if verified not in ("none", "pending", "verified"):
                verified = "none"
        res = await s.execute(select(PersonPrivacy).where(PersonPrivacy.person_id == pid))
        pp = res.scalar_one_or_none()
        if pp is None:
            visibility = "public"
        else:
            visibility = str(getattr(pp, "visibility", "") or "").strip().lower()
            if visibility not in ("public", "private", "venue_verified"):
                visibility = "private" if (int(pp.is_public or 1) == 0) else "public"
        res = await s.execute(select(UserCard).where(UserCard.user_key == uk).order_by(UserCard.created_at.desc()).limit(60))
        cards = res.scalars().all()
        res = await s.execute(select(Tip).where(Tip.user_key == uk).order_by(Tip.created_at.desc()).limit(20))
        mytips = res.scalars().all()
        res = await s.execute(
            select(CardEntry)
            .where(CardEntry.person_id == pid, CardEntry.status == "active")
            .order_by(CardEntry.created_at.desc())
            .limit(60)
        )
        entries = res.scalars().all()
    card_list = [
        {"title": c.title, "rarity": c.rarity, "kind": c.kind, "createdAt": c.created_at.isoformat()} for c in cards
    ]
    tip_list = [{"creatorId": t.creator_id, "amount": t.amount, "currency": t.currency, "message": t.message} for t in mytips]
    entry_list = [
        {
            "display": e.display,
            "authorLabel": (e.author_label if e.display == "signed" and e.author_label else "Name"),
            "body": e.body,
            "createdAt": e.created_at.isoformat(),
        }
        for e in entries
    ]
    presence_mode = await _presence_mode(uk)
    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "venues": venues,
            "cards": card_list,
            "tips": tip_list,
            "entries": entry_list,
            "personId": pid,
            "cardUrl": f"/card/{pid}",
            "visibility": visibility,
            "mode": _mode(request),
            "displayName": display_name,
            "titleLine": title_line,
            "namePublic": name_public,
            "verified": verified,
            "presenceMode": presence_mode,
        },
    )


async def profile_privacy_post(request: Request) -> Response:
    form: FormData = await request.form()
    v = str(form.get("privacy") or "").strip().lower()
    if v not in ("public", "private", "venue_verified"):
        v = "public"
    is_public = (v == "public")
    uk = _user_key(request)
    pid = _public_person_id(uk)
    now = _now()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(PersonPrivacy).where(PersonPrivacy.person_id == pid))
        row = res.scalar_one_or_none()
        if row:
            row.is_public = 1 if is_public else 0
            row.visibility = v
            row.updated_at = now
        else:
            s.add(PersonPrivacy(person_id=pid, is_public=1 if is_public else 0, visibility=v, updated_at=now))
    return RedirectResponse(url="/profile", status_code=303)


async def identity_post(request: Request) -> Response:
    """
    首页 Name Card：保存姓名/Title/是否公示（首版：软信息，后续再接强身份验证）。
    """
    form: FormData = await request.form()
    name = str(form.get("displayName") or "").strip()
    title_line = str(form.get("titleLine") or "").strip()
    name_public = str(form.get("namePublic") or "").strip().lower()
    pub = 1 if name_public in ("1", "true", "yes", "on", "public") else 0

    # hard limits
    if len(name) > 80:
        name = name[:80]
    if len(title_line) > 80:
        title_line = title_line[:80]

    mode = str(form.get("mode") or _mode(request)).strip().lower() or _mode(request)
    venue = str(form.get("venue") or "").strip()
    next_url = str(form.get("next") or "").strip()

    uk = _user_key(request)
    pid = _public_person_id(uk)
    now = _now()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(PersonIdentity).where(PersonIdentity.person_id == pid))
        row = res.scalar_one_or_none()
        if row:
            row.display_name = name
            row.title = title_line
            row.name_public = pub
            row.updated_at = now
        else:
            s.add(
                PersonIdentity(
                    person_id=pid,
                    display_name=name,
                    title=title_line,
                    name_public=pub,
                    verified="none",
                    updated_at=now,
                )
            )
    # safe redirect
    if next_url and next_url.startswith("/") and (not next_url.startswith("//")) and ("\n" not in next_url) and ("\r" not in next_url):
        return RedirectResponse(url=next_url, status_code=303)
    qp = f"?mode={mode}"
    if venue:
        qp += f"&venue={venue}"
    return RedirectResponse(url=f"/{qp}", status_code=303)


async def tip_create(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("tip", ip, limit=30, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    form: FormData = await request.form()
    creator_id = str(form.get("creatorId") or "").strip()
    if not creator_id:
        raise HTTPException(status_code=400, detail="creatorId_required")
    try:
        amount = int(form.get("amount") or 0)
    except Exception:
        amount = 0
    if amount <= 0:
        raise HTTPException(status_code=400, detail="invalid_amount")
    mode = _mode(request)
    currency = str(form.get("currency") or ("CNY" if mode == "cn" else "HKD")).upper()
    if mode == "cn":
        currency = "CNY"
    elif mode in ("hk", "global"):
        currency = "HKD"
    _ = str(form.get("paymentMethod") or "")  # placeholder for future PSP integration
    message = str(form.get("message") or "").strip()[:240]
    ok, reason = moderate_text(message)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    uk = _user_key(request)
    now = _now()

    async with session_scope(SessionLocal) as s:
        # ensure creator exists
        res = await s.execute(select(Creator).where(Creator.id == creator_id))
        creator = res.scalar_one_or_none()
        if not creator:
            raise HTTPException(status_code=404, detail="creator_not_found")

        res = await s.execute(select(Tip.id).order_by(Tip.id.desc()).limit(1))
        last = res.first()
        next_num = 1
        if last and isinstance(last[0], str) and last[0].startswith("t"):
            try:
                next_num = int(last[0][1:]) + 1
            except Exception:
                next_num = 1
        tip_id = f"t{next_num}"
        s.add(Tip(id=tip_id, creator_id=creator_id, user_key=uk, amount=amount, currency=currency, message=message, created_at=now))

        # mint a collectible card
        rarity = "common"
        if amount >= 500:
            rarity = "epic"
        elif amount >= 100:
            rarity = "rare"
        res = await s.execute(select(UserCard.id).order_by(UserCard.id.desc()).limit(1))
        last = res.first()
        next_num = 1
        if last and isinstance(last[0], str) and last[0].startswith("uc"):
            try:
                next_num = int(last[0][2:]) + 1
            except Exception:
                next_num = 1
        card_id = f"uc{next_num}"
        card_title = f"感谢卡：{creator.display_name}"
        s.add(UserCard(id=card_id, user_key=uk, kind="thanks", title=card_title, rarity=rarity, meta="", created_at=now))

    # realtime: broadcast a living feed event
    await hub.broadcast("global", {"type": "event", "event": "tip_created", "creatorId": creator_id, "amount": amount, "currency": currency})
    await hub.broadcast(f"creator:{creator_id}", {"type": "event", "event": "tip_created", "amount": amount, "currency": currency})

    return RedirectResponse(url="/profile", status_code=303)

async def auth(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    return templates.TemplateResponse(
        request,
        "auth.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request)},
    )


async def card_view(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    raw = str(request.path_params.get("personId") or "").strip()
    person_id = _normalize_person_id(raw)
    if not person_id:
        raise HTTPException(status_code=400, detail="personId_required")
    if raw and raw != person_id:
        # canonical redirect to public person id
        return RedirectResponse(url=f"/card/{person_id}?venue={venue_obj['id']}", status_code=302)
    me_pid = _public_person_id(_user_key(request))
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(PersonPrivacy).where(PersonPrivacy.person_id == person_id))
        pp = res.scalar_one_or_none()
        if pp is None:
            visibility = "public"
        else:
            visibility = str(getattr(pp, "visibility", "") or "").strip().lower()
            if visibility not in ("public", "private", "venue_verified"):
                visibility = "private" if (int(pp.is_public or 1) == 0) else "public"
    if person_id != me_pid:
        if visibility == "private":
            return templates.TemplateResponse(
                request,
                "card_private.html",
                {"venues": venues, "venue": venue_obj, "mode": _mode(request), "personId": person_id, "reason": "private"},
                status_code=404,
            )
        if visibility == "venue_verified":
            room = f"venue:{venue_obj['id']}"
            owner_present = any(_public_person_id(k) == person_id for k in hub.presence_keys(room))
            viewer_ok = await _viewer_verified_in_venue(_user_key(request), venue_obj["id"])
            if (not owner_present) or (not viewer_ok):
                return templates.TemplateResponse(
                    request,
                    "card_private.html",
                    {
                        "venues": venues,
                        "venue": venue_obj,
                        "mode": _mode(request),
                        "personId": person_id,
                        "reason": "venue_verified",
                    },
                    status_code=404,
                )
    async with session_scope(SessionLocal) as s:
        res = await s.execute(
            select(CardEntry)
            .where(CardEntry.person_id == person_id, CardEntry.status == "active")
            .order_by(CardEntry.created_at.desc())
            .limit(80)
        )
        entries = res.scalars().all()
        res = await s.execute(select(PersonIdentity).where(PersonIdentity.person_id == person_id))
        ident = res.scalar_one_or_none()
        ident_name = ""
        ident_title = ""
        if ident and (person_id == me_pid or int(getattr(ident, "name_public", 0) or 0) == 1):
            ident_name = str(getattr(ident, "display_name", "") or "").strip()
            ident_title = str(getattr(ident, "title", "") or "").strip()
    entry_list = [
        {
            "display": e.display,
            "authorLabel": (e.author_label if e.display == "signed" and e.author_label else "匿名"),
            "body": e.body,
            "createdAt": e.created_at.isoformat(),
        }
        for e in entries
    ]
    return templates.TemplateResponse(
        request,
        "card.html",
        {
            "venues": venues,
            "venue": venue_obj,
            "mode": _mode(request),
            "personId": person_id,
            "entries": entry_list,
            "displayName": ident_name,
            "titleLine": ident_title,
        },
    )


async def card_entry_new(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("card_entry", ip, limit=40, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    raw = str(request.path_params.get("personId") or "").strip()
    person_id = _normalize_person_id(raw)
    if not person_id:
        raise HTTPException(status_code=400, detail="personId_required")
    me_pid = _public_person_id(_user_key(request))
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(PersonPrivacy).where(PersonPrivacy.person_id == person_id))
        pp = res.scalar_one_or_none()
        if pp is None:
            visibility = "public"
        else:
            visibility = str(getattr(pp, "visibility", "") or "").strip().lower()
            if visibility not in ("public", "private", "venue_verified"):
                visibility = "private" if (int(pp.is_public or 1) == 0) else "public"
    if person_id != me_pid:
        if visibility == "private":
            raise HTTPException(status_code=404, detail="card_private")
        if visibility == "venue_verified":
            venue = request.query_params.get("venue")
            venues = await _get_venues()
            selected = venue or _default_venue_id(_mode(request), venues)
            room = f"venue:{selected}"
            owner_present = any(_public_person_id(k) == person_id for k in hub.presence_keys(room))
            viewer_ok = await _viewer_verified_in_venue(_user_key(request), selected)
            if (not owner_present) or (not viewer_ok):
                raise HTTPException(status_code=404, detail="card_venue_verified_only")
    form: FormData = await request.form()
    display = str(form.get("display") or "anon").strip().lower()
    if display not in ("anon", "signed"):
        display = "anon"
    author_label = str(form.get("authorLabel") or "").strip()[:40]
    body = str(form.get("body") or "").strip()
    ack = str(form.get("ack") or "").strip().lower()
    if ack not in ("1", "on", "true", "yes"):
        raise HTTPException(status_code=400, detail="ack_required")
    if len(body) < 6:
        raise HTTPException(status_code=400, detail="too_short")
    if len(body) > 600:
        body = body[:600]
    ok, reason = moderate_text(body)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    uk = _user_key(request)
    if not _allow("card_entry_by_user", uk, limit=10, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    now = _now()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(CardEntry.id).order_by(CardEntry.id.desc()).limit(1))
        last = res.first()
        next_num = 1
        if last and isinstance(last[0], str) and last[0].startswith("ce"):
            try:
                next_num = int(last[0][2:]) + 1
            except Exception:
                next_num = 1
        eid = f"ce{next_num}"
        if display == "signed" and not author_label:
            author_label = _anon_name(uk)
        if display != "signed":
            author_label = ""
        s.add(
            CardEntry(
                id=eid,
                person_id=person_id,
                author_key=uk,
                display=display,
                author_label=author_label,
                body=body,
                status="active",
                created_at=now,
            )
        )
    return RedirectResponse(url=f"/card/{person_id}", status_code=303)

async def _get_reports(
    venue_id: str,
    limit: int = 20,
    user_key: str | None = None,
) -> list[dict[str, Any]]:
    async with session_scope(SessionLocal) as s:
        q = select(SafetyReport).where(SafetyReport.venue_id == venue_id)
        if user_key:
            q = q.where(SafetyReport.user_key == user_key)
        q = q.order_by(SafetyReport.created_at.desc()).limit(limit)
        res = await s.execute(q)
        rs = res.scalars().all()

        # fetch author public display names (for signed bulletins only)
        ukeys = {str(getattr(r, "user_key", "") or "") for r in rs if getattr(r, "author_display", "anon") == "signed"}
        pid_map: dict[str, str] = {}
        name_map: dict[str, str] = {}
        pub_map: dict[str, int] = {}
        for uk in ukeys:
            pid_map[uk] = _public_person_id(uk)
        if pid_map:
            res = await s.execute(select(PersonIdentity).where(PersonIdentity.person_id.in_(list(pid_map.values()))))
            idents = res.scalars().all()
            for it in idents:
                pid = str(getattr(it, "person_id", "") or "")
                name_map[pid] = str(getattr(it, "display_name", "") or "").strip()
                try:
                    pub_map[pid] = 1 if int(getattr(it, "name_public", 0) or 0) == 1 else 0
                except Exception:
                    pub_map[pid] = 0

    out: list[dict[str, Any]] = []
    for r in rs:
        author_display = str(getattr(r, "author_display", "anon") or "anon").strip().lower()
        if author_display not in ("anon", "signed"):
            author_display = "anon"
        publish_request = 1 if int(getattr(r, "publish_request", 0) or 0) == 1 else 0
        author_label = ""
        if bool(r.is_public) and author_display == "signed":
            pid = pid_map.get(str(getattr(r, "user_key", "") or ""), "")
            if pid and pub_map.get(pid, 0) == 1:
                author_label = name_map.get(pid, "") or ""
        out.append(
            {
                "id": r.id,
                "venueId": r.venue_id,
                "category": r.category,
                "summary": r.summary,
                "details": r.details,
                "status": r.status,
                "isPublic": bool(r.is_public),
                "publicNote": r.public_note,
                "evidenceUrl": (f"/static/{r.evidence_path}" if getattr(r, "evidence_path", "") else ""),
                "publishRequest": bool(publish_request),
                "authorDisplay": author_display,
                "authorLabel": author_label,
                "createdAt": r.created_at.isoformat(),
            }
        )
    return out


def _score_bucket(score: int) -> str:
    try:
        s = int(score)
    except Exception:
        s = 50
    if s <= 39:
        return "low"
    if s <= 69:
        return "mid"
    return "high"


async def _get_safety_opinions(
    venue_id: str,
    limit: int = 30,
    user_key: str | None = None,
) -> list[dict[str, Any]]:
    async with session_scope(SessionLocal) as s:
        res = await s.execute(
            select(SafetyOpinion)
            .where(SafetyOpinion.venue_id == venue_id)
            .order_by(SafetyOpinion.created_at.desc())
            .limit(limit)
        )
        ops = res.scalars().all()
        ids = [str(getattr(o, "id", "") or "") for o in ops if getattr(o, "id", None)]
        my_votes: dict[str, int] = {}
        counts: dict[str, dict[str, int]] = {oid: {"low": 0, "mid": 0, "high": 0, "total": 0} for oid in ids}
        if ids:
            res = await s.execute(select(SafetyOpinionVote).where(SafetyOpinionVote.opinion_id.in_(ids)))
            vs = res.scalars().all()
            for v in vs:
                oid = str(getattr(v, "opinion_id", "") or "")
                if not oid:
                    continue
                b = _score_bucket(int(getattr(v, "score", 50) or 50))
                if oid not in counts:
                    counts[oid] = {"low": 0, "mid": 0, "high": 0, "total": 0}
                counts[oid][b] = int(counts[oid].get(b, 0)) + 1
                counts[oid]["total"] = int(counts[oid].get("total", 0)) + 1
                if user_key and str(getattr(v, "user_key", "") or "") == user_key:
                    my_votes[oid] = int(getattr(v, "score", 50) or 50)

    out: list[dict[str, Any]] = []
    for o in ops:
        oid = str(getattr(o, "id", "") or "")
        kind = str(getattr(o, "kind", "public") or "public").strip().lower()
        if kind not in ("pro", "public"):
            kind = "public"
        cred_status = str(getattr(o, "credential_status", "none") or "none").strip().lower()
        if cred_status not in ("none", "pending", "verified", "rejected"):
            cred_status = "none"
        stat = counts.get(oid, {"low": 0, "mid": 0, "high": 0, "total": 0})
        total = max(0, int(stat.get("total", 0) or 0))
        def pct(n: int) -> int:
            if total <= 0:
                return 0
            try:
                return int(round(100 * (int(n) / total)))
            except Exception:
                return 0

        out.append(
            {
                "id": oid,
                "venueId": str(getattr(o, "venue_id", "") or ""),
                "kind": kind,
                "credStatus": cred_status,
                "author": _anon_name(str(getattr(o, "user_key", "") or "")),
                "title": str(getattr(o, "title", "") or "").strip(),
                "body": str(getattr(o, "body", "") or "").strip(),
                "createdAt": getattr(o, "created_at").isoformat() if getattr(o, "created_at", None) else "",
                "votes": {
                    "total": total,
                    "low": int(stat.get("low", 0) or 0),
                    "mid": int(stat.get("mid", 0) or 0),
                    "high": int(stat.get("high", 0) or 0),
                    "pctLow": pct(int(stat.get("low", 0) or 0)),
                    "pctMid": pct(int(stat.get("mid", 0) or 0)),
                    "pctHigh": pct(int(stat.get("high", 0) or 0)),
                },
                "myScore": (my_votes.get(oid) if user_key else None),
            }
        )
    return out


async def safety(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    uk = _user_key(request)
    reports = await _get_reports(venue_obj["id"], limit=20, user_key=uk)
    opinions = await _get_safety_opinions(venue_obj["id"], limit=30, user_key=uk)
    return templates.TemplateResponse(
        request,
        "safety.html",
        {"venues": venues, "venue": venue_obj, "reports": reports, "opinions": opinions, "mode": _mode(request)},
    )


async def safety_report(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    pre = {
        "category": "",
        "summary": "",
        "details": "",
    }
    try:
        cat = str(request.query_params.get("category") or "").strip().lower()
        if cat in ("scam", "harassment", "safety", "privacy", "dispute", "feedback", "other"):
            pre["category"] = cat
    except Exception:
        pass
    try:
        pre["summary"] = str(request.query_params.get("summary") or "").strip()[:240]
        pre["details"] = str(request.query_params.get("details") or "").strip()[:1800]
    except Exception:
        pass
    return templates.TemplateResponse(
        request,
        "safety_report.html",
        {
            "venues": venues,
            "venue": venue_obj,
            "mode": _mode(request),
            "nextUrl": f"/safety/report?venue={venue_obj['id']}",
            "prefill": pre,
        },
    )


async def realname(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    uk = _user_key(request)
    row = None
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(RealNameRecord).where(RealNameRecord.user_key == uk))
        row = res.scalar_one_or_none()
    next_url = str(request.query_params.get("next") or "").strip()
    if not (next_url and next_url.startswith("/") and (not next_url.startswith("//")) and ("\n" not in next_url) and ("\r" not in next_url)):
        next_url = f"/safety/report?venue={venue_obj['id']}"
    rec = {
        "legalName": (getattr(row, "legal_name", "") if row else ""),
        "contact": (getattr(row, "contact", "") if row else ""),
        "idLast4": (getattr(row, "id_last4", "") if row else ""),
        "statementOk": int(getattr(row, "statement_ok", 0) if row else 0),
    }
    return templates.TemplateResponse(
        request,
        "realname.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request), "nextUrl": next_url, "rec": rec},
    )


async def realname_post(request: Request) -> Response:
    form: FormData = await request.form()
    legal = str(form.get("legalName") or "").strip()
    contact = str(form.get("contact") or "").strip()
    id_last4 = str(form.get("idLast4") or "").strip()
    ok = str(form.get("statementOk") or "").strip().lower()
    statement_ok = 1 if ok in ("1", "true", "yes", "on") else 0
    if not legal:
        raise HTTPException(status_code=400, detail="legal_name_required")
    if not contact:
        raise HTTPException(status_code=400, detail="contact_required")
    if id_last4 and (not re.fullmatch(r"[0-9a-zA-Z]{4,8}", id_last4)):
        raise HTTPException(status_code=400, detail="id_last4_invalid")
    if statement_ok != 1:
        raise HTTPException(status_code=400, detail="statement_required")

    # hard limits
    legal = legal[:80]
    contact = contact[:120]
    id_last4 = id_last4[:8]

    uk = _user_key(request)
    now = _now()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(RealNameRecord).where(RealNameRecord.user_key == uk))
        row = res.scalar_one_or_none()
        if row:
            row.legal_name = legal
            row.contact = contact
            row.id_last4 = id_last4
            row.statement_ok = statement_ok
            row.updated_at = now
        else:
            s.add(
                RealNameRecord(
                    user_key=uk,
                    legal_name=legal,
                    contact=contact,
                    id_last4=id_last4,
                    statement_ok=statement_ok,
                    updated_at=now,
                )
            )
        # mark identity as pending (platform has record; manual verification can be added later)
        pid = _public_person_id(uk)
        res = await s.execute(select(PersonIdentity).where(PersonIdentity.person_id == pid))
        ident = res.scalar_one_or_none()
        if ident:
            if str(getattr(ident, "verified", "") or "").strip().lower() == "none":
                ident.verified = "pending"
            ident.updated_at = now

    next_url = str(form.get("next") or "").strip()
    if next_url and next_url.startswith("/") and (not next_url.startswith("//")) and ("\n" not in next_url) and ("\r" not in next_url):
        return RedirectResponse(url=next_url, status_code=303)
    return RedirectResponse(url="/safety", status_code=303)


async def safety_report_post(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("safety_report", ip, limit=10, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")

    form: FormData = await request.form()
    # 平台实名留档：未留档则不允许提交
    uk = _user_key(request)
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(RealNameRecord.user_key).where(RealNameRecord.user_key == uk))
        if res.first() is None:
            venue_id0 = str(form.get("venueId") or (await _get_venues())[0]["id"])
            next_url = f"/safety/report?venue={venue_id0}"
            return RedirectResponse(url=f"/realname?venue={venue_id0}&next={urllib.parse.quote(next_url)}", status_code=303)
    venue_id = str(form.get("venueId") or (await _get_venues())[0]["id"])
    category = str(form.get("category") or "other")
    if category not in ("scam", "harassment", "safety", "privacy", "dispute", "feedback", "other"):
        category = "other"
    summary = str(form.get("summary") or "").strip()
    details = str(form.get("details") or "")
    public_mode = str(form.get("publicMode") or "private").strip().lower()
    publish_request = 1 if public_mode in ("public_anon", "public_signed") else 0
    author_display = "signed" if public_mode == "public_signed" else "anon"
    ok, reason = moderate_text(f"{summary}\n{details}")
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    if not summary:
        raise HTTPException(status_code=400, detail="summary_required")

    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(SafetyReport.id).order_by(SafetyReport.id.desc()).limit(1))
        last = res.first()
        next_num = 1
        if last and isinstance(last[0], str) and last[0].startswith("r"):
            try:
                next_num = int(last[0][1:]) + 1
            except Exception:
                next_num = 1
        rid = f"r{next_num}"
        now = _now()
        evidence_path = ""
        evidence = form.get("evidence")
        if isinstance(evidence, UploadFile):
            raw = await evidence.read()
        evidence_path = _save_upload_evidence(
                raw,
                (evidence.content_type or ""),
                (evidence.filename or ""),
                "report",
                rid,
            )
        s.add(
            SafetyReport(
                id=rid,
                venue_id=venue_id,
                user_key=uk,
                category=category,
                summary=summary[:240],
                details=details,
                status="received",
                is_public=0,
                public_note="",
                evidence_path=evidence_path,
                publish_request=publish_request,
                author_display=author_display,
                created_at=now,
            )
        )

    return RedirectResponse(url=f"/safety?venue={venue_id}", status_code=303)


async def safety_opinion_post(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("safety_opinion", ip, limit=18, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")

    form: FormData = await request.form()
    venue_id = str(form.get("venueId") or (await _get_venues())[0]["id"]).strip()

    # 平台实名留档：未留档则不允许参与互动板（避免无成本灌水）
    uk = _user_key(request)
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(RealNameRecord.user_key).where(RealNameRecord.user_key == uk))
        if res.first() is None:
            next_url = f"/safety?venue={venue_id}#opinions"
            return RedirectResponse(url=f"/realname?venue={venue_id}&next={urllib.parse.quote(next_url)}", status_code=303)

    kind = str(form.get("kind") or "public").strip().lower()
    if kind not in ("pro", "public"):
        kind = "public"
    title = str(form.get("title") or "").strip()[:160]
    body = str(form.get("body") or "").strip()[:2200]
    if not title:
        raise HTTPException(status_code=400, detail="title_required")

    ok, reason = moderate_text(f"{title}\n{body}")
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    cred_path = ""
    cred_status = "none"
    cred = form.get("credential")
    if kind == "pro":
        if not isinstance(cred, UploadFile):
            raise HTTPException(status_code=400, detail="credential_required")
        raw = await cred.read()
        cred_path = _save_upload_evidence(raw, (cred.content_type or ""), (cred.filename or ""), "lawyer", title[:24] or "so")
        cred_status = "pending"

    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(SafetyOpinion.id).order_by(SafetyOpinion.id.desc()).limit(1))
        last = res.first()
        next_num = 1
        if last and isinstance(last[0], str) and last[0].startswith("so"):
            try:
                next_num = int(last[0][2:]) + 1
            except Exception:
                next_num = 1
        oid = f"so{next_num}"
        now = _now()
        s.add(
            SafetyOpinion(
                id=oid,
                venue_id=venue_id,
                user_key=uk,
                kind=kind,
                title=title,
                body=body,
                credential_path=cred_path,
                credential_status=cred_status,
                created_at=now,
            )
        )
    return RedirectResponse(url=f"/safety?venue={venue_id}#opinions", status_code=303)


async def safety_opinion_vote_post(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("safety_opinion_vote", ip, limit=60, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")

    form: FormData = await request.form()
    venue_id = str(form.get("venueId") or (await _get_venues())[0]["id"]).strip()
    opinion_id = str(form.get("opinionId") or "").strip()[:64]
    if not opinion_id:
        raise HTTPException(status_code=400, detail="opinionId_required")

    # 同样要求平台实名留档（反作弊）
    uk = _user_key(request)
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(RealNameRecord.user_key).where(RealNameRecord.user_key == uk))
        if res.first() is None:
            next_url = f"/safety?venue={venue_id}#opinions"
            return RedirectResponse(url=f"/realname?venue={venue_id}&next={urllib.parse.quote(next_url)}", status_code=303)

    try:
        score = int(str(form.get("score") or "50").strip())
    except Exception:
        score = 50
    score = max(0, min(100, score))

    now = _now()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(
            select(SafetyOpinionVote).where(SafetyOpinionVote.opinion_id == opinion_id, SafetyOpinionVote.user_key == uk)
        )
        row = res.scalar_one_or_none()
        if row:
            row.score = score
            row.created_at = now
        else:
            s.add(SafetyOpinionVote(opinion_id=opinion_id, user_key=uk, score=score, created_at=now))
    return RedirectResponse(url=f"/safety?venue={venue_id}#opinions", status_code=303)


async def safety_bulletins(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    reports = await _get_reports(venue_obj["id"], limit=80, user_key=None)
    bulletins = [r for r in reports if r.get("isPublic")]
    return templates.TemplateResponse(
        request,
        "safety_bulletins.html",
        {"venues": venues, "venue": venue_obj, "bulletins": bulletins, "mode": _mode(request)},
    )


async def safety_plus(request: Request) -> Response:
    venues = await _get_venues()
    return templates.TemplateResponse(request, "safety_plus.html", {"venues": venues, "mode": _mode(request)})

async def _get_legal_tickets(venue_id: str, limit: int = 20) -> list[dict[str, Any]]:
    async with session_scope(SessionLocal) as s:
        q = (
            select(LegalTicket)
            .where(LegalTicket.venue_id == venue_id)
            .order_by(LegalTicket.created_at.desc())
            .limit(limit)
        )
        res = await s.execute(q)
        ts = res.scalars().all()
    out: list[dict[str, Any]] = []
    for t in ts:
        out.append(
            {
                "id": t.id,
                "venueId": t.venue_id,
                "kind": t.kind,
                "topic": t.topic,
                "summary": t.summary,
                "details": t.details,
                "status": t.status,
                "createdAt": t.created_at.isoformat(),
            }
        )
    return out


async def legal(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    tickets = await _get_legal_tickets(venue_obj["id"], limit=10)
    return templates.TemplateResponse(
        request,
        "legal.html",
        {"venues": venues, "venue": venue_obj, "tickets": tickets, "mode": _mode(request)},
    )


async def legal_probono(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    return templates.TemplateResponse(
        request,
        "legal_probono.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request)},
    )


async def legal_ticket_new(request: Request) -> Response:
    venue = request.query_params.get("venue")
    venues = await _get_venues()
    selected = venue or _default_venue_id(_mode(request), venues)
    venue_obj = next((v for v in venues if v["id"] == selected), venues[0])
    return templates.TemplateResponse(
        request,
        "legal_ticket_new.html",
        {"venues": venues, "venue": venue_obj, "mode": _mode(request)},
    )


async def legal_ticket_new_post(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("legal_ticket", ip, limit=10, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")

    form: FormData = await request.form()
    venue_id = str(form.get("venueId") or (await _get_venues())[0]["id"])
    kind = str(form.get("kind") or "pro_bono")
    if kind not in ("pro_bono", "paid", "referral"):
        kind = "pro_bono"
    topic = str(form.get("topic") or "other")
    if topic not in ("defamation", "harassment", "contract", "consumer", "privacy", "other"):
        # note: defamation reserved for later; keep list strict
        topic = "other"
    summary = str(form.get("summary") or "").strip()
    details = str(form.get("details") or "")
    ok, reason = moderate_text(f"{summary}\n{details}")
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    if not summary:
        raise HTTPException(status_code=400, detail="summary_required")

    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(LegalTicket.id).order_by(LegalTicket.id.desc()).limit(1))
        last = res.first()
        next_num = 1
        if last and isinstance(last[0], str) and last[0].startswith("l"):
            try:
                next_num = int(last[0][1:]) + 1
            except Exception:
                next_num = 1
        lid = f"l{next_num}"
        now = _now()
        s.add(
            LegalTicket(
                id=lid,
                venue_id=venue_id,
                kind=kind,
                topic=topic,
                summary=summary[:240],
                details=details,
                status="queued",
                created_at=now,
            )
        )
    return RedirectResponse(url=f"/legal?venue={venue_id}", status_code=303)


# ---- API (minimal, no pydantic) ----


async def api_venues(_: Request) -> Response:
    return JSONResponse(await _get_venues())


async def api_venues_geo(_: Request) -> Response:
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(Venue))
        venues = res.scalars().all()
        res = await s.execute(select(VenueGeo))
        geos = res.scalars().all()
    geo_map: dict[str, VenueGeo] = {g.venue_id: g for g in geos}
    out: list[dict[str, Any]] = []
    for v in venues:
        g = geo_map.get(v.id)
        if not g:
            continue
        out.append(
            {
                "id": v.id,
                "name": v.name,
                "city": v.city,
                "lat": float(g.lat),
                "lng": float(g.lng),
                "radiusM": int(g.radius_m),
            }
        )
    return JSONResponse(out)


async def api_universe(request: Request) -> Response:
    venue_id = str(request.query_params.get("venueId") or "").strip()
    if not venue_id:
        raise HTTPException(status_code=400, detail="venueId_required")
    room = f"venue:{venue_id}"

    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(Venue).where(Venue.id == venue_id))
        v = res.scalar_one_or_none()

    me_pid = _public_person_id(_user_key(request))

    # People nodes (nearby in this venue) - respect privacy
    people_keys = hub.presence_keys(room)
    pids = [_public_person_id(k) for k in people_keys]
    vmap = await _privacy_vis_map(pids + [me_pid])
    viewer_ok = await _viewer_verified_in_venue(_user_key(request), venue_id)
    hidden_count = 0
    people: list[dict[str, Any]] = []
    for k in people_keys:
        pid = _public_person_id(k)
        vis = vmap.get(pid, "public")
        if pid != me_pid:
            if vis == "private":
                hidden_count += 1
                continue
            if vis == "venue_verified" and (not viewer_ok):
                hidden_count += 1
                continue
        people.append(
            {
                "id": pid,
                "kind": "person",
                "code": _planet_code(pid),
                "title": ("我" if pid == me_pid else _anon_name(k)),
                "subtitle": "信息名片",
                "cardUrl": f"/card/{pid}",
                "isMe": bool(pid == me_pid),
            }
        )
    # Ensure "me" exists even if not present (MVP stability)
    if not any(p.get("id") == me_pid for p in people):
        people.append(
            {
                "id": me_pid,
                "kind": "person",
                "code": _planet_code(me_pid),
                "title": "我",
                "subtitle": "信息名片",
                "cardUrl": f"/card/{me_pid}",
                "isMe": True,
            }
        )

    # Live/event nodes (recent)
    events = []
    for ev in hub.recent_events(room, limit=8):
        txt = str(ev.get("text") or "")[:120]
        if not txt:
            continue
        hid = hashlib.sha256(txt.encode("utf-8", errors="ignore")).hexdigest()[:10]
        events.append(
            {
                "id": f"e_{hid}",
                "kind": "event",
                "code": "LIVE",
                "title": txt,
                "subtitle": "这里有什么 live",
            }
        )

    venue_label = f"{v.name} · {v.city}" if v else venue_id

    core = {
        "id": f"v_{venue_id}",
        "kind": "venue",
        "code": "CORE",
        "title": venue_label,
        "subtitle": "场所（中心）",
    }

    hidden_node = None
    if hidden_count > 0:
        hidden_node = {
            "id": f"priv_{venue_id}",
            "kind": "hidden",
            "code": "PRIV",
            "title": f"隐私星×{hidden_count}",
            "subtitle": "有人选择不公开名片",
        }

    return JSONResponse(
        {
            "venueId": venue_id,
            "core": core,
            "people": people,
            "events": events,
            "hidden": hidden_node,
            "me": {"personId": me_pid},
        }
    )


async def api_venues_nearest(request: Request) -> Response:
    try:
        lat = float(request.query_params.get("lat"))
        lng = float(request.query_params.get("lng"))
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_lat_lng")

    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(VenueGeo))
        geos = res.scalars().all()
        if not geos:
            raise HTTPException(status_code=404, detail="no_venues")

        best: tuple[float, VenueGeo] | None = None
        for g in geos:
            d = _haversine_m(lat, lng, float(g.lat), float(g.lng))
            if best is None or d < best[0]:
                best = (d, g)
        assert best is not None
        dist_m, geo = best

        res = await s.execute(select(Venue).where(Venue.id == geo.venue_id))
        v = res.scalar_one_or_none()
        if not v:
            raise HTTPException(status_code=404, detail="venue_not_found")

    return JSONResponse(
        {
            "venue": {"id": v.id, "name": v.name, "city": v.city},
            "distanceM": int(dist_m),
            "radiusM": int(geo.radius_m),
        }
    )


async def api_now_presence(request: Request) -> Response:
    venue_id = str(request.query_params.get("venueId") or "").strip()
    if not venue_id:
        raise HTTPException(status_code=400, detail="venueId_required")
    room = f"venue:{venue_id}"
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(Venue).where(Venue.id == venue_id))
        v = res.scalar_one_or_none()
    label = f"{v.name} · {v.city}" if v else venue_id
    viewer_pid = _public_person_id(_user_key(request))
    keys = hub.presence_keys(room)
    pids = [_public_person_id(k) for k in keys]
    vmap = await _privacy_vis_map(pids)
    viewer_ok = await _viewer_verified_in_venue(_user_key(request), venue_id)
    public_entities: list[dict[str, Any]] = []
    hidden_count = 0
    for k in keys:
        pid = _public_person_id(k)
        vis = vmap.get(pid, "public")
        if pid != viewer_pid:
            if vis == "private":
                hidden_count += 1
                continue
            if vis == "venue_verified" and (not viewer_ok):
                hidden_count += 1
                continue
        public_entities.append(
            {
                "kind": "person",
                "personId": pid,
                "alias": _anon_name(k),
                "code": _planet_code(pid),
            }
        )
    return JSONResponse(
        {
            "room": room,
            "count": hub.presence_count(room),
            "users": [
                _anon_name(k)
                for k in keys
                if (
                    (_public_person_id(k) == viewer_pid)
                    or (vmap.get(_public_person_id(k), "public") == "public")
                    or (vmap.get(_public_person_id(k), "public") == "venue_verified" and viewer_ok)
                )
            ][:18],
            "entities": public_entities,
            "hiddenCount": int(hidden_count),
            "venueLabel": label,
        }
    )


async def api_now_ping(request: Request) -> Response:
    venue_id = str(request.query_params.get("venueId") or "").strip()
    if not venue_id:
        raise HTTPException(status_code=400, detail="venueId_required")
    room = f"venue:{venue_id}"
    uk = getattr(request.state, "user_key", None) or request.cookies.get("abang_uid") or "anon"
    if await _presence_mode(str(uk)) == "offline":
        return JSONResponse({"ok": True, "online": False})
    hub.ping(room, str(uk))
    return JSONResponse({"ok": True, "online": True})


async def api_now_ask(request: Request) -> Response:
    ip = request.client.host if request.client else "unknown"
    if not _allow("now_ask", ip, limit=80, window_s=3600):
        raise HTTPException(status_code=429, detail="rate_limited")
    payload: dict[str, Any] = {}
    if request.method == "GET":
        payload = dict(request.query_params)
    else:
        try:
            payload = await request.json()
        except Exception:
            try:
                raw = (await request.body()) or b""
                txt = raw.decode("utf-8", errors="ignore").strip()
                if txt.startswith("{") and txt.endswith("}"):
                    payload = json.loads(txt)
                else:
                    from urllib.parse import parse_qs

                    q = parse_qs(txt, keep_blank_values=True)
                    payload = {k: (v[-1] if isinstance(v, list) and v else v) for k, v in q.items()}
            except Exception:
                raise HTTPException(status_code=400, detail="invalid_json")
    venue_id = str(payload.get("venueId") or "").strip()
    kind = str(payload.get("kind") or "").strip().lower()
    if not venue_id:
        raise HTTPException(status_code=400, detail="venueId_required")
    if kind not in ("people", "live"):
        raise HTTPException(status_code=400, detail="invalid_kind")

    room = f"venue:{venue_id}"
    online = hub.presence_count(room)
    recent_events = hub.recent_events(room, limit=10)

    async with session_scope(SessionLocal) as s:
        res = await s.execute(
            select(Post)
            .where(Post.venue_id == venue_id)
            .order_by(Post.created_at.desc())
            .limit(20)
        )
        posts = res.scalars().all()

    def _bucket(tags: str) -> str:
        ts = (tags or "").lower()
        if "petcare" in ts:
            return "BBEats"
        if "companion" in ts:
            return "ForYou"
        if "coffee" in ts:
            return "Coffee Chat"
        if "lost" in ts or "found" in ts:
            return "失物招领"
        if "eat" in ts:
            return "吃饭邀约"
        return "Post"

    buckets: dict[str, int] = {}
    for p in posts:
        b = _bucket(p.tags or "")
        buckets[b] = buckets.get(b, 0) + 1
    top = sorted(buckets.items(), key=lambda x: x[1], reverse=True)[:4]

    if kind == "people":
        lines: list[str] = []
        lines.append(f"附近在线：{online} 人")
        if top:
            lines.append("可能在做：")
            for name, n in top:
                lines.append(f"- {name} ×{n}")
        if recent_events:
            lines.append("刚刚发生：")
            for ev in recent_events[:3]:
                lines.append(f"- {ev.get('text','')}")
        answer = "\n".join(lines)
        return JSONResponse({"answer": answer})

    # kind == "live"
    lines: list[str] = []
    if recent_events:
        lines.append("这里的 live：")
        for ev in recent_events[:6]:
            lines.append(f"- {ev.get('text','')}")
    else:
        lines.append("这里暂时没有明显 live 事件。")
    if top:
        lines.append("")
        lines.append("热点：")
        for name, n in top:
            lines.append(f"- {name} ×{n}")
    answer = "\n".join(lines)
    return JSONResponse({"answer": answer})


async def api_posts(request: Request) -> Response:
    venue_id = request.query_params.get("venueId")
    if not venue_id:
        raise HTTPException(status_code=400, detail="venueId_required")
    ptype = request.query_params.get("type")
    types = {ptype} if ptype else None
    return JSONResponse(await _get_posts(venue_id, types))


async def api_post_create(request: Request) -> Response:
    payload = await request.json()
    ptype = str(payload.get("type") or "")
    if ptype not in ("invite", "lost", "found"):
        raise HTTPException(status_code=400, detail="invalid_type")
    title = str(payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title_required")
    body = str(payload.get("body") or "")
    venue_id = str(payload.get("venueId") or "")
    if not venue_id:
        raise HTTPException(status_code=400, detail="venueId_required")
    try:
        start_at = datetime.fromisoformat(str(payload.get("startAt")))
        end_at = datetime.fromisoformat(str(payload.get("endAt")))
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_time")
    tags_in = payload.get("tags") or []
    tags_list = [str(x) for x in tags_in] if isinstance(tags_in, list) else []

    ok, reason = moderate_text(f"{title}\n{body}")
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    tags = tags_list or suggest_tags(title, body)
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(Post.id).order_by(Post.id.desc()).limit(1))
        last = res.first()
        next_num = 1
        if last and isinstance(last[0], str) and last[0].startswith("p"):
            try:
                next_num = int(last[0][1:]) + 1
            except Exception:
                next_num = 1
        post_id = f"p{next_num}"
        p = Post(
            id=post_id,
            type=ptype,
            scope=str(payload.get("scope") or "keep").strip().lower() if str(payload.get("scope") or "").strip().lower() in ("now","keep") else "keep",
            title=title,
            body=body,
            venue_id=venue_id,
            start_at=start_at,
            end_at=end_at,
            tags=",".join(tags),
            created_at=_now(),
        )
        s.add(p)
    posts = await _get_posts(venue_id, {ptype})
    created = next((x for x in posts if x["id"] == post_id), None)
    if not created:
        raise HTTPException(status_code=500, detail="create_failed")
    return JSONResponse(created)


async def api_post_get(request: Request) -> Response:
    post_id = request.path_params["postId"]
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(Post).where(Post.id == post_id))
        p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="not_found")
    return JSONResponse(
        {
        "id": p.id,
        "type": p.type,
        "scope": getattr(p, "scope", "keep"),
        "title": p.title,
        "body": p.body,
        "venueId": p.venue_id,
        "startAt": p.start_at.isoformat(),
        "endAt": p.end_at.isoformat(),
        "tags": [t for t in (p.tags or "").split(",") if t],
        }
    )


async def api_checkout_mock(request: Request) -> Response:
    """
    一个可运行的“模拟收款”端点，用来把订单状态机跑通。
    接真实 PSP 时，这里会替换为创建 Checkout/PaymentIntent。
    """
    payload = await request.json()
    kind = str(payload.get("kind") or "")
    if kind not in ("market", "support"):
        raise HTTPException(status_code=400, detail="invalid_kind")
    try:
        amount = int(payload.get("amount"))
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_amount")
    if amount < 1:
        raise HTTPException(status_code=400, detail="invalid_amount")
    currency = str(payload.get("currency") or "HKD").upper()
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(Order.id).order_by(Order.id.desc()).limit(1))
        last = res.first()
        next_num = 1
        if last and isinstance(last[0], str) and last[0].startswith("o"):
            try:
                next_num = int(last[0][1:]) + 1
            except Exception:
                next_num = 1
        order_id = f"o{next_num}"
        now = _now()
        fee = int(amount * 0.06)  # 默认6%示例
        s.add(
            Order(
                id=order_id,
                kind=kind,
                status="paid",
                currency=currency,
                amount=amount,
                platform_fee=fee,
                ps_provider="mock",
                ps_ref=f"mock_{order_id}",
                created_at=now,
            )
        )
    return JSONResponse({"orderId": order_id, "status": "paid", "platformFee": fee})


async def api_lost_suggestions(request: Request) -> Response:
    """
    首版相似匹配：同venue内对比 title+body 的 Jaccard 相似度。
    后续可替换成 pgvector / embedding 检索。
    """
    venue_id = request.query_params.get("venueId")
    post_id = request.query_params.get("postId")
    if not venue_id or not post_id:
        raise HTTPException(status_code=400, detail="venueId_and_postId_required")
    async with session_scope(SessionLocal) as s:
        res = await s.execute(select(Post).where(Post.id == post_id))
        p = res.scalar_one_or_none()
    if not p or p.venue_id != venue_id:
        raise HTTPException(status_code=404, detail="not_found")
    t = {
        "id": p.id,
        "type": p.type,
        "title": p.title,
        "body": p.body,
        "venueId": p.venue_id,
        "startAt": p.start_at.isoformat(),
        "endAt": p.end_at.isoformat(),
        "tags": [t for t in (p.tags or "").split(",") if t],
    }
    candidates = await _get_posts(venue_id, {"lost", "found"})
    scored: list[tuple[float, dict[str, Any]]] = []
    t_text = f'{t["title"]} {t["body"]}'
    for c in candidates:
        if c["id"] == post_id:
            continue
        c_text = f'{c["title"]} {c["body"]}'
        score = jaccard(t_text, c_text)
        if score >= 0.10:
            scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return JSONResponse([{"score": round(s, 3), **c} for s, c in scored[:10]])


class ChatEndpoint(WebSocketEndpoint):
    encoding = "text"

    async def on_connect(self, websocket: WebSocket) -> None:
        self.room = websocket.query_params.get("room") or "venue:v_hk_001"
        uk = websocket.cookies.get("abang_uid") or "anon"
        await hub.join(self.room, websocket, uk)
        await hub.broadcast(self.room, {"type": "system", "text": "有人加入了房间", "ts": _now().isoformat()})

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        hub.leave(self.room, websocket)
        await hub.broadcast(self.room, {"type": "system", "text": "有人离开了房间", "ts": _now().isoformat()})

    async def on_receive(self, websocket: WebSocket, data: str) -> None:
        if not _allow("ws_msg", str(id(websocket)), limit=8, window_s=10):
            await websocket.send_json({"type": "system", "text": "发送过快，请稍后再试", "ts": _now().isoformat()})
            return
        if any(k in data.lower() for k in ["验证码", "cvv", "私钥", "seed", "mnemonic", "usdt", "btc", "eth"]):
            await websocket.send_json({"type": "system", "text": "内容可能涉及敏感信息，已拦截", "ts": _now().isoformat()})
            return
        await hub.broadcast(self.room, {"type": "msg", "text": data, "ts": _now().isoformat()})


routes = [
    Route("/docs", docs_index, methods=["GET"]),
    Route("/docs/{docPath:path}", docs_view, methods=["GET"]),
    Route("/", home, methods=["GET"]),
    Route("/post", hub_post, methods=["GET"]),
    Route("/coffeechat", hub_coffeechat, methods=["GET"]),
    Route("/public", hub_public, methods=["GET"]),
    Route("/help", hub_help, methods=["GET"]),
    Route("/robot4s", robot4s, methods=["GET"]),
    Route("/support-sell", support_sell, methods=["GET"]),
    Route("/support", support_page, methods=["GET"]),
    Route("/support/new", support_new, methods=["GET"]),
    Route("/support/new", support_new_post, methods=["POST"]),
    Route("/support/project", support_project, methods=["GET"]),
    Route("/support/story", support_story, methods=["GET"]),
    Route("/support/crowd", support_crowd, methods=["GET"]),
    Route("/support/{sid:str}", support_detail, methods=["GET"]),
    Route("/sell", sell_page, methods=["GET"]),
    Route("/sell/new", sell_new, methods=["GET"]),
    Route("/sell/new", sell_new_post, methods=["POST"]),
    Route("/sell/arts", sell_arts, methods=["GET"]),
    Route("/sell/product", sell_product, methods=["GET"]),
    Route("/sell/vintage", sell_vintage, methods=["GET"]),
    Route("/sell/{iid:str}", sell_detail, methods=["GET"]),
    Route("/map", map_page, methods=["GET"]),
    Route("/invite/new", invite_new, methods=["GET", "POST"]),
    Route("/ask/{token:str}", ask_view, methods=["GET"]),
    Route("/ask/{token:str}", ask_reply, methods=["POST"]),
    Route("/invite/{token:str}", invite_view, methods=["GET"]),
    Route("/invite/{token:str}/accept", invite_accept, methods=["POST"]),
    Route("/invite/{token:str}/decline", invite_decline, methods=["POST"]),
    Route("/invite/{token:str}/complain", invite_complain, methods=["POST"]),
    Route("/universe", universe_page, methods=["GET"]),
    Route("/universe/wm", universe_wm_page, methods=["GET"]),
    Route("/wm/reset", wm_reset_page, methods=["GET"]),
    Route("/interact", interact, methods=["GET"]),
    Route("/interact/live", interact_live, methods=["GET"]),
    Route("/live", interact_live, methods=["GET"]),
    Route("/interact/region", interact_region, methods=["GET"]),
    Route("/interact/new", interact_new, methods=["GET"]),
    Route("/interact/new", interact_new_post, methods=["POST"]),
    Route("/coffee", coffee, methods=["GET"]),
    Route("/coffee/new", coffee_new, methods=["GET"]),
    Route("/coffee/new", coffee_new_post, methods=["POST"]),
    Route("/lost", lost, methods=["GET"]),
    Route("/lost/new", lost_new, methods=["GET"]),
    Route("/lost/new", lost_new_post, methods=["POST"]),
    Route("/pets", pets, methods=["GET"]),
    Route("/pets/new", pets_new, methods=["GET"]),
    Route("/pets/new", pets_new_post, methods=["POST"]),
    Route("/companion", companion, methods=["GET"]),
    Route("/companion/new", companion_new, methods=["GET"]),
    Route("/companion/new", companion_new_post, methods=["POST"]),
    Route("/market", market, methods=["GET"]),
    Route("/charity", charity, methods=["GET"]),
    Route("/news", charity, methods=["GET"]),
    Route("/27hours", hours27, methods=["GET"]),
    Route("/plan", plan_page, methods=["GET"]),
    Route("/reward", reward_page, methods=["GET"]),
    Route("/realname", realname, methods=["GET"]),
    Route("/realname", realname_post, methods=["POST"]),
    Route("/emergency", emergency_list, methods=["GET"]),
    Route("/emergency/new", emergency_new, methods=["GET"]),
    Route("/emergency/new", emergency_new_post, methods=["POST"]),
    Route("/emergency/{caseId:str}", emergency_case, methods=["GET"]),
    Route("/emergency/{caseId:str}/update", emergency_update_post, methods=["POST"]),
    Route("/emergency/{caseId:str}/export", emergency_export, methods=["GET"]),
    Route("/safety", safety, methods=["GET"]),
    Route("/safety/report", safety_report, methods=["GET"]),
    Route("/safety/report", safety_report_post, methods=["POST"]),
    Route("/safety/opinion", safety_opinion_post, methods=["POST"]),
    Route("/safety/vote", safety_opinion_vote_post, methods=["POST"]),
    Route("/safety/bulletins", safety_bulletins, methods=["GET"]),
    Route("/safety/plus", safety_plus, methods=["GET"]),
    Route("/legal", legal, methods=["GET"]),
    Route("/legal/probono", legal_probono, methods=["GET"]),
    Route("/legal/ticket/new", legal_ticket_new, methods=["GET"]),
    Route("/legal/ticket/new", legal_ticket_new_post, methods=["POST"]),
    Route("/projects", projects, methods=["GET"]),
    Route("/tips", tip_create, methods=["POST"]),
    Route("/messages", messages, methods=["GET"]),
    Route("/profile", profile, methods=["GET"]),
    Route("/profile/privacy", profile_privacy_post, methods=["POST"]),
    Route("/profile/presence", presence_set_post, methods=["POST"]),
    Route("/identity", identity_post, methods=["POST"]),
    Route("/auth", auth, methods=["GET"]),
    Route("/card/{personId:str}", card_view, methods=["GET"]),
    Route("/card/{personId:str}/new", card_entry_new, methods=["POST"]),
    Route("/api/venues", api_venues, methods=["GET"]),
    Route("/api/venues/geo", api_venues_geo, methods=["GET"]),
    Route("/api/universe", api_universe, methods=["GET"]),
    Route("/api/venues/nearest", api_venues_nearest, methods=["GET"]),
    Route("/api/now/presence", api_now_presence, methods=["GET"]),
    Route("/api/now/ping", api_now_ping, methods=["GET"]),
    Route("/api/billboard/refresh", api_billboard_refresh, methods=["POST"]),
    Route("/api/prefs", api_prefs_set, methods=["POST"]),
    Route("/api/public/hints", api_public_hints, methods=["GET"]),
    Route("/api/plan", api_plan_get, methods=["GET"]),
    Route("/api/plan", api_plan_save, methods=["POST"]),
    Route("/api/reward/suggest", api_reward_suggest, methods=["GET"]),
    Route("/api/reward/log", api_reward_log, methods=["POST"]),
    Route("/api/posts", api_posts, methods=["GET"]),
    Route("/api/posts", api_post_create, methods=["POST"]),
    Route("/api/posts/{postId:str}", api_post_get, methods=["GET"]),
    Route("/api/now/ask", api_now_ask, methods=["GET", "POST"]),
    Route("/api/challenge", api_challenge, methods=["GET"]),
    Route("/api/invite/live", api_invite_live_create, methods=["POST"]),
    Route("/api/game/bailan", api_game_bailan, methods=["POST"]),
    Route("/api/lost/suggestions", api_lost_suggestions, methods=["GET"]),
    Route("/api/checkout/mock", api_checkout_mock, methods=["POST"]),
    WebSocketRoute("/ws/chat", ChatEndpoint),
]


app = Starlette(debug=True, routes=routes, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
# Embedded World Monitor static build (aabapp/dist) served under /wm/.
_wm_dist = Path(__file__).resolve().parents[2] / "aabapp" / "dist"
if (_wm_dist / "index.html").exists():
    app.mount("/wm", StaticFiles(directory=str(_wm_dist), html=True), name="wm")
app.add_middleware(ModeMiddleware)
app.add_middleware(UserKeyMiddleware)

