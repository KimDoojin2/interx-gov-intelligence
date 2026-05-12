"""
compat shim — 개별 파일로 분리된 컬렉터들의 하위호환 re-export.
새 코드는 각 사이트별 파일을 직접 import할 것.
"""
from interx_engine.infrastructure.collectors.sites.base_collector import (
    BaseCollector,
    PlaywrightBaseCollector,
    _extract_dates,
    _notice_id,
    _USER_AGENTS,
    _DATE_RE,
)
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

COLLECTOR_CLASSES: dict = {
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
}
