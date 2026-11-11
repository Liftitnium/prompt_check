"""HttpPromptsGateway: every way the prompts service can answer, or fail to."""
import httpx
import pytest

from app.errors import NotFoundError, UpstreamError, UpstreamUnavailableError
from app.gateway import HttpPromptsGateway

VERSION = {"id": 7, "prompt_id": 1, "version": 2, "template": "Hi {name}", "model": None,
           "test_cases": []}


def gateway_answering(handler) -> HttpPromptsGateway:
    return HttpPromptsGateway("http://prompts:8000/", timeout_s=2, transport=httpx.MockTransport(handler))


def test_returns_the_version_from_the_for_run_endpoint():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, json=VERSION)

    assert gateway_answering(handler).get_version_for_run(7) == VERSION
    assert seen == ["http://prompts:8000/versions/7/for-run"]


def test_404_becomes_not_found():
    with pytest.raises(NotFoundError):
        gateway_answering(lambda r: httpx.Response(404, json={"detail": "x"})).get_version_for_run(7)


@pytest.mark.parametrize("status", [502, 503, 504])
def test_upstream_outage_becomes_503(status):
    with pytest.raises(UpstreamUnavailableError):
        gateway_answering(lambda r: httpx.Response(status)).get_version_for_run(7)


def test_unexpected_answer_becomes_502():
    with pytest.raises(UpstreamError):
        gateway_answering(lambda r: httpx.Response(500, text="boom")).get_version_for_run(7)


def test_timeout_becomes_503():
    def handler(request):
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(UpstreamUnavailableError, match="in time"):
        gateway_answering(handler).get_version_for_run(7)


def test_connection_refused_becomes_503():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    gateway = gateway_answering(handler)
    with pytest.raises(UpstreamUnavailableError, match="unavailable"):
        gateway.get_version_for_run(7)
    gateway.close()


def test_real_timeout_is_enforced():
    # nothing listens on this port in a test run: fails fast instead of hanging
    gateway = HttpPromptsGateway("http://127.0.0.1:1", timeout_s=0.5)
    with pytest.raises(UpstreamUnavailableError):
        gateway.get_version_for_run(7)
