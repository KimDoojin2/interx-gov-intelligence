"""
DailyPipelineOrchestrator — 9-sheet 아키텍처 + 전체 기능 통합
  수집 → notice_id중복제거 → 마감지난공고제거 → 스코어링
  → TF-IDF중복제거 → 변경감지 → 담당자배정 → 경쟁사트래킹
  → 품질등급 → 행빌드 → 시트업로드 → SQLite저장 → 알림발송
"""
from __future__ import annotations

import logging
import time
from datetime import date
from typing import List, Optional

from interx_engine.application.use_cases.score_notices import ScoreNoticesUseCase
from interx_engine.application.use_cases.deep_parsing import DeepParsingUseCase
from interx_engine.application.use_cases.portfolio_analysis import PortfolioAnalysisUseCase
from interx_engine.application.use_cases.win_prediction import WinPredictionUseCase
from interx_engine.application.use_cases.deduplicate_notices import deduplicate_by_tfidf
from interx_engine.application.use_cases.detect_changes import detect_changes
from interx_engine.application.use_cases.assign_manager import assign_managers
from interx_engine.application.use_cases.assign_milestone import assign_milestones
from interx_engine.application.use_cases.track_competitors import track_competitors
from interx_engine.application.use_cases.detect_recurring import detect_recurring
from interx_engine.application.use_cases.site_quality_grader import grade_site_quality
from interx_engine.application.use_cases.generate_proposal import generate_proposals
from interx_engine.application.mappers.notice_mapper import (
    notice_to_master_row, notice_to_urgent_row, _calc_dday,
)
from interx_engine.application.mappers.kpi_mapper import (
    build_kpi_rows, build_exec_log_row,
    build_site_stats_rows, build_collect_error_rows,
)

log = logging.getLogger("interx.pipeline")


def _urgent_dday() -> int:
    try:
        from interx_engine.infrastructure.config.settings_loader import settings
        return settings.urgent_dday()
    except Exception:
        return 7


def _get_sqlite_writer():
    """SQLitePipelineWriter 싱글턴. 실패 시 None 반환."""
    try:
        from interx_engine.infrastructure.config.settings_loader import settings
        from interx_engine.infrastructure.persistence.sqlite_writer import SQLitePipelineWriter
        return SQLitePipelineWriter(settings.db_path)
    except Exception as e:
        log.debug("[Pipeline] SQLite 초기화 실패: %s", e)
        return None


def _build_alert_gateway():
    """환경변수 기반 알림 게이트웨이 자동 선택. 없으면 None."""
    import os
    telegram_token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    slack_webhook    = os.getenv("SLACK_WEBHOOK_URL", "")

    try:
        if telegram_token and telegram_chat_id:
            from interx_engine.infrastructure.alert.telegram_gateway import TelegramAlertGateway
            log.info("[Pipeline] 알림: Telegram")
            return TelegramAlertGateway(telegram_token, telegram_chat_id)
        if slack_webhook:
            from interx_engine.infrastructure.alert.slack_gateway import SlackAlertGateway
            log.info("[Pipeline] 알림: Slack")
            return SlackAlertGateway(slack_webhook)
    except Exception as e:
        log.warning("[Pipeline] 알림 게이트웨이 초기화 실패: %s", e)
    return None


