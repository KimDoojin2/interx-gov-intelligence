from abc import ABC, abstractmethod
from typing import List
from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.recommendation import Recommendation


class AlertGatewayPort(ABC):
    @abstractmethod
    def send_p1_alert(self, notices: List[Notice], recommendations: List[Recommendation]) -> bool:
        raise NotImplementedError

    @abstractmethod
    def send_daily_summary(self, stats: dict) -> bool:
        raise NotImplementedError
