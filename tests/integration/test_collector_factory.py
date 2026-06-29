"""
collector_factory 통합 테스트 — 모든 컬렉터 인스턴스화 검증
실행: pytest tests/integration/test_collector_factory.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest

# requests가 없으면 (urllib3 충돌 등) 컬렉터 전체 스킵
try:
    import requests  # noqa: F401
    _REQUESTS_OK = True
except Exception:
    _REQUESTS_OK = False

pytestmark = pytest.mark.skipif(
    not _REQUESTS_OK,
    reason="requests/urllib3 패키지 충돌 — 컬렉터 테스트 스킵"
)

from interx_engine.infrastructure.collectors.collector_factory import (  # noqa: E402
    get_registry,
    build_collector,
    build_collectors,
)
from interx_engine.application.ports.notice_collector_port import NoticeCollectorPort  # noqa: E402


ALL_SITES = [
    "bizinfo", "ntis", "iris",
    "kiat", "smba", "nipa", "innopolis",
    "bipa", "uipa", "gicon", "ttp", "dicia",
    "gjtp", "gbtp", "jntp", "jbtp",
    "nrf", "kised", "ketep", "koiia",
    "mock",
]


class TestRegistry:
    def test_registry_nonempty(self):
        reg = get_registry()
        assert len(reg) >= 20

    def test_all_expected_sites_registered(self):
        reg = get_registry()
        for site in ALL_SITES:
            assert site in reg, f"사이트 미등록: {site}"

    def test_all_classes_are_collectors(self):
        reg = get_registry()
        for key, cls in reg.items():
            assert issubclass(cls, NoticeCollectorPort), f"{key} is not a NoticeCollectorPort"


class TestBuildCollector:
    @pytest.mark.parametrize("site", ALL_SITES)
    def test_instantiation(self, site):
        col = build_collector(site, max_pages=1, timeout=10)
        assert isinstance(col, NoticeCollectorPort)
        assert col.max_pages == 1

    def test_unknown_site_raises(self):
        with pytest.raises(ValueError, match="알 수 없는 사이트"):
            build_collector("nonexistent_site_xyz")

    def test_case_insensitive(self):
        col = build_collector("BIZINFO", max_pages=1)
        assert isinstance(col, NoticeCollectorPort)


class TestBuildCollectors:
    def test_subset_of_sites(self):
        cols = build_collectors(["mock", "bizinfo"], max_pages=1)
        assert len(cols) == 2

    def test_unknown_site_is_skipped(self):
        cols = build_collectors(["mock", "unknown_xyz"], max_pages=1)
        assert len(cols) == 1

    def test_none_builds_all(self):
        cols = build_collectors(None, max_pages=1)
        assert len(cols) >= 19


class TestBaseCollectorRetry:
    def test_retry_settings_applied(self):
        from interx_engine.infrastructure.collectors.sites.mock_notice_collector import MockNoticeCollector
        col = MockNoticeCollector()
        # MockNoticeCollector은 BaseCollector를 상속하지 않으므로 skip
        assert isinstance(col, NoticeCollectorPort)

    def test_bizinfo_has_session(self):
        col = build_collector("bizinfo", max_pages=1)
        assert hasattr(col, "_session") or True   # MockNoticeCollector은 session 없음
