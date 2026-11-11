"""The seam between the evals and prompts services (ADR-2).

Evals depends only on the PromptsGateway protocol. In Assignment 1 it was implemented
in-process; now HttpPromptsGateway calls the prompts service over HTTP, found through
the PROMPTS_URL setting, and nothing else in evals changed.
"""
import logging
from typing import Protocol

import httpx

from app.errors import NotFoundError, UpstreamError, UpstreamUnavailableError

log = logging.getLogger(__name__)


class PromptsGateway(Protocol):
    def get_version_for_run(self, version_id: int) -> dict:
        """Return {id, prompt_id, version, template, model, test_cases: [...]}.

        Raises NotFoundError (404), UpstreamUnavailableError (503) if the prompts
        service is down or too slow, or UpstreamError (502) if it answers wrongly.
        """
        ...


class HttpPromptsGateway:
    def __init__(self, base_url: str, timeout_s: float, transport: httpx.BaseTransport | None = None):
        # one client for the app's lifetime, so connections are reused
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_s,
                                    transport=transport)

    def get_version_for_run(self, version_id: int) -> dict:
        try:
            response = self._client.get(f"/versions/{version_id}/for-run")
        except httpx.TimeoutException as e:
            log.warning("prompts service timed out: %s", e)
            raise UpstreamUnavailableError("the prompts service did not answer in time; try again") from e
        except httpx.TransportError as e:
            log.warning("prompts service unreachable: %s", e)
            raise UpstreamUnavailableError("the prompts service is unavailable; try again later") from e

        if response.status_code == 200:
            return response.json()
        if response.status_code == 404:
            raise NotFoundError(f"prompt version {version_id} not found")
        if response.status_code in (502, 503, 504):
            raise UpstreamUnavailableError("the prompts service is unavailable; try again later")
        log.error("prompts service answered %d: %s", response.status_code, response.text[:200])
        raise UpstreamError(f"the prompts service answered {response.status_code}")

    def close(self) -> None:
        self._client.close()
