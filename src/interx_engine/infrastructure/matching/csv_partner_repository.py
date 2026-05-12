from __future__ import annotations
import csv
from pathlib import Path
from typing import List
from interx_engine.core.entities.partner import Partner
from interx_engine.application.ports.partner_repository_port import PartnerRepositoryPort


class CsvPartnerRepository(PartnerRepositoryPort):
    """
    data/partners.csv 를 읽어 Partner 목록을 반환한다.
    CSV 컬럼: partner_id, name, solutions, keywords, tier, contact, note

    solutions / keywords 는 파이프(|) 구분자로 저장.
    예) ManufacturingDT|QualityAI   /   디지털트윈|품질|이상탐지
    """

    def __init__(self, csv_path: str):
        self.csv_path = Path(csv_path)

    def load_all(self) -> List[Partner]:
        if not self.csv_path.exists():
            return []
        partners = []
        with open(self.csv_path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                solutions = [s.strip() for s in row.get("solutions", "").split("|") if s.strip()]
                keywords  = [k.strip() for k in row.get("keywords",  "").split("|") if k.strip()]
                partners.append(Partner(
                    partner_id=row.get("partner_id", ""),
                    name=row.get("name", ""),
                    solutions=solutions,
                    keywords=keywords,
                    tier=row.get("tier", "TIER3"),
                    contact=row.get("contact", ""),
                    note=row.get("note", ""),
                ))
        return partners
