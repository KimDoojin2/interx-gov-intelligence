from __future__ import annotations
from typing import Dict, List
from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.core.entities.partner import Partner
from interx_engine.application.ports.partner_repository_port import PartnerRepositoryPort


def _top_k() -> int:
    try:
        from interx_engine.infrastructure.config.settings_loader import settings
        return settings.top_k()
    except Exception:
        return 3


class MatchPartnersUseCase:
    """
    공고별로 파트너 DB를 검색해 매칭 점수 상위 TOP_K개 파트너를 반환한다.
    matching 알고리즘:
      score = Σ(solution_overlap * sol_score) + Σ(keyword_hit * 2)
    """

    def __init__(self, partner_repo: PartnerRepositoryPort):
        self.partner_repo = partner_repo

    def execute(
        self,
        notices: List[Notice],
        score_cards: List[ScoreCard],
    ) -> Dict[str, List[Partner]]:
        partners = self.partner_repo.load_all()
        score_map = {s.notice_id: s for s in score_cards}
        result: Dict[str, List[Partner]] = {}

        for notice in notices:
            score = score_map.get(notice.notice_id)
            if score is None or score.priority_grade == "D":
                continue

            matched: List[Partner] = []
            for partner in partners:
                match_score = 0.0

                # 솔루션 오버랩 점수
                for sol in partner.solutions:
                    sol_score = score.solution_scores.get(sol, 0.0)
                    if sol_score > 0:
                        match_score += sol_score * 0.8

                # 키워드 오버랩 점수
                full_text = f"{notice.title} {notice.summary}".lower()
                for kw in partner.keywords:
                    if kw.lower() in full_text:
                        match_score += 2.0

                if match_score > 0:
                    import copy
                    p = copy.copy(partner)
                    p.match_score = round(match_score, 1)
                    matched.append(p)

            matched.sort(key=lambda x: x.match_score, reverse=True)
            result[notice.notice_id] = matched[: _top_k()]

        return result
