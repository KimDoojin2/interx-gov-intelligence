from typing import List
from interx_engine.application.ports.notice_collector_port import NoticeCollectorPort
from interx_engine.core.entities.notice import Notice


class MockNoticeCollector(NoticeCollectorPort):
    def collect(self, execution_id: str) -> List[Notice]:
        return [
            Notice(
                execution_id=execution_id,
                site="mock",
                notice_id="MOCK-001",
                title="스마트공장 AI 기반 품질 고도화 지원사업",
                detail_url="https://example.com/1",
                notice_link="https://example.com/1",
                posted_date="2026-04-01",
                deadline_date="2026-06-30",
                ministry="중소벤처기업부",
                agency="테스트기관",
                business_type="제조AI",
                budget="300000000",
                summary="제조, 품질, AI, 스마트공장 중심 사업",
                recommended_solution="Quality.AI",
                recommended_action="검토 후 제안",
                attachments=["공고문.pdf", "신청서.hwp"],
            ),
            Notice(
                execution_id=execution_id,
                site="mock",
                notice_id="MOCK-002",
                title="일반 창업 지원사업",
                detail_url="https://example.com/2",
                notice_link="https://example.com/2",
                posted_date="2026-04-01",
                deadline_date="2026-07-31",
                ministry="테스트부처",
                agency="테스트진흥원",
                business_type="창업",
                budget="100000000",
                summary="창업 일반 지원",
                recommended_solution="",
                recommended_action="보류",
                attachments=[],
            ),
        ]
