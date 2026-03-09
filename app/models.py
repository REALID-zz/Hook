from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

PostType = Literal["invite", "lost", "found"]


class Base(DeclarativeBase):
    pass


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False)


class VenueGeo(Base):
    """
    场所的“地理围栏”配置（独立表：避免改动既有 venues 表结构）。
    仅用于首版的“GPS 在场范围”校验与展示，不做持续定位追踪。
    """

    __tablename__ = "venue_geo"

    venue_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    radius_m: Mapped[int] = mapped_column(nullable=False, default=200)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # invite|lost|found
    scope: Mapped[str] = mapped_column(String(12), nullable=False, default="keep")  # now|keep
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    venue_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    tags: Mapped[str] = mapped_column(String(400), nullable=False, default="")  # comma-separated
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class InviteProof(Base):
    """
    “现场拍照 + 定位”证明（用于 invite 类帖子）。
    注意：这是“抬高作弊成本”的 MVP 信号，不等同于强身份认证。
    """

    __tablename__ = "invite_proofs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # ip1...
    post_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    venue_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    address_label: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    photo_path: Mapped[str] = mapped_column(String(240), nullable=False, default="")  # relative to /static
    lat: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    lng: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    accuracy_m: Mapped[int] = mapped_column(nullable=False, default=0)
    venue_distance_m: Mapped[int] = mapped_column(nullable=False, default=-1)
    verification: Mapped[str] = mapped_column(String(24), nullable=False, default="gps_only")  # gps_only|geofence
    challenge_nonce: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # market|support
    status: Mapped[str] = mapped_column(String(24), nullable=False)  # created|paid|...
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="HKD")
    amount: Mapped[int] = mapped_column(nullable=False, default=0)  # minor units
    platform_fee: Mapped[int] = mapped_column(nullable=False, default=0)  # minor units
    ps_provider: Mapped[str] = mapped_column(String(24), nullable=False, default="mock")
    ps_ref: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class SafetyReport(Base):
    """
    安全举报/事件记录（首版：不做“点名曝光”，只做去标识化的已核实通报）。
    """

    __tablename__ = "safety_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # r1, r2...
    venue_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_key: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)  # 提交人（平台追责）
    category: Mapped[str] = mapped_column(String(32), nullable=False)  # scam|harassment|safety|privacy|other
    summary: Mapped[str] = mapped_column(String(240), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="received")  # received|reviewing|actioned|dismissed
    is_public: Mapped[int] = mapped_column(nullable=False, default=0)  # 0/1
    public_note: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    evidence_path: Mapped[str] = mapped_column(String(240), nullable=False, default="")  # uploads/...
    publish_request: Mapped[int] = mapped_column(nullable=False, default=0)  # 0/1：申请公开
    author_display: Mapped[str] = mapped_column(String(12), nullable=False, default="anon")  # anon|signed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class SafetyOpinion(Base):
    """
    民众反馈互动板：两类内容
    - pro: 需上传律师/专业资质凭证（先记为 pending，后续可做人工/机构核验）
    - public: 普通人观点/看法

    注意：不做点名曝光，不收集不必要的敏感信息。
    """

    __tablename__ = "safety_opinions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # so1, so2...
    venue_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_key: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    kind: Mapped[str] = mapped_column(String(12), nullable=False, default="public")  # pro|public
    title: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    credential_path: Mapped[str] = mapped_column(String(240), nullable=False, default="")  # uploads/...
    credential_status: Mapped[str] = mapped_column(String(16), nullable=False, default="none")  # none|pending|verified|rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class SafetyOpinionVote(Base):
    """
    道德评分（民意调查式）：每个 opinion 每个用户 1 票，可覆盖更新。
    score: 0..100
    """

    __tablename__ = "safety_opinion_votes"
    __table_args__ = (UniqueConstraint("opinion_id", "user_key", name="uq_opinion_user"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    opinion_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_key: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    score: Mapped[int] = mapped_column(nullable=False, default=50)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class MeetInvite(Base):
    """
    线下“搭讪式邀请”：
    - 邀请者必须完成平台实名留档（可追责）
    - 每日限 1 次（后端路由里执行）
    - 邀请通过一次性 token + 有效期
    - 只有对方扫码并同意才进入聊天
    """

    __tablename__ = "meet_invites"

    token: Mapped[str] = mapped_column(String(96), primary_key=True)  # urlsafe token
    venue_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    inviter_key: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    invitee_key: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    room: Mapped[str] = mapped_column(String(96), nullable=False, default="")  # meet:<token>
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")  # open|accepted|declined|complained|expired
    note: Mapped[str] = mapped_column(String(160), nullable=False, default="")  # optional opening line
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class MeetInviteComplaint(Base):
    """
    邀请被投诉：用于限制邀请者后续邀请能力（例如 7 天内禁止再次邀请）。
    """

    __tablename__ = "meet_invite_complaints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    inviter_key: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    reason: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class NextQuestion(Base):
    """
    只问问题（不进入实时互动）：不强制实名。
    通过一次性 token 分享，过期后不可提交。
    """

    __tablename__ = "next_questions"

    token: Mapped[str] = mapped_column(String(96), primary_key=True)
    venue_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    asker_key: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    question: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class NextQuestionReply(Base):
    __tablename__ = "next_question_replies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    user_key: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    choice: Mapped[str] = mapped_column(String(16), nullable=False, default="maybe")  # yes|no|maybe
    message: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class RealNameRecord(Base):
    """
    平台实名留档（不自动公示）。
    目标：平台可追责；是否对外展示由 PersonIdentity.name_public 控制。
    """

    __tablename__ = "realname_records"

    user_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    contact: Mapped[str] = mapped_column(String(120), nullable=False, default="")  # 手机/邮箱其一
    id_last4: Mapped[str] = mapped_column(String(8), nullable=False, default="")  # 仅保存后4位
    statement_ok: Mapped[int] = mapped_column(nullable=False, default=0)  # 0/1：对陈述事实负责
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class PlanNote(Base):
    """
    计划本（记事本式自由编辑），按 user_key 保存。
    """

    __tablename__ = "plan_notes"

    user_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class RewardNote(Base):
    """
    报酬通道（给与/索取）记录：只做建议与留档，不直接处理支付。
    """

    __tablename__ = "reward_notes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # rw20260226_ab12cd
    user_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(12), nullable=False, default="global", index=True)
    venue_id: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    direction: Mapped[str] = mapped_column(String(8), nullable=False, default="give")  # give|ask
    scenario: Mapped[str] = mapped_column(Text, nullable=False, default="")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="HKD")
    suggested: Mapped[int] = mapped_column(nullable=False, default=0)  # integer amount (major unit)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class LegalTicket(Base):
    """
    公益法律咨询/律师介入工单（首版：以“工单+分发”跑通流程，不直接提供法律意见）。
    """

    __tablename__ = "legal_tickets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # l1, l2...
    venue_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)  # pro_bono|paid|referral
    topic: Mapped[str] = mapped_column(String(48), nullable=False)  # defamation|harassment|contract|consumer|other
    summary: Mapped[str] = mapped_column(String(240), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="received")  # received|queued|assigned|closed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class Creator(Base):
    __tablename__ = "creators"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # c1, c2...
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    story: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recognition: Mapped[str] = mapped_column(String(24), nullable=False, default="none")  # none|candidate|verified
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class Work(Base):
    __tablename__ = "works"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # w1...
    creator_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_hint: Mapped[str] = mapped_column(String(120), nullable=False, default="")  # placeholder
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class Tip(Base):
    __tablename__ = "tips"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # t1...
    creator_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(nullable=False, default=0)  # minor units
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="HKD")
    message: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class UserCard(Base):
    __tablename__ = "user_cards"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # uc1...
    user_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # thanks|badge|work
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    rarity: Mapped[str] = mapped_column(String(16), nullable=False, default="common")  # common|rare|epic
    meta: Mapped[str] = mapped_column(Text, nullable=False, default="")  # json-ish string
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class CardEntry(Base):
    """
    公信力名片：他人关于某个“名片ID”的记录/评价/事实补充。
    - display: anon|signed 仅影响前端展示；author_key 始终保存用于追责/申诉。
    """

    __tablename__ = "card_entries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # ce1...
    person_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    author_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display: Mapped[str] = mapped_column(String(12), nullable=False, default="anon")  # anon|signed
    author_label: Mapped[str] = mapped_column(String(80), nullable=False, default="")  # display name if signed
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")  # active|hidden|disputed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class PersonPrivacy(Base):
    """
    公开名片的可见性设置（对外展示）。
    - 默认：公开（不写入记录也视作公开）
    - 关闭公开后：他人不可查看名片内容，也不可投稿；本人仍可查看。
    """

    __tablename__ = "person_privacy"

    person_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    is_public: Mapped[int] = mapped_column(nullable=False, default=1)  # 0/1
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="public")  # public|private|venue_verified
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class PersonIdentity(Base):
    """
    个人名片的“身份信息（软）”：
    - display_name / title：名片两行展示
    - name_public：是否对外公示（后续可扩展更细粒度）
    - verified：身份验证占位（none|pending|verified）
    """

    __tablename__ = "person_identity"

    person_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    name_public: Mapped[int] = mapped_column(nullable=False, default=0)  # 0/1
    verified: Mapped[str] = mapped_column(String(16), nullable=False, default="none")  # none|pending|verified
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class BillboardItem(Base):
    """
    官方消息 Billboard（广告牌）条目：
    - title/source/url：用于“直接引用/跳转”
    - quote：引用的摘要（来自源的 description/summary，截断）
    - ai_note：可选 AI 注释（1 行）
    - mode：global/cn/hk
    - day：YYYY-MM-DD（按天聚合展示）
    """

    __tablename__ = "billboard_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # bb20260225_1 ...
    mode: Mapped[str] = mapped_column(String(12), nullable=False, default="global", index=True)
    day: Mapped[str] = mapped_column(String(16), nullable=False, default="", index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    url: Mapped[str] = mapped_column(String(600), nullable=False, default="")
    quote: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ai_note: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class UserPreference(Base):
    """
    用户偏好（用于公共提示/推荐，不涉及敏感信息）。
    用 user_key（cookie abang_uid）作为主键。
    """

    __tablename__ = "user_preferences"

    user_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    prefs: Mapped[str] = mapped_column(String(240), nullable=False, default="")  # comma-separated
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class PresenceSetting(Base):
    """
    在线状态（presence）设置：
    - online: 允许出现在“附近在线”
    - offline: 不参与在线统计（不出现，也不计数）
    """

    __tablename__ = "presence_settings"

    user_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="online")  # online|offline
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class EmergencyCase(Base):
    """
    紧急事件（例如：周边小朋友/老人失踪求助）。
    目标：让周围人快速提交“现场照片+讯息”，形成可追溯记录，便于对接官方处理。
    """

    __tablename__ = "emergency_cases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # ec20260226_ab12cd
    venue_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False, default="missing")  # missing_child|missing_elder|missing
    reason: Mapped[str] = mapped_column(String(16), nullable=False, default="witness")  # witness|self|proxy|online_lead
    risk_level: Mapped[str] = mapped_column(String(12), nullable=False, default="medium")  # low|medium|high
    title: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")  # open|closed
    # ISO datetime string (avoid SQLite legacy empty-string parsing issues)
    start_at: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    end_at: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class EmergencyUpdate(Base):
    """
    紧急事件的现场线索提交（任何周边人可提交）。
    """

    __tablename__ = "emergency_updates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # eu20260226_ab12cd
    case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    photo_path: Mapped[str] = mapped_column(String(240), nullable=False, default="")  # uploads/...
    photo_sha256: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class SupportListing(Base):
    """
    Support：把作品放上来，写清楚缘由与需要的帮助。
    - contact 允许填写公开联系方式（用户自行决定是否公开）
    """

    __tablename__ = "support_listings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # sp1...
    user_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    venue_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    story: Mapped[str] = mapped_column(Text, nullable=False, default="")
    need_help: Mapped[str] = mapped_column(Text, nullable=False, default="")
    contact: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    contact_public: Mapped[int] = mapped_column(nullable=False, default=0)  # 0/1
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")  # active|hidden
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class SellListing(Base):
    """
    Sell：像“闲鱼”一样卖自己的东西。
    """

    __tablename__ = "sell_listings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # si1...
    user_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    venue_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price: Mapped[int] = mapped_column(nullable=False, default=0)  # integer amount
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    contact: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    contact_public: Mapped[int] = mapped_column(nullable=False, default=0)  # 0/1
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")  # active|sold|hidden
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

