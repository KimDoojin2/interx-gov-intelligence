from __future__ import annotations
import logging
from typing import List
import requests
from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.recommendation import Recommendation
from interx_engine.application.ports.alert_gateway_port import AlertGatewayPort

log = logging.getLogger(__name__)


class SlackAlertGateway(AlertGatewayPort):
    """
    Incoming Webhook URL 방식.
    SLACK_WEBHOOK_URL 환경변수로 동작.
    """

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def _send(self, blocks: list) -> bool:
        if not self.webhook_url:
            log.info("[Slack SKIP] webhook URL 미설정")
            return False
        try:
            r = requests.post(self.webhook_url, json={"blocks": blocks}, timeout=10)
            r.raise_for_status()
            return True
        except Exception as e:
            log.warning("Slack 전송 실패: %s", e)
            return False

    def send_p1_alert(
        self, notices: List[Notice], recommendations: List[Recommendation]
    ) -> bool:
        rec_map = {r.notice_id: r for r in recommendations}
        blocks  = [
            {"type": "header", "text": {"type": "plain_text", "text": "🚨 InterX P1 공고 발생"}},
            {"type": "divider"},
        ]
        for n in notices[:5]:
            rec = rec_map.get(n.notice_id)
            text = (
                f"*{n.title[:50]}*\n"
                f"📌 {n.site} | 마감 {n.deadline_date}\n"
                f"💡 {rec.reason if rec else '-'}\n"
                f"✅ {rec.action if rec else '-'}\n"
                f"🔗 {n.detail_url}"
            )
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": text},
            })
        return self._send(blocks)

    def send_daily_summary(self, stats: dict) -> bool:
        dist = stats.get("grade_distribution", {})
        text = (
            f"*📊 InterX 일별 요약* — `{stats.get('execution_id', '')}`\n"
            f"전체 {stats.get('total', 0)}건 | "
            f"A *{dist.get('A', 0)}* | B {dist.get('B', 0)} | "
            f"C {dist.get('C', 0)} | D {dist.get('D', 0)}\n"
            f"L3강공고 {stats.get('l3_count', 0)}건 | "
            f"파트너전달 {stats.get('partner_count', 0)}건"
        )
        blocks = [{
            "type": "section",
            "text": {"type": "mrkdwn", "text": text},
        }]
        return self._send(blocks)
