from __future__ import annotations
import logging
from typing import List
import requests
from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.recommendation import Recommendation
from interx_engine.application.ports.alert_gateway_port import AlertGatewayPort

log = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramAlertGateway(AlertGatewayPort):
    """
    환경변수 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 로 동작.
    비어 있으면 로그만 남기고 조용히 통과.
    """

    def __init__(self, token: str, chat_id: str):
        self.token   = token
        self.chat_id = chat_id
        self._url    = _API.format(token=token)

    def _send(self, text: str) -> bool:
        if not self.token or not self.chat_id:
            log.info("[Telegram SKIP] 토큰/채팅ID 미설정")
            return False
        try:
            r = requests.post(
                self._url,
                json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )
            r.raise_for_status()
            return True
        except Exception as e:
            log.warning("Telegram 전송 실패: %s", e)
            return False

    def send_p1_alert(
        self, notices: List[Notice], recommendations: List[Recommendation]
    ) -> bool:
        rec_map = {r.notice_id: r for r in recommendations}
        lines = ["<b>🚨 [InterX] P1 공고 발생</b>", ""]
        for i, n in enumerate(notices[:5], 1):
            rec = rec_map.get(n.notice_id)
            lines.append(f"<b>{i}. {n.title[:40]}</b>")
            lines.append(f"   📌 사이트: {n.site}  |  마감: {n.deadline_date}")
            lines.append(f"   💡 {rec.reason if rec else '-'}")
            lines.append(f"   ✅ 액션: {rec.action if rec else '-'}")
            lines.append(f"   🔗 {n.detail_url[:60]}")
            lines.append("")
        if len(notices) > 5:
            lines.append(f"… 외 {len(notices) - 5}건")
        return self._send("\n".join(lines))

    def send_daily_summary(self, stats: dict) -> bool:
        dist = stats.get("grade_distribution", {})
        msg = (
            f"<b>📊 [InterX] 일별 수집 요약</b>\n"
            f"실행ID: {stats.get('execution_id', '')}\n"
            f"전체: {stats.get('total', 0)}건  |  "
            f"A: {dist.get('A', 0)}  B: {dist.get('B', 0)}  "
            f"C: {dist.get('C', 0)}  D: {dist.get('D', 0)}\n"
            f"L3강공고: {stats.get('l3_count', 0)}건  |  "
            f"파트너전달: {stats.get('partner_count', 0)}건"
        )
        return self._send(msg)
