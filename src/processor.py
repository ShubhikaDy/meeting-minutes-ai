"""Meeting pipeline using prompt chaining:
Step 1: summary  ->  Step 2: decisions + action items + open items  ->  Step 3: follow-up email.
"""

import logging
from typing import Any

from src.llm_client import LLMClient
from src.utils import render_prompt

logger = logging.getLogger(__name__)


class MeetingProcessor:
    """Turns a raw meeting transcript into structured minutes."""

    def __init__(self, client: LLMClient, config: dict, prompts: dict) -> None:
        self.client = client
        self.config = config
        self.prompts = prompts
        self.system_prompt: str = prompts["system_prompt"]

    def _temperature(self, task: str) -> float:
        """Get the temperature for a task from the config file."""
        return self.config["tasks"][task]["temperature"]

    # ---------- Step 1 ----------
    def summarize(self, transcript: str) -> dict:
        """Step 1: title, participants, summary, key topics."""
        logger.info("Step 1/3: summarizing transcript")
        prompt = render_prompt(self.prompts["summary_prompt"], transcript=transcript)
        data = self.client.generate_json(
            self.system_prompt, prompt, temperature=self._temperature("summary")
        )
        data.setdefault("title", "Meeting Minutes")
        data.setdefault("participants", [])
        data.setdefault("summary", "Not specified")
        data.setdefault("key_topics", [])
        return data

    # ---------- Step 2 ----------
    def extract(self, transcript: str) -> dict:
        """Step 2: decisions, action items (owner, deadline, priority) and open items."""
        logger.info("Step 2/3: extracting decisions, action items and open items")
        prompt = render_prompt(self.prompts["extraction_prompt"], transcript=transcript)
        data = self.client.generate_json(
            self.system_prompt, prompt, temperature=self._temperature("extraction")
        )
        data.setdefault("decisions", [])
        data.setdefault("action_items", [])
        data.setdefault("open_items", [])
        return data

    # ---------- Step 3 ----------
    def draft_email(self, summary: dict, extraction: dict) -> str:
        """Step 3: follow-up email built from the results of steps 1 and 2."""
        logger.info("Step 3/3: drafting follow-up email")
        email_cfg = self.config["email"]

        decisions = "\n".join(
            f"- {d.get('decision', '')} ({d.get('context', '')})"
            for d in extraction["decisions"]
        ) or "None"
        actions = "\n".join(
            f"- {a.get('task', '')} | owner: {a.get('owner', 'Unassigned')} | "
            f"deadline: {a.get('deadline', 'Not specified')}"
            for a in extraction["action_items"]
        ) or "None"
        open_items = "\n".join(
            f"- {o.get('issue', '')} ({o.get('reason', '')})"
            for o in extraction["open_items"]
        ) or "None"

        prompt = render_prompt(
            self.prompts["email_prompt"],
            tone=email_cfg["tone"],
            sender_name=email_cfg["sender_name"],
            title=summary["title"],
            participants=", ".join(summary["participants"]) or "Team",
            summary=summary["summary"],
            decisions=decisions,
            action_items=actions,
            open_items=open_items,
        )
        return self.client.generate(
            self.system_prompt, prompt, temperature=self._temperature("email")
        )

    # ---------- Full pipeline ----------
    def run(self, transcript: str, with_email: bool = True) -> dict[str, Any]:
        """Run the whole chain and return everything in one dictionary."""
        summary = self.summarize(transcript)
        extraction = self.extract(transcript)
        result: dict[str, Any] = {"summary": summary, "extraction": extraction}
        if with_email:
            result["email"] = self.draft_email(summary, extraction)
        logger.info("Pipeline finished")
        return result


def build_markdown(result: dict) -> str:
    """Turn the pipeline result into a readable Markdown report."""
    s, e = result["summary"], result["extraction"]
    lines = [
        f"# {s['title']}",
        "",
        f"**Participants:** {', '.join(s['participants']) or 'Not specified'}",
        "",
        "## Summary",
        s["summary"],
        "",
        "## Key Topics",
        *[f"- {topic}" for topic in s["key_topics"]],
        "",
        "## Decisions",
    ]
    if e["decisions"]:
        lines += [f"- **{d.get('decision', '')}** - {d.get('context', '')}" for d in e["decisions"]]
    else:
        lines.append("- None recorded")

    lines += ["", "## Action Items", "", "| Task | Owner | Deadline | Priority |", "|---|---|---|---|"]
    for a in e["action_items"]:
        lines.append(
            f"| {a.get('task', '')} | {a.get('owner', 'Unassigned')} | "
            f"{a.get('deadline', 'Not specified')} | {a.get('priority', 'Medium')} |"
        )
    if not e["action_items"]:
        lines.append("| None | - | - | - |")

    lines += ["", "## Open Items"]
    if e.get("open_items"):
        lines += [f"- **{o.get('issue', '')}** - {o.get('reason', '')}" for o in e["open_items"]]
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"