"""Unit tests for mail token signing and body instrumentation."""

from __future__ import annotations

from platform_api.services.mail import tracking

SECRET = "test-tracking-secret"
SEND_ID = "3f1c9d7e-0000-4000-8000-abcdefabcdef"
USER_ID = "9a8b7c6d-1111-4222-8333-444455556666"


def test_open_token_round_trip() -> None:
    token = tracking.build_open_token(SECRET, SEND_ID)
    assert tracking.parse_open_token(SECRET, token) == SEND_ID


def test_wrong_secret_is_rejected() -> None:
    token = tracking.build_open_token("other-secret", SEND_ID)
    assert tracking.unpack(SECRET, token) is None
    assert tracking.parse_open_token(SECRET, token) is None


def test_tampered_payload_is_rejected() -> None:
    token = tracking.build_open_token(SECRET, SEND_ID)
    _, _, signature = token.rpartition(".")
    forged_body = tracking._b64url(f"o1.{USER_ID}".encode())
    assert tracking.unpack(SECRET, f"{forged_body}.{signature}") is None


def test_purpose_prefixes_stop_cross_use() -> None:
    unsub = tracking.build_unsub_token(SECRET, USER_ID)
    assert tracking.parse_open_token(SECRET, unsub) is None
    assert tracking.parse_click_token(SECRET, unsub) is None
    assert tracking.parse_unsub_token(SECRET, unsub) == USER_ID

    open_token = tracking.build_open_token(SECRET, SEND_ID)
    assert tracking.parse_unsub_token(SECRET, open_token) is None


def test_click_token_carries_signed_destination() -> None:
    url = "https://music.camxora.com/pricing?pack=20"
    token = tracking.build_click_token(SECRET, SEND_ID, url)
    parsed = tracking.parse_click_token(SECRET, token)
    assert parsed == (SEND_ID, url)

    # Swapping the destination invalidates the signature, so the redirect cannot
    # be turned into an open redirect.
    evil = tracking.build_click_token(SECRET, SEND_ID, "https://evil.example/steal")
    _, _, signature = evil.rpartition(".")
    forged_body = tracking._b64url(
        f"c1.{SEND_ID}.{tracking._b64url(b'https://evil.example')}".encode()
    )
    assert tracking.parse_click_token(SECRET, f"{forged_body}.{signature}") is None


def test_non_http_destinations_are_not_redirectable() -> None:
    assert tracking.is_safe_redirect("https://music.camxora.com")
    assert not tracking.is_safe_redirect("javascript:alert(1)")
    assert not tracking.is_safe_redirect("data:text/html,hi")
    assert not tracking.is_safe_redirect("/relative")
    assert not tracking.is_safe_redirect("not a url")


def test_instrument_html_wraps_real_links_only() -> None:
    html = (
        "<html><body>"
        '<a href="https://music.camxora.com/pricing">Pricing</a>'
        '<a href="mailto:hi@camxora.com">Mail us</a>'
        '<a href="#top">Top</a>'
        '<a href="{{app_url}}">Placeholder</a>'
        '<a href="javascript:alert(1)">Bad</a>'
        "</body></html>"
    )

    out, links = tracking.instrument_html(
        html,
        click_url=lambda target: f"https://track.test/c?u={target}",
        open_url="https://track.test/o.gif",
    )

    assert links == 1
    assert "https://track.test/c?u=" in out
    assert "mailto:hi@camxora.com" in out
    assert 'href="#top"' in out
    assert "{{app_url}}" in out
    assert "javascript:alert(1)" in out
    assert out.index("track.test/o.gif") < out.index("</body>")


def test_pixel_appended_without_body_tag() -> None:
    out, links = tracking.instrument_html(
        '<a href="https://music.camxora.com">Go</a>',
        click_url=lambda target: f"https://track.test/c?u={target}",
        open_url="https://track.test/o.gif",
    )
    assert links == 1
    assert out.endswith('src="https://track.test/o.gif" width="1" height="1" alt="" '
                        'style="display:block;width:1px;height:1px;border:0;outline:none;" />')


def test_render_vars_escapes_and_keeps_unknown() -> None:
    out = tracking.render_vars(
        "<p>{{name}} — {{credits}} — {{unknown}}</p>",
        {"name": "<script>x</script>", "credits": 2300},
    )
    assert out == "<p>&lt;script&gt;x&lt;/script&gt; — 2300 — {{unknown}}</p>"


def test_render_vars_without_escaping_for_text() -> None:
    assert tracking.render_vars("Hi {{name}}", {"name": "A & B"}, escape=False) == "Hi A & B"


def test_html_to_text_strips_markup() -> None:
    text = tracking.html_to_text(
        "<html><head><style>p{color:red}</style></head>"
        "<body><p>Hello</p><p>2,300 credits</p></body></html>"
    )
    assert text == "Hello\n2,300 credits"
