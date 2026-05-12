from __future__ import annotations
import logging
from typing import List
from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.core.entities.recommendation import Recommendation
from interx_engine.application.ports.alert_gateway_port import AlertGatewayPort

log = logging.getLogger(__name__)


class AlertNoticesUseCase:
    """
    P1 공고 즉시 알림 + 일별 요약 알림 전송.
    gateway 교체만으로 Telegram ↔ Slack ↔ Email 전환 가능.
    """

    def __init__(self, gateway: AlertGatewayPort):
        self.gateway = gateway

    def execute(
        self,
        notices: List[Notice],
        score_cards: List[ScoreCard],
        recommendations: List[Recommendation],
        execution_id: str,
    ) -> dict:
        score_map = {s.notice_id: s for s in score_cards}
        rec_map   = {r.notice_id: r for r in recommendations}

        a_notices = [n for n in notices if score_map.get(n.notice_id, None) and
                     score_map[n.notice_id].priority_grade == "A"]
        a_recs    = [rec_map[n.notice_id] for n in a_notices if n.notice_id in rec_map]

        alert_sent = False
        if a_notices:
            try:
                alert_sent = self.gateway.send_p1_alert(a_notices, a_recs)
            except Exception as e:
                log.warning("A등급 알림 전송 실패: %s", e)

        grade_dist = {}
        for s in score_cards:
            grade_dist[s.priority_grade] = grade_dist.get(s.priority_grade, 0) + 1

        stats = {
            "execution_id": execution_id,
            "total": len(notices),
            "p1_count": len(a_notices),
            "grade_distribution": grade_dist,
            "l3_count": sum(1 for n in notices if n.l3_strong == "Y"),
            "partner_count": sum(1 for n in notices if n.partner_candidate == "Y"),
        }

        try:
            self.gateway.send_daily_summary(stats)
        except Exception as e:
            log.warning("일별 요약 전송 실패: %s", e)

        return {"a_alerted": len(a_notices), "alert_sent": alert_sent, "stats": stats}
