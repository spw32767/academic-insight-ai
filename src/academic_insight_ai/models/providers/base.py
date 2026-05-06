from __future__ import annotations

from abc import ABC, abstractmethod

from academic_insight_ai.models.types import GenerateRequest, GenerateResponse


class BaseModelProvider(ABC):
    @abstractmethod
    def generate(self, request: GenerateRequest) -> GenerateResponse:
        raise NotImplementedError
