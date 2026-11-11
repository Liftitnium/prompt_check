"""An in-memory prompts service for evals tests.

It answers get_version_for_run with the same shape as the real
GET /versions/{id}/for-run, and has just enough of the prompts API (publish a
version, add/archive test cases) to set up each test.
"""
import itertools

from app.errors import NotFoundError, UpstreamUnavailableError


class FakePromptsGateway:
    def __init__(self):
        self._ids = itertools.count(1)
        self.versions: dict[int, dict] = {}
        self.test_cases: dict[int, dict] = {}
        self.down = False  # True simulates the prompts service being unreachable

    def create_prompt(self, name: str) -> dict:
        return {"id": next(self._ids), "name": name}

    def publish_version(self, prompt_id: int, template: str, model: str | None = None) -> dict:
        number = 1 + sum(1 for v in self.versions.values() if v["prompt_id"] == prompt_id)
        version = {"id": next(self._ids), "prompt_id": prompt_id, "version": number,
                   "template": template, "model": model}
        self.versions[version["id"]] = version
        return dict(version)

    def add_test_case(self, prompt_id: int, name: str, inputs: dict, checks: list[dict]) -> dict:
        tc = {"id": next(self._ids), "prompt_id": prompt_id, "name": name,
              "inputs": inputs, "checks": checks, "archived": False}
        self.test_cases[tc["id"]] = tc
        return dict(tc)

    def archive_test_case(self, test_case_id: int) -> None:
        self.test_cases[test_case_id]["archived"] = True

    def list_test_cases(self, prompt_id: int) -> list[dict]:
        return [dict(tc) for tc in self.test_cases.values()
                if tc["prompt_id"] == prompt_id and not tc["archived"]]

    def get_version_for_run(self, version_id: int) -> dict:
        if self.down:
            raise UpstreamUnavailableError("the prompts service is unavailable; try again later")
        if version_id not in self.versions:
            raise NotFoundError(f"prompt version {version_id} not found")
        version = dict(self.versions[version_id])
        version["test_cases"] = self.list_test_cases(version["prompt_id"])
        return version
