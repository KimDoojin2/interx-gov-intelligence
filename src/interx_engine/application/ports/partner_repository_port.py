from abc import ABC, abstractmethod
from typing import List
from interx_engine.core.entities.partner import Partner


class PartnerRepositoryPort(ABC):
    @abstractmethod
    def load_all(self) -> List[Partner]:
        raise NotImplementedError
