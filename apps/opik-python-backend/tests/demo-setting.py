import pytest
import uuid6
import json
import re

from opik_backend.demo_data_generator import create_demo_data


def generate_uuid():
    return str(uuid6.uuid7())


def respond_with_json(content, status=200):
    return dict(status=status, content_type="application/json", response=json.dumps(content))


def mock_feedback_definition_exists(httpserver):
    httpserver.expect_request("/v1/private/feedback-definitions", method="GET", query_string="name=User+feedback") \
        .respond_with_json({
            "content": [{"name": "User feedback"}],
            "page": 1,
            "size": 1,
            "total": 1
        })


def test_create_demo_data_structure(httpserver):
    """
    Validates that the demo data is created correctly when no data exists yet.
    """
    base_url = httpserver.url_for("/")

    # Setup mocks for expected requests
    httpserver.expect_request("/v1/private/projects/retrieve", method="POST").respond_with_data(status=404)
    httpserver.expect_request("/v1/private/traces/batch", method="POST").respond_with_data(status=204)
    httpserver.expect_request("/v1/private/spans/batch", method="POST").respond_with_data(status=204)
    httpserver.expect_request("/v1/private/traces/feedback-scores", method="PUT").respond_with_data(status=204)

    # Feedback definitions
    httpserver.expect_request("/v1/private/feedback-definitions", method="GET", query_string="name=User+feedback") \
        .respond_with_json({"content": [], "page": 1, "size": 0, "total": 0})
    httpserver.expect_request("/v1/private/feedback-definitions", method="POST").respond_with_data(status=201)

    # Prompts and datasets
    httpserver.expect_request("/v1/private/prompts", method="POST").respond_with_data(status=201)
    httpserver.expect_request("/v1/private/datasets", method="POST").respond_with_data(status=201)

    httpserver.expect_request("/v1/private/datasets/retrieve", method="POST").respond_with_json({
        "id": generate_uuid(),
        "name": "Demo dataset",
        "description": "",
        "metadata": {},
        "created_at": "2024-01-01T00:00:00Z",
        "last_updated_at": "2024-01-01T00:00:00Z"
    })

    httpserver.expect_request("/v1/private/datasets/items", method="POST").respond_with_data(status=201)

    dataset_items = [
        {"data": {"input": "What is the best LLM evaluation tool?", "output": "Comet"}, "id": generate_uuid(), "source": "sdk"},
        {"data": {"input": "What is the easiest way to start with Opik?", "output": "Read the docs"}, "id": generate_uuid(), "source": "sdk"},
        {"data": {"input": "Is Opik open source?", "output": "Yes"}, "id": generate_uuid(), "source": "sdk"},
    ]

    httpserver.expect_request("v1/private/datasets/items/stream", method="POST").respond_with_data(
        status=200,
        headers={"Content-Type": "application/octet-stream"},
        response_data=b"\n".join(json.dumps(item).encode("utf-8") for item in dataset_items)
    )

    httpserver.expect_request("/v1/private/datasets/items", method="PUT").respond_with_data(status=204)

    # Experiments
    httpserver.expect_request("/v1/private/experiments", method="POST").respond_with_data(status=201)
    httpserver.expect_request("/v1/private/experiments/items", method="POST").respond_with_data(status=204)

    # Prompts versions
    prompt = {
        "id": generate_uuid(),
        "prompt_id": generate_uuid(),
        "commit": "12345678",
        "template": "",
        "metadata": {},
        "type": "mustache",
        "variables": []
    }
    httpserver.expect_request("/v1/private/prompts/versions/retrieve", method="POST").respond_with_json(prompt)
    httpserver.expect_request("/v1/private/prompts/versions", method="POST").respond_with_json(prompt)

    # Optimization endpoint mocks
    httpserver.expect_request("/v1/private/optimizations", method="POST").respond_with_json({
        "id": generate_uuid(),
        "name": "Demo optimization",
        "dataset_id": generate_uuid(),
        "objective_name": "Demo objective",
        "status": "running",
        "metadata": {},
        "created_at": "2024-01-01T00:00:00Z"
    })

    httpserver.expect_request(re.compile(r"/v1/private/optimizations/.*"), method="PUT").respond_with_data(status=204)

    # Thread feedback endpoints
    httpserver.expect_request("/v1/private/traces/threads/close", method="PUT").respond_with_data(status=204)
    httpserver.expect_request("/v1/private/traces/threads/feedback-scores", method="PUT").respond_with_data(status=204)

    # Run and validate
    create_demo_data(base_url, "default", "comet_api_key")
    httpserver.check_assertions()


def fail_on_request(_request):
    raise AssertionError("Request should not have been made in idempotent test!")


def test_create_demo_data_idempotence(httpserver):
    """
    Validates that if demo data already exists, the function avoids re-creating it.
    """
    base_url = httpserver.url_for("/")

    # Existing project
    httpserver.expect_request("/v1/private/projects/retrieve", method="POST").respond_with_json({
        "id": generate_uuid()
    })

    # Feedback definition already exists
    mock_feedback_definition_exists(httpserver)

    # All other calls that would mutate data should NOT be called
    endpoints = [
        "/v1/private/traces/batch",
        "/v1/private/spans/batch",
        "/v1/private/traces/feedback-scores",
        "/v1/private/prompts",
        "/v1/private/datasets",
        "/v1/private/datasets/retrieve",
        "/v1/private/datasets/items",
        "v1/private/datasets/items/stream",
        "/v1/private/datasets/items",
        "/v1/private/experiments",
        "/v1/private/experiments/items",
        "/v1/private/prompts/versions/retrieve",
        "/v1/private/prompts/versions",
        "/v1/private/optimizations",
        "/v1/private/traces/threads/close",
        "/v1/private/traces/threads/feedback-scores",
        "/v1/private/traces/threads/retrieve"
    ]

    for endpoint in endpoints:
        method = "POST" if "retrieve" in endpoint or "stream" in endpoint else "PUT" if "feedback-scores" in endpoint or "close" in endpoint else "POST"
        httpserver.expect_request(re.compile(endpoint), method=method).respond_with_handler(fail_on_request)

    # Run and validate
    create_demo_data(base_url, "default", "comet_api_key")
    httpserver.check_assertions()
