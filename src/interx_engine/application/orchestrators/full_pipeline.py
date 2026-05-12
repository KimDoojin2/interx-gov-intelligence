from __future__ import annotations
import json
import logging
import os
from dataclasses import asdict, fields
from datetime import datetime
from pathlib import Path
from typing import Optional

from interx_engine.application.orchestrators.daily_pipeline import DailyPipelineOrchestrator
from interx_engine.application.use_cases.recommend_notices import RecommendNoticesUseCase
from interx_engine.application.use_cases.match_partners import MatchPartnersUseCase
from interx_engine.application.use_cases.cluster_notices import ClusterNoticesUseCase
from interx_engine.application.use_cases.alert_notices import AlertNoticesUseCase
from interx_engine.infrastructure.matching.csv_partner_repository import CsvPartnerRepository
from interx_engine.infrastructure.clustering.embedding_clusterer import EmbeddingClusterer
from interx_engine.infrastructure.clustering.tfidf_clusterer import TfidfClusterer
from interx_engine.infrastructure.storage.csv_writer import CsvFallbackWriter


# ── JSON 아티팩트 저장 헬퍼 ───────────────────────────────────────────────────

def _to_jsonable(obj):
    """dataclass / list / dict → JSON 직렬화 가능 형태로 변환."""
    if hasattr(obj, "__dataclass_fields__"):
        return {f.name: _to_jsonable(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, list):
        return [_to_jsonable(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    return obj


def _save_json_artifact(base_dir: Path, filename: str, data: dict) -> None:
    out_dir = base_dir / "data" / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.debug("JSON 아티팩트 저장: %s", path)

log = logging.getLogger(__name__)


def _build_alert_gateway():
    """
    환경변수 기반으로 Telegram 또는 Slack 게이트웨이 자동 선택.
    둘 다 없으면 NullGateway (아무것도 안 함).
    """
    telegram_token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    slack_webhook    = os.getenv("SLACK_WEBHOOK_URL", "")

    if telegram_token and telegram_chat_id:
        from interx_engine.infrastructure.alert.telegram_gateway import TelegramAlertGateway
        log.info("알림: Telegram 사용")
        return TelegramAlertGateway(telegram_token, telegram_chat_id)
    if slack_webhook:
        from interx_engine.infrastructure.alert.slack_gateway import SlackAlertGateway
        log.info("알림: Slack 사용")
        return SlackAlertGateway(slack_webhook)

    # Null gateway (알림 없이 실행)
    from interx_engine.application.ports.alert_gateway_port import AlertGatewayPort
    class _NullGateway(AlertGatewayPort):
        def send_p1_alert(self, *a, **kw): return False
        def send_daily_summary(self, *a, **kw): return False
    log.info("알림: 비활성화 (환경변수 미설정)")
    return _NullGateway()


class FullPipelineOrchestrator:
    """
    기존 DailyPipelineOrchestrator 를 래핑하여
    추천 → 파트너 매칭 → 클러스터링 → 알림 → CSV fallback 까지 추가.

    기존 코드 무수정.
    ─────────────────────────────────────────────────────────────────
    raw notice
        │ DailyPipelineOrchestrator (수집·스코어링·Sheets·SQLite)
        ↓
    scored notices + score_cards
        │ RecommendNoticesUseCase
        ↓
    recommendations
        │ MatchPartnersUseCase
        ↓
    partner_matches
        │ ClusterNoticesUseCase
        ↓
    clusters
        │ AlertNoticesUseCase
        ↓
    alerts sent
        │ CsvFallbackWriter
        ↓
    CSV backup
    ─────────────────────────────────────────────────────────────────
    LLM 확장 포인트:
      - RecommendationRules → LLMRecommendationRules (동일 인터페이스)
      - TfidfClusterer      → EmbeddingClusterer     (동일 인터페이스)
    """

    def __init__(
        self,
        collector,
        base_dir: str,
        sheet_gateway=None,
        attachment_download_use_case=None,
        document_parse_use_case=None,
        sqlite_writer=None,
    ):
        base = Path(base_dir)

        self.daily = DailyPipelineOrchestrator(
            collector=collector,
            sheet_gateway=sheet_gateway,
            attachment_download_use_case=attachment_download_use_case,
            document_parse_use_case=document_parse_use_case,
        )
        self.sqlite_writer = sqlite_writer

        self.base_dir     = base
        self.recommend_uc = RecommendNoticesUseCase()
        self.match_uc     = MatchPartnersUseCase(
            CsvPartnerRepository(str(base / "data/partners.csv"))
        )
        self.cluster_uc   = ClusterNoticesUseCase(EmbeddingClusterer(threshold=0.70))
        self.alert_uc     = AlertNoticesUseCase(_build_alert_gateway())
        self.csv_writer   = CsvFallbackWriter(str(base / "output/csv"))

    def run(self, execution_id: str) -> dict:
        start = datetime.now()
        log.info("=== FullPipeline 시작: %s ===", execution_id)

        # ── 1. 수집 + 스코어링 + Sheets + SQLite (기존 파이프라인) ──────────
        result = self.daily.run(execution_id)

        notices     = result["notices"]
        score_cards = result["score_cards"]

        if self.sqlite_writer:
            try:
                self.sqlite_writer.save(execution_id, "full", result)
            except Exception as e:
                log.warning("SQLite 저장 실패: %s", e)

        # ── 2. 추천 생성 ──────────────────────────────────────────────────────
        recommendations = []
        try:
            recommendations = self.recommend_uc.execute(notices, score_cards)
            log.info("추천 생성: %d건", len(recommendations))
        except Exception as e:
            log.error("추천 생성 실패: %s", e)

        # ── 3. 파트너 매칭 ────────────────────────────────────────────────────
        partner_matches = {}
        try:
            partner_matches = self.match_uc.execute(notices, score_cards)
            log.info("파트너 매칭: %d건 공고 매칭", len(partner_matches))
        except Exception as e:
            log.warning("파트너 매칭 실패: %s", e)

        # ── 4. 클러스터링 ──────────────────────────────────────────────────────
        clusters = []
        try:
            clusters = self.cluster_uc.execute(notices, score_cards)
            log.info("클러스터링: %d개 그룹", len(clusters))
        except Exception as e:
            log.warning("클러스터링 실패: %s", e)

        # ── 5. 알림 ───────────────────────────────────────────────────────────
        alert_result = {}
        try:
            alert_result = self.alert_uc.execute(
                notices, score_cards, recommendations, execution_id
            )
            log.info("알림 전송: P1=%d건", alert_result.get("p1_alerted", 0))
        except Exception as e:
            log.warning("알림 실패: %s", e)

        # ── 6. CSV fallback ───────────────────────────────────────────────────
        try:
            self.csv_writer.write_all(
                execution_id, notices, score_cards,
                recommendations, partner_matches, clusters,
            )
        except Exception as e:
            log.warning("CSV fallback 실패: %s", e)

        # ── 7. 수주 예측 결과 재사용 (DailyPipeline Step 11-D에서 이미 실행됨) ──
        win_report = result.get("win_report")
        try:
            if win_report:
                log.info("수주 예측 결과 재사용: 총 %d건 | A등급 %d건",
                         len(win_report.predictions), len(win_report.top_opportunities))
                _save_json_artifact(self.base_dir, "win_report_latest.json", {
                    "execution_id":      execution_id,
                    "created_at":        datetime.now().isoformat(),
                    "total":             len(win_report.predictions),
                    "a_count":           len(win_report.top_opportunities),
                    "predictions":       _to_jsonable(win_report.predictions),
                    "top_opportunities": win_report.top_opportunities,
                })
        except Exception as e:
            log.warning("수주 예측 JSON 저장 실패: %s", e)

        # ── 8. 제안서 결과 재사용 (DailyPipeline Step 11-E에서 이미 실행됨) ──
        proposals = result.get("proposal_files", [])

        # ── 9. 클러스터 JSON 저장 (대시보드용) ───────────────────────────────
        try:
            _save_json_artifact(self.base_dir, "clusters_latest.json", {
                "created_at": datetime.now().isoformat(),
                "count":      len(clusters),
                "clusterer":  "TfidfClusterer",
                "clusters":   _to_jsonable(clusters),
            })
        except Exception as e:
            log.warning("클러스터 JSON 저장 실패: %s", e)

        elapsed = (datetime.now() - start).total_seconds()
        log.info("=== FullPipeline 완료: %.1f초 ===", elapsed)

        return {
            **result,
            "recommendations":   recommendations,
            "partner_matches":   partner_matches,
            "clusters":          clusters,
            "alert_result":      alert_result,
            "win_report":        win_report,
            "proposals":         proposals,
            "elapsed_seconds":   elapsed,
        }
