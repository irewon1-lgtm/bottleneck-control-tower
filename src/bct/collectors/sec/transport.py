"""Existing serial SEC HTTP client, isolated from optional ORM imports."""
import time
from urllib.request import Request,urlopen

class SECTransport:
    """One serial requester, explicit identity, hard limits, no automatic retries."""

    def __init__(self, user_agent: str, *, interval_seconds: float = 0.25,
                 timeout_seconds: int = 25, max_bytes: int = 20_000_000):
        if not isinstance(user_agent, str) or len(user_agent.strip()) < 12:
            raise ValueError("identify the project and contact in the SEC User-Agent")
        if interval_seconds < 0.1 or timeout_seconds <= 0 or max_bytes < 1024:
            raise ValueError("invalid transport limits")
        self.user_agent = user_agent
        self.interval = interval_seconds
        self.timeout = timeout_seconds
        self.max_bytes = max_bytes
        self._previous = None

    def get(self, url: str) -> bytes:
        if not (url.startswith("https://data.sec.gov/submissions/CIK") or
                url.startswith("https://www.sec.gov/Archives/edgar/data/")):
            raise ValueError("unapproved SEC URL")
        if self._previous is not None:
            wait = self.interval - (time.monotonic() - self._previous)
            if wait > 0:
                time.sleep(wait)
        self._previous = time.monotonic()
        request = Request(url, headers={"User-Agent": self.user_agent,
                                        "Accept-Encoding": "identity", "Accept": "*/*"})
        with urlopen(request, timeout=self.timeout) as response:
            if response.status != 200:
                raise IOError(f"SEC HTTP {response.status}")
            data = response.read(self.max_bytes + 1)
        if len(data) > self.max_bytes:
            raise IOError("SEC response exceeded max_bytes")
        return data

