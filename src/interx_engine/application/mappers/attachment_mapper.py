"""
attachment_mapper  –  DEPRECATED (v4.4)

04_첨부파일목록 / 04_첨부문서관리 시트는 2026-04-21 아키텍처 정리로 제거되었습니다.
첨부파일 정보는 notice_to_master_row() 의 '첨부수' / '첨부명' 컬럼으로 대체합니다.

하위 호환성을 위해 함수 시그니처는 유지하되 빈 리스트를 반환합니다.
"""
from __future__ import annotations

import warnings
from typing import List

from interx_engine.core.entities.notice import Notice


def notice_to_attachment_rows(notice: Notice) -> List[dict]:  # noqa: ARG001
    """(Deprecated) 빈 리스트 반환 — 04_첨부파일목록 시트 제거됨"""
    warnings.warn(
        "notice_to_attachment_rows is deprecated; 04_첨부파일목록 sheet was removed.",
        DeprecationWarning,
        stacklevel=2,
    )
    return []


def notice_to_doc_mgmt_rows(notice: Notice) -> List[dict]:  # noqa: ARG001
    """(Deprecated) 빈 리스트 반환 — 04_첨부문서관리 시트 제거됨"""
    warnings.warn(
        "notice_to_doc_mgmt_rows is deprecated; 04_첨부문서관리 sheet was removed.",
        DeprecationWarning,
        stacklevel=2,
    )
    return []
