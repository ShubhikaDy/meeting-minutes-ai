"""Command-line entry point for the Meeting Minutes Generator.

Usage (run from the project root):
    python -m src.main
    python -m src.main --input data/my_meeting.txt --tone friendly
    python -m src.main --no-email
"""

import argparse
import logging
import sys
from pathlib import Path

from src.llm_client import LLMClient, LLMError
from src.processor import MeetingProcessor, build_markdown
from src.utils import (
    load_config,
    load_prompts,
    read_text,
    save_json,
    save_text,
    setup_logging,
)

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Turn a meeting transcript into minutes, action items and a follow-up email."
    )
    parser.add_argument("--input", help="Path to the transcript .txt file")
    parser.add_argument("--config", default="config/config.yaml", help="Path to the config file")
    parser.add_argument("--tone", help="Email tone, e.g. professional, friendly, formal")
    parser.add_argument("--no-email", action="store_true", help="Skip the follow-up email")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    setup_logging(config.get("logging", {}).get("level", "INFO"))

    if args.tone:
        config["email"]["tone"] = args.tone
    with_email = config["email"]["enabled"] and not args.no_email

    try:
        prompts = load_prompts(config["paths"]["prompts_file"])
        input_path = args.input or config["paths"]["default_input"]
        transcript = read_text(input_path)
        logger.info("Loaded transcript: %s (%d characters)", input_path, len(transcript))

        client = LLMClient(config)
        processor = MeetingProcessor(client, config, prompts)
        result = processor.run(transcript, with_email=with_email)
    except (FileNotFoundError, ValueError, LLMError) as exc:
        logger.error("%s", exc)
        return 1

    out_dir = Path(config["paths"]["output_dir"])
    save_json(result, str(out_dir / "minutes.json"))
    markdown = build_markdown(result)
    save_text(markdown, str(out_dir / "minutes.md"))
    if "email" in result:
        save_text(result["email"], str(out_dir / "follow_up_email.txt"))

    print("\n" + "=" * 60)
    print(markdown)
    if "email" in result:
        print("=" * 60)
        print(result["email"])
        print("=" * 60)
    logger.info("Files saved in the '%s' folder", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())