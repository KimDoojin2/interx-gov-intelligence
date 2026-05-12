from __future__ import annotations

import logging
import pathlib
from typing import Dict, Type

import yaml

from interx_engine.application.ports.notice_collector_port import NoticeCollectorPort

log = logging.getLogger("interx.collectors")

# configs/sites.yaml 에서 enabled: true 인 사이트 코드만 반환
def _enabled_site_keys() -> set[str]:
    """sites.yaml 을 읽어 enabled: true 인 code 목록을 반환한다."""
    try:
        cfg_path = pathlib.Path(__file__).parents[4] / "configs" / "sites.yaml"
        with open(cfg_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return {
            s["code"]
            for s in data.get("sites", [])
            if s.get("enabled", True)
        }
    except Exception as e:
        log.warning("sites.yaml 로드 실패 — 모든 사이트 활성화: %s", e)
        return None  # None → 필터 없음


def _build_registry() -> Dict[str, Type[NoticeCollectorPort]]:
    from interx_engine.infrastructure.collectors.sites.bizinfo_collector   import BizinfoCollector
    from interx_engine.infrastructure.collectors.sites.ntis_collector      import NtisCollector
    from interx_engine.infrastructure.collectors.sites.iris_collector      import IrisCollector
    from interx_engine.infrastructure.collectors.sites.kiat_collector      import KiatCollector
    from interx_engine.infrastructure.collectors.sites.smba_collector      import SmbaCollector
    from interx_engine.infrastructure.collectors.sites.nipa_collector      import NipaCollector
    from interx_engine.infrastructure.collectors.sites.innopolis_collector import InnopolisCollector
    from interx_engine.infrastructure.collectors.sites.bipa_collector      import BipaCollector
    from interx_engine.infrastructure.collectors.sites.uipa_collector      import UipaCollector
    from interx_engine.infrastructure.collectors.sites.gicon_collector     import GiconCollector
    from interx_engine.infrastructure.collectors.sites.ttp_collector       import TtpCollector
    from interx_engine.infrastructure.collectors.sites.dicia_collector     import DiciaCollector
    from interx_engine.infrastructure.collectors.sites.gjtp_collector      import GjtpCollector
    from interx_engine.infrastructure.collectors.sites.gbtp_collector      import GbtpCollector
    from interx_engine.infrastructure.collectors.sites.jntp_collector      import JntpCollector
    from interx_engine.infrastructure.collectors.sites.jbtp_collector      import JbtpCollector
    from interx_engine.infrastructure.collectors.sites.new_collectors      import NEW_COLLECTOR_CLASSES
    from interx_engine.infrastructure.collectors.sites.mock_notice_collector import MockNoticeCollector

    return {
        "bizinfo":   BizinfoCollector,
        "ntis":      NtisCollector,
        "iris":      IrisCollector,
        "kiat":      KiatCollector,
        "smba":      SmbaCollector,
        "nipa":      NipaCollector,
        "innopolis": InnopolisCollector,
        "bipa":      BipaCollector,
        "uipa":      UipaCollector,
        "gicon":     GiconCollector,
        "ttp":       TtpCollector,
        "dicia":     DiciaCollector,
        "gjtp":      GjtpCollector,
        "gbtp":      GbtpCollector,
        "jntp":      JntpCollector,
        "jbtp":      JbtpCollector,
        "mock":      MockNoticeCollector,
        **NEW_COLLECTOR_CLASSES,
    }


_REGISTRY: Dict[str, Type[NoticeCollectorPort]] = {}


def get_registry() -> Dict[str, Type[NoticeCollectorPort]]:
    global _REGISTRY
    if not _REGISTRY:
        _REGISTRY = _build_registry()
    return _REGISTRY


def build_collector(source_site: str, max_pages: int = 5, timeout: int = 0) -> NoticeCollectorPort:
    registry = get_registry()
    key = (source_site or "bizinfo").lower()
    cls = registry.get(key)
    if cls is None:
        available = ", ".join(sorted(registry.keys()))
        raise ValueError(f"알 수 없는 사이트: '{key}'. 지원: {available}")

    if timeout == 0:
        try:
            from interx_engine.infrastructure.config.settings_loader import settings
            timeout = settings.collector_timeout_sec()
        except Exception:
            timeout = 20

    try:
        return cls(max_pages=max_pages, timeout=timeout)
    except TypeError:
        col = cls()
        col.max_pages = max_pages
        return col


def build_collectors(site_keys: list[str] | None, max_pages: int) -> list[NoticeCollectorPort]:
    registry = get_registry()

    # site_keys 가 명시되면 그대로 사용, 아니면 registry 전체 키 대상
    if site_keys:
        targets = site_keys
    else:
        # sites.yaml enabled 필터 적용
        enabled = _enabled_site_keys()
        if enabled is None:
            targets = list(registry.keys())
        else:
            skipped = [k for k in registry.keys() if k not in enabled]
            if skipped:
                log.info("sites.yaml enabled:false → 스킵: %s", ", ".join(sorted(skipped)))
            targets = [k for k in registry.keys() if k in enabled]

    collectors = []
    for key in targets:
        try:
            col = build_collector(key, max_pages=max_pages)
            collectors.append(col)
            log.info("콜렉터 등록: %s", key)
        except ValueError as e:
            log.warning("%s (스킵)", e)
    return collectors
