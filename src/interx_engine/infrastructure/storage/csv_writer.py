from __future__ import annotations
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import List
from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.core.entities.recommendation import Recommendation
from interx_engine.core.entities.partner import Partner
from interx_engine.core.entities.cluster import NoticeCluster

log = logging.getLogger(__name__)


class CsvFallbackWriter:
    """
    Google Sheets / SQLite 실패 시 CSV 로 낙하산 저장.
    output_dir/YYYYMMDD/ 하위에 파일별로 저장.
    """

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)

    def _dir(self, execution_id: str) -> Path:
        d = self.output_dir / execution_id[:8]
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _write(self, path: Path, rows: List[dict]) -> None:
        if not rows:
            return
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        log.info("CSV 저장: %s (%d행)", path.name, len(rows))

    def write_all(
        self,
        execution_id: str,
        notices: List[Notice],
        score_cards: List[ScoreCard],
        recommendations: List[Recommendation],
        partner_matches: dict,
        clusters: List[NoticeCluster],
    ) -> None:
        d        = self._dir(execution_id)
        score_map = {s.notice_id: s for s in score_cards}
        rec_map   = {r.notice_id: r for r in recommendations}

        # ── notices + scores + recommendations ───────────────────────────────
        master_rows = []
        for n in notices:
            sc  = score_map.get(n.notice_id)
            rec = rec_map.get(n.notice_id)
            sol = sc.solution_scores if sc else {}
            master_rows.append({
                "execution_id":     execution_id,
                "notice_id":        n.notice_id,
                "site":             n.site,
                "title":            n.title,
                "posted_date":      n.posted_date,
                "deadline_date":    n.deadline_date,
                "ministry":         n.ministry,
                "agency":           n.agency,
                "budget":           n.budget,
                "fitness_score":    sc.fitness_score   if sc else "",
                "priority_grade":   sc.priority_grade  if sc else "",
                "priority_score":   sc.priority_score  if sc else "",
                "industry_score":   sc.industry_score  if sc else "",
                "ManufacturingDT":  sol.get("ManufacturingDT", ""),
                "RecipeAI":         sol.get("RecipeAI", ""),
                "QualityAI":        sol.get("QualityAI", ""),
                "InspectionAI":     sol.get("InspectionAI", ""),
                "SafetyAI":         sol.get("SafetyAI", ""),
                "GenAI":            sol.get("GenAI", ""),
                "InfraDS":          sol.get("InfraDS", ""),
                "PdM":              sol.get("PdM", ""),
                "positive_kw":      "|".join(sc.positive_keywords) if sc else "",
                "negative_kw":      "|".join(sc.negative_keywords) if sc else "",
                "l3_strong":        n.l3_strong,
                "partner_candidate":n.partner_candidate,
                "recommended_solution": n.recommended_solution,
                "recommended_action":   n.recommended_action,
                "reason":           rec.reason          if rec else "",
                "action":           rec.action          if rec else "",
                "partner_type":     rec.partner_type    if rec else "",
                "confidence":       rec.confidence      if rec else "",
                "action_deadline":  rec.action_deadline if rec else "",
                "detail_url":       n.detail_url,
            })
        self._write(d / "notices_scored.csv", master_rows)

        # ── partner matches ───────────────────────────────────────────────────
        partner_rows = []
        for notice_id, partners in partner_matches.items():
            for rank, p in enumerate(partners, 1):
                partner_rows.append({
                    "notice_id":   notice_id,
                    "rank":        rank,
                    "partner_id":  p.partner_id,
                    "name":        p.name,
                    "solutions":   "|".join(p.solutions),
                    "tier":        p.tier,
                    "match_score": p.match_score,
                    "contact":     p.contact,
                })
        self._write(d / "partner_matches.csv", partner_rows)

        # ── clusters ─────────────────────────────────────────────────────────
        cluster_rows = []
        for cl in clusters:
            cluster_rows.append({
                "cluster_id":           cl.cluster_id,
                "size":                 cl.size,
                "representative_title": cl.representative_title,
                "top_solution":         cl.top_solution,
                "common_keywords":      "|".join(cl.common_keywords),
                "notice_ids":           "|".join(cl.notice_ids),
            })
        self._write(d / "clusters.csv", cluster_rows)

        log.info("CSV fallback 완료: %s", d)
