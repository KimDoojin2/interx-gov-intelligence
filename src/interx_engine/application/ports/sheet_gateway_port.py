from abc import ABC, abstractmethod
from typing import List, Dict, Any


class SheetGatewayPort(ABC):
    @abstractmethod
    def append_rows(self, worksheet_name: str, rows: List[Dict[str, Any]]) -> None:
        raise NotImplementedError
