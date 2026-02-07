from __future__ import annotations

import abc

from nachojobs.models import Job


class BaseFetcher(abc.ABC):
    @abc.abstractmethod
    async def fetch(self, identifier: str, company_name: str) -> list[Job]:
        """Fetch all jobs for a company. identifier is slug (Ashby) or token (Greenhouse)."""
