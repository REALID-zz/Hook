import re
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar


def _opener() -> urllib.request.OpenerDirector:
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def get(opener: urllib.request.OpenerDirector, url: str) -> tuple[int, str]:
    try:
        r = opener.open(url)
        return int(r.getcode() or 200), r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return int(e.code), e.read().decode("utf-8", "ignore")


def post_form(opener: urllib.request.OpenerDirector, url: str, data: dict[str, str]) -> int:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        r = opener.open(req)
        return int(r.getcode() or 200)
    except urllib.error.HTTPError as e:
        return int(e.code)


def main() -> None:
    base = "http://127.0.0.1:8000"

    op1 = _opener()
    c1, html = get(op1, f"{base}/profile")
    m = re.search(r"(p_[0-9a-f]{12})", html)
    if not m:
        raise SystemExit("no public person id found on /profile")
    pid = m.group(1)
    print("profile:", c1, "pid:", pid)

    c2 = post_form(op1, f"{base}/profile/privacy", {"privacy": "private"})
    print("set_private:", c2)

    op2 = _opener()
    c3, _ = get(op2, f"{base}/card/{pid}")
    print("other_session_card:", c3, "(expect 404)")

    # owner still can view
    c4, _ = get(op1, f"{base}/card/{pid}")
    print("owner_card:", c4, "(expect 200)")

    # restore public
    c5 = post_form(op1, f"{base}/profile/privacy", {"privacy": "public"})
    print("set_public:", c5)

    c6, _ = get(op2, f"{base}/card/{pid}")
    print("other_session_card_after_public:", c6, "(expect 200)")


if __name__ == "__main__":
    main()

