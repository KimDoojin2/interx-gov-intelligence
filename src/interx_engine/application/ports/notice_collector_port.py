from abc import ABC, abstractmethod
from typing import List
from interx_engine.core.entities.notice import Notice


class NoticeCollectorPort(ABC):
    @abstractmethod
    def collect(self, execution_id: str) -> List[Notice]:
        raise NotImplementedError
