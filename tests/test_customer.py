"""customer_service_access helpers — /e/<CODE> building + per-service view."""

from __future__ import annotations

from unitysvc_mcp.customer_context import CustomerContext, EnrollmentInfo
from unitysvc_mcp.tools.customer import _endpoint_url, _service_view


def _enr(service_id: str, code: str | None, proxy: str | None) -> EnrollmentInfo:
    return EnrollmentInfo(service_id=service_id, status="active", code=code, proxy_endpoint=proxy)


def test_endpoint_url_is_origin_plus_code() -> None:
    url = _endpoint_url(_enr("s1", "CODE1", "https://gw.test/a/foo?x=1"))
    assert url == "https://gw.test/e/CODE1"


def test_endpoint_url_is_none_when_incomplete() -> None:
    assert _endpoint_url(_enr("s1", None, "https://gw.test/x")) is None
    assert _endpoint_url(_enr("s1", "C", None)) is None
    assert _endpoint_url(_enr("s1", "C", "not-a-url")) is None


def test_service_view_filters_enrollments_to_this_service() -> None:
    context = CustomerContext(
        secret_names=frozenset({"A"}),
        enrollments=(
            _enr("s1", "C1", "https://gw.test/a/one"),
            _enr("s2", "C2", "https://gw.test/a/two"),
        ),
    )
    view = _service_view(context, "s1")

    assert view.set_secret_names == frozenset({"A"})  # account-wide
    assert view.enrollment_urls == ["https://gw.test/e/C1"]  # s2 excluded
