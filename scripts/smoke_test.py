from __future__ import annotations

import sys
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar


BASE = "http://127.0.0.1:8000"


class Client:
    def __init__(self) -> None:
        self.cj = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def get(self, path: str) -> tuple[int, str]:
        url = BASE + path
        req = urllib.request.Request(url, method="GET")
        with self.opener.open(req, timeout=10) as r:
            return int(r.status), r.read().decode("utf-8", "ignore")

    def post_form(self, path: str, data: dict[str, str]) -> tuple[int, str | None]:
        url = BASE + path
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with self.opener.open(req, timeout=10) as r:
            return int(r.status), r.getheader("Location")


def main() -> int:
    c = Client()

    paths = [
        "/",
        "/interact",
        "/coffee",
        "/lost",
        "/projects",
        "/charity",
        "/safety",
        "/legal",
        "/messages",
        "/profile",
    ]
    modes = ["global", "cn", "hk"]

    print("== GET pages ==")
    for m in modes:
        for p in paths:
            status, _ = c.get(f"{p}?mode={m}")
            print(m, p, status)

    print("\n== POST invite ==")
    status, _ = c.get("/interact/new?mode=global")
    if status != 200:
        raise RuntimeError("interact_new not 200")
    status, loc = c.post_form("/interact/new", {"venueId": "v_cn_001", "title": "测试邀约", "body": "自动化测试"})
    print("invite", status, "loc", loc)

    print("\n== POST lost ==")
    status, _ = c.get("/lost/new?type=lost&mode=global")
    if status != 200:
        raise RuntimeError("lost_new not 200")
    status, loc = c.post_form(
        "/lost/new",
        {"venueId": "v_cn_001", "type": "lost", "title": "测试失物", "body": "自动化测试：手机"},
    )
    print("lost", status, "loc", loc)

    print("\n== CN tip -> profile card ==")
    status, _ = c.get("/projects?mode=cn")  # sets cookie abang_mode=cn
    if status != 200:
        raise RuntimeError("projects cn not 200")
    status, loc = c.post_form(
        "/tips",
        {"creatorId": "c1", "amount": "20", "currency": "CNY", "paymentMethod": "wxpay", "message": "加油"},
    )
    print("tip", status, "loc", loc)
    status, prof = c.get("/profile?mode=cn")
    print("profile", status, "has_card", ("感谢卡" in prof))

    print("\n== Safety report ==")
    status, _ = c.get("/safety/report?mode=global")
    if status != 200:
        raise RuntimeError("safety report page not 200")
    status, loc = c.post_form(
        "/safety/report",
        {"venueId": "v_cn_001", "category": "scam", "summary": "测试举报", "details": "自动化测试"},
    )
    print("report", status, "loc", loc)

    print("\n== Legal ticket ==")
    status, _ = c.get("/legal/ticket/new?mode=global")
    if status != 200:
        raise RuntimeError("legal ticket page not 200")
    status, loc = c.post_form(
        "/legal/ticket/new",
        {"venueId": "v_cn_001", "kind": "pro_bono", "topic": "consumer", "summary": "测试工单", "details": "自动化测试"},
    )
    print("legal", status, "loc", loc)

    print("\nALL_OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print("FAILED:", repr(e), file=sys.stderr)
        raise