class DailyPipelineOrchestrator:
    def __init__(self, collector, sheet_gateway=None, alert_gateway=None, **_):
        self._collector       = collector
        self.score_use_case   = ScoreNoticesUseCase()
        self.deep_parsing_uc  = DeepParsingUseCase()
        self.portfolio_uc     = PortfolioAnalysisUseCase()
        self.win_pred_uc      = WinPredictionUseCase()
        self.sheet_gateway    = sheet_gateway
        # 알림: 명시 전달 우선, 없으면 환경변수에서 자동 탐지
        self.alert_gateway    = alert_gateway or _build_alert_gateway()

    def run(self, execution_id: str) -> dict:
        t0 = time.monotonic()

        # ── 1. 수집 ──────────────────────────────────────────────────────────
        log.info("[Pipeline] 수집 시작 (%s)", execution_id)
        notices = self._collector.collect(execution_id)
        log.info("[Pipeline] %d건 수집 완료", len(notices))

        # ── 2. notice_id 중복 제거 ────────────────────────────────────────────
        seen, unique = set(), []
        for n in notices:
            if n.notice_id not in seen:
                seen.add(n.notice_id); unique.append(n)
        if len(unique) < len(notices):
            log.info("[Pipeline] notice_id 중복 제거: %d → %d건", len(notices), len(unique))
        notices = unique

        # ── 2-B. SQLite 기존 공고 필터 (30일 내 동일 공고 재수집 방지) ─────
        db_skip_count = 0
        sqlite_writer = _get_sqlite_writer()
        if sqlite_writer:
            try:
                existing_ids = sqlite_writer.existing_notice_ids(days=30)
                if existing_ids:
                    before = len(notices)
                    # 기존 공고는 is_new=False로 마킹만 하고 파이프라인은 계속 진행
                    # (detect_changes에서 변경 감지 후 변경 공고는 유지)
                    for n in notices:
                        if n.notice_id in existing_ids:
                            n.is_new = False
                    db_skip_count = sum(1 for n in notices if not n.is_new)
                    log.info("[Pipeline] DB 기존 공고 %d건 감지 (변경 확인 예정)", db_skip_count)
            except Exception as e:
                log.debug("[Pipeline] 기존 공고 ID 조회 실패: %s", e)

        # ── 3. 마감 지난 공고 제거 ────────────────────────────────────────────
        today_date = date.today()
        before_filter = len(notices)
        valid_notices = []
        for n in notices:
            if getattr(n, "open_ended", False):
                valid_notices.append(n)
                continue
            dl = n.deadline_date
            if not dl:
                valid_notices.append(n)
                continue
            try:
                dl_date = date.fromisoformat(str(dl)[:10])
                if dl_date >= today_date:
                    valid_notices.append(n)
            except Exception:
                valid_notices.append(n)
        expired_count = before_filter - len(valid_notices)
        if expired_count:
            log.info("[Pipeline] 마감 지난 공고 %d건 제거 (%d → %d건)",
                     expired_count, before_filter, len(valid_notices))
        notices = valid_notices

        # ── 4. 스코어링 ──────────────────────────────────────────────────────
        notices, score_cards = self.score_use_case.execute(notices)
        score_map = {s.notice_id: s for s in score_cards}

        # ── 5. TF-IDF cross-site 중복 완전 제거 ──────────────────────────────
        notices, dup_count = deduplicate_by_tfidf(notices, score_cards)

        # ── 6. 공고 변경 감지 ─────────────────────────────────────────────────
        notices, new_count, changed_count = detect_changes(notices)

        # ── 7. 담당자 자동 배정 ───────────────────────────────────────────────
        notices = assign_managers(notices)

        # ── 7-B. BD 마일스톤 자동 배정 ───────────────────────────────────────
        notices = assign_milestones(notices, score_cards)

        # ── 8. 경쟁사 트래킹 ─────────────────────────────────────────────────
        notices = track_competitors(notices)

        # ── 8-B. 정기공고 감지 (recurring_flag / recurring_group 설정) ──────
        try:
            notices, recurring_count = detect_recurring(notices)
            if recurring_count:
                log.info("[Pipeline] 정기공고 감지: %d건", recurring_count)
        except Exception as e:
            log.warning("[Pipeline] 정기공고 감지 실패 (무시): %s", e)
            recurring_count = 0

        # ── 9. 사이트별 품질 등급 ─────────────────────────────────────────────
        quality_grades = grade_site_quality(notices, score_cards)

        # ── 10. 행 빌드 ───────────────────────────────────────────────────────
        master_rows, l3_rows, urgent_rows = [], [], []
        for notice in notices:
            score = score_map.get(notice.notice_id)
            row   = notice_to_master_row(notice, score)
            master_rows.append(row)
            if notice.l3_strong == "Y":
                l3_rows.append(row.copy())
            dday_str = _calc_dday(notice.deadline_date)
            if dday_str and dday_str != "상시":
                try:
                    if 0 <= int(dday_str) <= _urgent_dday():
                        urgent_rows.append(notice_to_urgent_row(notice, score))
                except ValueError:
                    pass

        # ── 11-A. 문서 정밀 파싱 (첨부파일 → 예산·KPI 추출) ────────────────
        try:
            notices = self.deep_parsing_uc.execute(notices)
        except Exception as e:
            log.warning("[Pipeline] DeepParsing 실패 (무시): %s", e)

        # ── 11-B. L3 공고 Claude API 요약 (settings.yaml summarize.enabled=true 만) ─
        try:
            from interx_engine.infrastructure.config.settings_loader import settings as _s
            if _s.summarize_enabled():
                from interx_engine.application.use_cases.summarize_l3 import summarize_l3_notices
                l3_notices = [n for n in notices if n.l3_strong == "Y"]
                if l3_notices:
                    summarize_l3_notices(l3_notices)
                    log.info("[Pipeline] L3 요약 완료: %d건", len(l3_notices))
            else:
                log.debug("[Pipeline] L3 요약 비활성화 (summarize.enabled=false)")
        except Exception as e:
            log.debug("[Pipeline] L3 요약 스킵: %s", e)

        # ── 11-C. 포트폴리오 분석 ────────────────────────────────────────────
        analysis_report = None
        try:
            analysis_report = self.portfolio_uc.execute(execution_id, notices, score_cards)
        except Exception as e:
            log.warning("[Pipeline] PortfolioAnalysis 실패 (무시): %s", e)

        # ── 11-D. 수주 가능성 예측 ───────────────────────────────────────────
        win_report = None
        try:
            win_report = self.win_pred_uc.execute(notices, score_cards, execution_id)
        except Exception as e:
            log.warning("[Pipeline] WinPrediction 실패 (무시): %s", e)

        # ── 11-E. 제안서 초안 자동 생성 (A/B 등급) ───────────────────────────
        try:
            proposal_files = generate_proposals(notices, score_cards)
        except Exception as e:
            log.warning("[Pipeline] 제안서 생성 실패 (무시): %s", e)
            proposal_files = []

        # ── 12. KPI / 통계 / 에러 빌드 ──────────────────────────────────────
        elapsed    = round(time.monotonic() - t0, 1)
        kpi_rows   = build_kpi_rows(execution_id, notices, score_cards)
        site_stats = build_site_stats_rows(execution_id, notices, score_cards)

        raw_errors = getattr(self._collector, "last_errors", [])
        error_rows = build_collect_error_rows(execution_id, raw_errors)

        milestone_counts: dict = {}
        for n in notices:
            ms = getattr(n, "bd_milestone", "")
            if ms:
                for code in ms.split("|"):
                    milestone_counts[code] = milestone_counts.get(code, 0) + 1
        ms_summary = " ".join(f"{k}={v}" for k, v in sorted(milestone_counts.items()))

        exec_log_row = build_exec_log_row(
            execution_id, "pipeline_complete", "OK", elapsed,
            f"총 {len(notices)}건 | L3={len(l3_rows)} | 긴급={len(urgent_rows)} | "
            f"신규={new_count} | 변경={changed_count} | "
            f"마감제거={expired_count} | 중복제거={dup_count} | "
            f"정기공고={recurring_count} | "
            f"경쟁사={sum(1 for n in notices if n.competitor_flag)} | "
            f"제안서={len(proposal_files)} | 에러={len(error_rows)} | "
            f"마일스톤=[{ms_summary}]"
        )

        # ── 13. C/D 학습데이터 자동 export ──────────────────────────────────
        training_export_path = ""
        try:
            from interx_engine.application.use_cases.export_training_data import export_training_data
            training_export_path = export_training_data(notices, score_cards, execution_id)
        except Exception as e:
            log.warning("[Pipeline] 학습데이터 export 실패 (무시): %s", e)

        result = {
            "notices":               notices,
            "score_cards":           score_cards,
            "notice_count":          len(notices),
            "master_rows":           master_rows,
            "l3_rows":               l3_rows,
            "urgent_rows":           urgent_rows,
            "new_count":             new_count,
            "changed_count":         changed_count,
            "dup_count":             dup_count,
            "expired_count":         expired_count,
            "error_count":           len(error_rows),
            "proposal_files":        proposal_files,
            "quality_grades":        quality_grades,
            "analysis_report":       analysis_report,
            "win_report":            win_report,
            "training_export_path":  training_export_path,
        }

        # ── 14. 시트 업로드 ──────────────────────────────────────────────────
        if self.sheet_gateway:
            self._upload(master_rows, l3_rows, urgent_rows,
                         kpi_rows, site_stats, error_rows,
                         exec_log_row, elapsed, len(notices))

        # ── 15. SQLite 저장 ───────────────────────────────────────────────────
        if sqlite_writer:
            try:
                sqlite_writer.save(execution_id, "multi", result)
                log.info("[Pipeline] SQLite 저장 완료 (%d건)", len(notices))
            except Exception as e:
                log.warning("[Pipeline] SQLite 저장 실패 (무시): %s", e)

        # ── 16. 알림 발송 ─────────────────────────────────────────────────────
        if self.alert_gateway:
            self._send_alerts(notices, score_cards, execution_id, elapsed)

        # ── 17. 자동 비지도학습 분석 + 시각화 PNG 생성 (비용 0원) ─────────────
        try:
            from interx_engine.application.use_cases.auto_analysis import run_auto_analysis
            analysis_png = run_auto_analysis(notices, score_cards, execution_id)
            if analysis_png:
                result["analysis_png"] = analysis_png
                log.info("[Pipeline] 자동분석 완료 → %s", analysis_png)
        except Exception as e:
            log.warning("[Pipeline] 자동분석 실패 (무시): %s", e)

        return result

    # ─────────────────────────────────────────────────────────────────────────
    def _upload(self, master_rows, l3_rows, urgent_rows,
                kpi_rows, site_stats, error_rows,
                exec_log_row, elapsed, total):
        gw = self.sheet_gateway

        try:
            if hasattr(gw, "cleanup_old_sheets"):
                gw.cleanup_old_sheets()
        except Exception as e:
            log.warning("[Pipeline] cleanup 실패 (무시): %s", e)

        try:
            gw.replace_rows("01_영업기회_정보", master_rows)
            gw.replace_rows("02_L3강공고",      l3_rows)
            gw.replace_rows("05_긴급마감_공고",  urgent_rows)

            if kpi_rows:   gw.append_rows("22_KPI현황",         kpi_rows)
            if site_stats: gw.append_rows("93_사이트별수집통계", site_stats)
            gw.append_rows("94_실행로그",                        [exec_log_row])
            if error_rows: gw.append_rows("96_수집에러로그",     error_rows)

            log.info("[Pipeline] 업로드 완료 (%.1fs, %d건)", elapsed, total)
        except Exception as exc:
            log.error("[Pipeline] 업로드 실패: %s", exc)
            raise

    def _send_alerts(self, notices, score_cards, execution_id: str, elapsed: float):
        """L3 강공고 알림 + 일별 요약 알림 발송."""
        gw = self.alert_gateway
        if not gw:
            return

        try:
            # L3 강공고 알림
            l3_notices = [n for n in notices if n.l3_strong == "Y"]
            if l3_notices:
                gw.send_p1_alert(l3_notices, [])
                log.info("[Pipeline] L3 알림 발송: %d건", len(l3_notices))

            # 일별 요약 알림
            score_map = {s.notice_id: s for s in score_cards}
            grade_dist: dict = {"A": 0, "B": 0, "C": 0, "D": 0}
            for sc in score_cards:
                grade_dist[sc.priority_grade] = grade_dist.get(sc.priority_grade, 0) + 1

            stats = {
                "execution_id":     execution_id,
                "total":            len(notices),
                "grade_distribution": grade_dist,
                "l3_count":         len(l3_notices),
                "partner_count":    sum(1 for n in notices if n.partner_candidate == "Y"),
                "elapsed_sec":      elapsed,
            }
            gw.send_daily_summary(stats)
        except Exception as e:
            log.warning("[Pipeline] 알림 발송 실패 (무시): %s", e)
