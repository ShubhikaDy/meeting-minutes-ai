"""Basic tests. None of these call the real API."""

from src.processor import MeetingProcessor, build_markdown
from src.utils import load_config, load_prompts, parse_json, render_prompt


class FakeClient:
    """Stands in for the real LLM client so tests run offline."""

    def generate_json(self, system_prompt, user_prompt, temperature=None, parse_retries=1):
        if "key_topics" in user_prompt:  # the summary prompt
            return {
                "title": "Test Meeting",
                "participants": ["Raj", "Priya"],
                "summary": "A short test meeting.",
                "key_topics": ["Launch"],
            }
        return {  # the extraction prompt
            "decisions": [{"decision": "Ship on Friday", "context": "Team agreed"}],
            "action_items": [
                {"task": "Fix bug", "owner": "Priya", "deadline": "Thursday", "priority": "High"}
            ],
            "open_items": [{"issue": "Server cost", "reason": "Nobody assigned"}],
        }

    def generate(self, system_prompt, user_prompt, temperature=None, json_mode=False):
        return "Subject: Test\n\nHello team"


def test_parse_json_plain():
    assert parse_json('{"a": 1}') == {"a": 1}


def test_parse_json_with_code_fences():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_with_extra_text():
    assert parse_json('Here you go: {"a": 1} Thanks') == {"a": 1}


def test_render_prompt_keeps_json_braces():
    out = render_prompt('Return {"x": 1} for {name}', name="Raj")
    assert out == 'Return {"x": 1} for Raj'


def test_pipeline_with_fake_client():
    processor = MeetingProcessor(FakeClient(), load_config(), load_prompts())
    result = processor.run("Raj: hello")
    assert result["summary"]["title"] == "Test Meeting"
    assert result["extraction"]["action_items"][0]["owner"] == "Priya"
    assert result["email"].startswith("Subject:")


def test_markdown_has_all_sections():
    processor = MeetingProcessor(FakeClient(), load_config(), load_prompts())
    markdown = build_markdown(processor.run("Raj: hello", with_email=False))
    for section in ("## Summary", "## Decisions", "## Action Items", "## Open Items"):
        assert section in markdown
    assert "Priya" in markdown