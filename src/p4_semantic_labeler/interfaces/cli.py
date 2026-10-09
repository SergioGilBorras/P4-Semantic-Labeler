"""Standard-library argparse CLI; JSON/JSONL output usable in automation."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from p4_semantic_labeler.config import Settings
from p4_semantic_labeler.core.errors import LabelerError
from p4_semantic_labeler.core.file_utils import read_local_file
from p4_semantic_labeler.core.models import BatchRequest, Context, LabelRequest, Subject
from p4_semantic_labeler.core.service import Labeler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="p4-labeler")
    subs = parser.add_subparsers(dest="command", required=True)
    label = subs.add_parser("label", help="Generate one label")
    label.add_argument("--name", required=True)
    label.add_argument("--kind", default="concept")
    label.add_argument("--file", type=Path)
    label.add_argument("--stdin", action="store_true", help="Read additional context from stdin")
    label.add_argument("--documentation")
    label.add_argument("--output-type", choices=("title", "summary"), default="title")
    label.add_argument("--max-chars", type=int, default=80)
    label.add_argument("--style", default="neutral")
    label.add_argument("--language", default="es")
    label.add_argument("--json", action="store_true", help="Output full JSON response")
    batch = subs.add_parser("batch", help="Process JSON array or JSONL, output JSONL")
    batch.add_argument("--input", type=Path, help="Use stdin when omitted")
    batch.add_argument("--format", choices=("json", "jsonl"), default="jsonl")
    subs.add_parser("mcp", help="Run local stdio MCP server")
    return parser


async def _run(args: argparse.Namespace, settings: Settings) -> int:
    labeler = Labeler(settings=settings)
    if args.command == "mcp":
        from p4_semantic_labeler.interfaces.mcp_server import main as run_mcp

        run_mcp()
        return 0
    if args.command == "label":
        content: dict[str, str] = {}
        if args.documentation:
            content["documentation"] = args.documentation
        if args.file is not None:
            field = "source_code" if args.file.suffix.lower() == ".py" else "text"
            content[field] = read_local_file(args.file, settings)
        if args.stdin:
            content["before"] = sys.stdin.read(settings.max_input_chars + 1)
        request = LabelRequest(
            subject=Subject(kind=args.kind, name=args.name),
            context=Context(**content) if content else None,
            output_type=args.output_type, max_chars=args.max_chars,
            style=args.style, language=args.language,
        )
        result = await labeler.agenerate(request)
        print(result.model_dump_json() if args.json else result.label)
        return 0
    raw = (
        read_local_file(args.input, settings)
        if args.input is not None
        else sys.stdin.read(settings.max_file_bytes + 1)
    )
    if len(raw.encode("utf-8")) > settings.max_file_bytes:
        from p4_semantic_labeler.core.errors import InputLimitError

        raise InputLimitError()
    objects = json.loads(raw) if args.format == "json" else [json.loads(line) for line in raw.splitlines() if line.strip()]
    if not isinstance(objects, list):
        raise ValueError("batch JSON must contain an array")
    req = BatchRequest(items=objects)
    result = await labeler.agenerate_batch(req)
    for item in result.items:
        print(item.model_dump_json(exclude_none=True))
    return 1 if result.error_count else 0


def main() -> None:
    args = build_parser().parse_args()
    try:
        code = asyncio.run(_run(args, Settings.from_env()))
    except (LabelerError, ValidationError, ValueError, OSError) as exc:
        # Do not print raw model/provider/private input data into errors.
        if isinstance(exc, LabelerError):
            message = exc.public_message
        elif isinstance(exc, ValidationError):
            message = "Invalid request fields"
        else:
            message = type(exc).__name__
        print(json.dumps({"error": message}), file=sys.stderr)
        code = 2
    sys.exit(code)


if __name__ == "__main__":
    main()
