import pytest

from promptcheck.errors import ConflictError, InvalidInputError, NotFoundError
from promptcheck.prompts import service


@pytest.fixture
def prompt(conn):
    return service.create_prompt(conn, "refund-reply", "Replies to refund requests")


# ---------- prompts ----------

def test_create_and_list_prompts(conn, prompt):
    assert prompt["name"] == "refund-reply"
    listed = service.list_prompts(conn)
    assert [p["name"] for p in listed] == ["refund-reply"]
    assert listed[0]["latest_version"] is None
    assert listed[0]["test_case_count"] == 0


def test_duplicate_prompt_name_conflicts(conn, prompt):
    with pytest.raises(ConflictError):
        service.create_prompt(conn, "refund-reply")


def test_blank_prompt_name_rejected(conn):
    with pytest.raises(InvalidInputError):
        service.create_prompt(conn, "   ")


def test_missing_prompt_is_not_found(conn):
    with pytest.raises(NotFoundError):
        service.get_prompt(conn, 999)


# ---------- versions ----------

def test_versions_are_numbered_sequentially(conn, prompt):
    v1 = service.publish_version(conn, prompt["id"], "Reply to: {message}")
    v2 = service.publish_version(conn, prompt["id"], "Reply in Spanish to: {message}")
    assert (v1["version"], v2["version"]) == (1, 2)
    assert v2["variables"] == ["message"]
    assert [v["version"] for v in service.list_versions(conn, prompt["id"])] == [1, 2]
    assert service.list_prompts(conn)[0]["latest_version"] == 2


def test_publishing_identical_template_conflicts(conn, prompt):
    service.publish_version(conn, prompt["id"], "Reply to: {message}")
    with pytest.raises(ConflictError, match="identical to v1"):
        service.publish_version(conn, prompt["id"], "Reply to: {message}")


def test_same_template_with_new_model_is_a_new_version(conn, prompt):
    service.publish_version(conn, prompt["id"], "Reply to: {message}", model="a")
    v2 = service.publish_version(conn, prompt["id"], "Reply to: {message}", model="b")
    assert v2["version"] == 2


def test_empty_template_rejected(conn, prompt):
    with pytest.raises(InvalidInputError):
        service.publish_version(conn, prompt["id"], "  ")


def test_publish_to_missing_prompt_is_not_found(conn):
    with pytest.raises(NotFoundError):
        service.publish_version(conn, 999, "Hi")


def test_missing_version_is_not_found(conn, prompt):
    with pytest.raises(NotFoundError):
        service.get_version(conn, prompt["id"], 7)


def test_template_variables_are_unique_and_ordered():
    assert service.template_variables("{b} {a} {b} {{not}}") == ["b", "a", "not"]


def test_diff_counts_added_and_removed_lines(conn, prompt):
    service.publish_version(conn, prompt["id"], "Be polite.\nReply to: {message}")
    service.publish_version(conn, prompt["id"], "Be polite.\nReply in Spanish.\nAnswer: {message}")
    diff = service.diff_versions(conn, prompt["id"], 1, 2)
    assert (diff["added"], diff["removed"]) == (2, 1)
    assert diff["model_changed"] is False
    assert "+Reply in Spanish." in diff["diff"]


# ---------- test cases ----------

def test_add_and_list_test_cases(conn, prompt):
    tc = service.add_test_case(
        conn, prompt["id"], "spanish refund",
        {"message": "quiero devolver"}, [{"type": "contains", "arg": "reembolso"}],
    )
    assert tc["inputs"] == {"message": "quiero devolver"}
    assert tc["checks"] == [{"type": "contains", "arg": "reembolso"}]
    assert tc["archived"] is False
    assert [t["id"] for t in service.list_test_cases(conn, prompt["id"])] == [tc["id"]]


def test_test_case_with_invalid_check_rejected(conn, prompt):
    with pytest.raises(InvalidInputError):
        service.add_test_case(conn, prompt["id"], "bad", {}, [{"type": "nope"}])


def test_test_case_with_non_string_input_rejected(conn, prompt):
    with pytest.raises(InvalidInputError):
        service.add_test_case(
            conn, prompt["id"], "bad", {"n": 3}, [{"type": "valid_json"}]
        )


def test_blank_test_case_name_rejected(conn, prompt):
    with pytest.raises(InvalidInputError):
        service.add_test_case(conn, prompt["id"], " ", {}, [{"type": "valid_json"}])


def test_archived_test_cases_are_hidden(conn, prompt):
    tc = service.add_test_case(conn, prompt["id"], "t", {}, [{"type": "valid_json"}])
    service.archive_test_case(conn, tc["id"])
    assert service.list_test_cases(conn, prompt["id"]) == []


def test_archiving_missing_test_case_is_not_found(conn):
    with pytest.raises(NotFoundError):
        service.archive_test_case(conn, 999)


# ---------- the seam used by evals ----------

def test_get_version_for_run_bundles_version_and_active_tests(conn, prompt):
    v1 = service.publish_version(conn, prompt["id"], "Reply to: {message}", model="m")
    keep = service.add_test_case(conn, prompt["id"], "keep", {"message": "hi"}, [{"type": "valid_json"}])
    drop = service.add_test_case(conn, prompt["id"], "drop", {"message": "x"}, [{"type": "valid_json"}])
    service.archive_test_case(conn, drop["id"])

    bundle = service.get_version_for_run(conn, v1["id"])
    assert bundle["template"] == "Reply to: {message}"
    assert bundle["model"] == "m"
    assert [t["id"] for t in bundle["test_cases"]] == [keep["id"]]


def test_get_version_for_run_missing_version(conn):
    with pytest.raises(NotFoundError):
        service.get_version_for_run(conn, 999)
