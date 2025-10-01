import json
import uuid
import traceback
import inspect
from types import ModuleType
from typing import Type, Union, List, Any, Dict
from sys import argv

from opik.evaluation.metrics import BaseMetric
from opik.evaluation.metrics.score_result import ScoreResult

TRACE_THREAD_METRIC_TYPE = "trace_thread"


def get_metric_class(module: ModuleType) -> Union[Type[BaseMetric], None]:
    """Find a subclass of BaseMetric defined in the given module."""
    for _, cls in inspect.getmembers(module, inspect.isclass):
        if issubclass(cls, BaseMetric) and cls is not BaseMetric:
            return cls
    return None


def to_score_list(score_result: Union[ScoreResult, List[ScoreResult], None]) -> List[ScoreResult]:
    """Normalize result to a list of ScoreResult instances."""
    if score_result is None:
        return []
    if isinstance(score_result, ScoreResult):
        return [score_result]
    if isinstance(score_result, list):
        return [s for s in score_result if isinstance(s, ScoreResult)]
    return []


def run_user_code(code: str) -> Union[ModuleType, str]:
    """Executes user-provided code in a new module context and returns the module or error message."""
    module = ModuleType(str(uuid.uuid4()))
    try:
        exec(code, module.__dict__)
        return module
    except Exception:
        tb = "\n".join(traceback.format_exc().splitlines()[3:])
        return f"Field 'code' contains invalid Python code:\n{tb}"


def run_metric(metric_class: Type[BaseMetric], data: Dict[str, Any], payload_type: str) -> Union[List[ScoreResult], str]:
    """Instantiates and runs the metric scoring function."""
    try:
        metric = metric_class()
        if payload_type == TRACE_THREAD_METRIC_TYPE:
            result = metric.score(data)
        else:
            result = metric.score(**data)
        return to_score_list(result)
    except Exception:
        tb = "\n".join(traceback.format_exc().splitlines()[3:])
        return f"The provided 'code' and 'data' fields can't be evaluated:\n{tb}"


def main():
    if len(argv) < 3:
        print(json.dumps({"error": "Usage: script.py <code> <data_json> [<payload_type>]"}))
        exit(1)

    code, data_json = argv[1], argv[2]
    payload_type = argv[3] if len(argv) > 3 else None

    try:
        data = json.loads(data_json)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON in 'data': {str(e)}"}))
        exit(1)

    module_or_error = run_user_code(code)
    if isinstance(module_or_error, str):
        print(json.dumps({"error": module_or_error}))
        exit(1)

    metric_class = get_metric_class(module_or_error)
    if metric_class is None:
        print(json.dumps({
            "error": "Field 'code' doesn't contain a valid subclass of 'BaseMetric'"
        }))
        exit(1)

    result_or_error = run_metric(metric_class, data, payload_type)
    if isinstance(result_or_error, str):
        print(json.dumps({"error": result_or_error}))
        exit(1)

    response = {
        "scores": [score.__dict__ for score in result_or_error]
    }
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
