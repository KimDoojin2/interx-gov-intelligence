"""
스마트 알림 발송 유스케이스 — A등급 신규, D-3 마감, 변경 감지 공고를 자동 알림

사용법 (파이프라인 마지막 단계에서 호출):
    from interx_engine.application.use_cases.send_smart_alerts import send_smart_alerts
    send_smart_alerts(notices, score_cards, alert_gateway, execution_id)

주의: 이 모듈은 구현만 해둔 것으로, 실제 발송은 환경변수 설정 후 활성화.
  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID  또는  SLACK_WEBHOOK_URL
"""
from __future__ import annotations

import logging
from datetime import date
from typing import List, Optional

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.application.ports.alert_gateway_port import AlertGatewayPort

log = logging.getLogger("interx.smart_alerts")


def _dday(deadline: str) -> int:
    if not deadline:
        return 999
    try:
        return (date.fromisoformat(deadline[:10]) - date.today()).days
    except Exception:
        return 999


def send_smart_alerts(
    notices: List[Notice],
    score_cards: List[ScoreCard],
    gateway: Optional[AlertGatewayPort],
    execution_id: str = "",
    *,
    enabled: bool = False,
) -> dict:
    """
    스마트 알림 발송.

    Args:
        enabled: False면 로그만 남기고 실제 발송 안 함 (기본값).
                 True로 바꾸면 실제 Telegram/Slack 발송.

    Returns:
        {"a_grade_new": int, "urgent_d3": int, "changed": int, "sent": bool}
    """
    score_map = {s.notice_id: s for s in score_cards}
    result = {"a_grade_new": 0, "urgent_d3": 0, "changed": 0, "sent": False}

    # ── 1) A등급 신규 공고 ───────────────────────────────────────────────────
    a_new = []
    for n in notices:
        sc = score_map.get(n.notice_id)
        if sc and sc.priority_grade == "A" and getattr(n, "is_new", False):
            a_new.append((n, sc))
    result["a_grade_new"] = len(a_new)

    # ── 2) D-3 마감 임박 (A/B등급만) ────────────────────────────────────────
    urgent = []
    for n in notices:
        sc = score_map.get(n.notice_id)
        dd = _dday(n.deadline_date)
        if 0 <= dd <= 3 and sc and sc.priority_grade in ("A", "B"):
            urgent.append((n, sc, dd))
    urgent.sort(key=lambda x: x[2])
    result["urgent_d3"] = len(urgent)

    # ── 3) 변경 감지 공고 (A/B등급만) ───────────────────────────────────────
    changed = []
    for n in notices:
        sc = score_map.get(n.notice_id)
        if getattr(n, "is_changed", False) and sc and sc.priority_grade in ("A", "B"):
            changed.append((n, sc))
    result["changed"] = len(changed)

    # ── 알림 메시지 구성 ─────────────────────────────────────────────────────
    if not (a_new or urgent or changed):
        log.info("[SmartAlert] 알림 대상 없음")
        return result

    lines = [f"<b>🔔 [InterX] 스마트 알림</b>  ({execution_id[:16]})", ""]

    if a_new:
        lines.append(f"<b>⭐ A등급 신규 공고 {len(a_new)}건</b>")
        for n, sc in a_new[:5]:
            lines.append(f"  • {n.title[:45]}  ({sc.fitness_score:.0f}점)")
            lines.append(f"    마감: {n.deadline_date or '미정'}  |  {n.detail_url[:60]}")
        if len(a_new) > 5:
            lines.append(f"  … 외 {len(a_new) - 5}건")
        lines.append("")

    if urgent:
        lines.append(f"<b>🚨 D-3 마감 임박 {len(urgent)}건</b>")
        for n, sc, dd in urgent[:5]:
            lines.append(f"  • [D-{dd}] {n.title[:40]}  ({sc.priority_grade}등급)")
            lines.append(f"    {n.detail_url[:60]}")
        lines.append("")

    if changed:
        lines.append(f"<b>🔄 변경 감지 {len(changed)}건</b>")
        for n, sc in changed[:5]:
            lines.append(f"  • {n.title[:45]}  ({sc.priority_grade}등급)")
        lines.append("")

    message = "\n".join(lines)

    if not enabled:
        log.info("[SmartAlert] 발송 비활성 (enabled=False). 대상: A신규=%d, D-3=%d, 변경=%d",
                 len(a_new), len(urgent), len(changed))
        log.debug("[SmartAlert] 메시지 미리보기:\n%s", message)
        return result

    if gateway:
        try:
            gateway._send(message)
            result["sent"] = True
            log.info("[SmartAlert] 알림 발송 완료: A신규=%d, D-3=%d, 변경=%d",
                     len(a_new), len(urgent), len(changed))
        except Exception as e:
            log.warning("[SmartAlert] 발송 실패: %s", e)

    return result
