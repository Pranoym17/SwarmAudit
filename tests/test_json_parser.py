from app.schemas import Severity
from app.services.json_parser import parse_agent_output, parse_json_object


def test_parse_json_object_accepts_fenced_json():
    data = parse_json_object('```json\n{"findings": []}\n```')

    assert data == {"findings": []}


def test_parse_json_object_extracts_object_from_extra_text():
    data = parse_json_object('Here is JSON: {"findings": []} done.')

    assert data == {"findings": []}


def test_parse_agent_output_returns_empty_output_for_invalid_json():
    output = parse_agent_output("not json", "Security Agent")

    assert output.findings == []
    assert output.metadata["parse_error"] is True


def test_parse_agent_output_validates_findings():
    output = parse_agent_output(
        {
            "findings": [
                {
                    "title": "Unsafe eval",
                    "severity": "HIGH",
                    "file_path": "app.py",
                    "line_start": 1,
                    "line_end": 1,
                    "description": "eval is used",
                    "why_it_matters": "Arbitrary code execution",
                    "suggested_fix": "Remove eval",
                    "agent_source": "Security Agent",
                }
            ]
        },
        "Security Agent",
    )

    assert output.findings[0].severity == Severity.high
