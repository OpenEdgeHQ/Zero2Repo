#!/usr/bin/env python3
"""Parse step-by-step PRD Markdown: per-step files or legacy single-file PRD."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PrdStep:
    step_num: int
    title: str
    content: str  # full text including the ### heading
    start_line: int
    end_line: int


@dataclass(frozen=True)
class PrdSource:
    """Resolved PRD location for a case public/ directory."""

    mode: str  # "dir" or "legacy"
    path: Path  # public/prd/ or public/Full_PRD.draft.md


_STEP_HEADING_RE = re.compile(r"^###\s+Step\s+(\d+)\s*:\s*(.+)$", re.MULTILINE)
_MIN_STEP_CHARS = 200


def resolve_prd_source(public_dir: Path) -> PrdSource | None:
    """Return PRD source for *public_dir*, preferring public/prd/ over legacy file.

    Resolution order: the structured ``public/prd/`` directory, then the legacy
    ``Full_PRD.draft.md`` draft, then the merged holistic ``Full_PRD.md`` that
    the canonical single-document PRD. The last
    fallback lets cases that only ship the merged PRD
    resolve without a ``prd/`` directory.
    """
    public_dir = Path(public_dir)
    prd_dir = public_dir / "prd"
    if (prd_dir / "index.json").is_file():
        return PrdSource(mode="dir", path=prd_dir)
    legacy = public_dir / "Full_PRD.draft.md"
    if legacy.is_file():
        return PrdSource(mode="legacy", path=legacy)
    merged = public_dir / "Full_PRD.md"
    if merged.is_file():
        return PrdSource(mode="legacy", path=merged)
    return None


def load_prd_index(prd_dir: Path) -> dict:
    index_path = Path(prd_dir) / "index.json"
    return json.loads(index_path.read_text(encoding="utf-8"))


def _step_file_path(prd_dir: Path, step_num: int) -> Path:
    return Path(prd_dir) / "steps" / f"step_{step_num}.md"


def _parse_step_heading(content: str) -> tuple[int, str] | None:
    match = _STEP_HEADING_RE.search(content)
    if not match:
        return None
    return int(match.group(1)), match.group(2).strip()


def get_step_from_dir(prd_dir: Path, step_num: int) -> PrdStep | None:
    """Read a single step file from public/prd/steps/step_N.md."""
    prd_dir = Path(prd_dir)
    step_path = _step_file_path(prd_dir, step_num)
    if not step_path.is_file():
        return None
    content = step_path.read_text(encoding="utf-8")
    if not content.endswith("\n"):
        content += "\n"
    parsed = _parse_step_heading(content)
    if parsed:
        num, title = parsed
    else:
        index = load_prd_index(prd_dir)
        title = ""
        for entry in index.get("steps", []):
            if entry.get("step") == step_num:
                title = entry.get("title", "")
                break
        num = step_num
    return PrdStep(
        step_num=num,
        title=title,
        content=content,
        start_line=0,
        end_line=content.count("\n"),
    )


def list_steps_from_dir(prd_dir: Path) -> list[PrdStep]:
    """Return all steps listed in index.json, in order."""
    prd_dir = Path(prd_dir)
    index = load_prd_index(prd_dir)
    steps: list[PrdStep] = []
    for entry in index.get("steps", []):
        step_num = int(entry["step"])
        step = get_step_from_dir(prd_dir, step_num)
        if step:
            if entry.get("title"):
                step = PrdStep(
                    step_num=step.step_num,
                    title=entry["title"],
                    content=step.content,
                    start_line=step.start_line,
                    end_line=step.end_line,
                )
            steps.append(step)
    return steps


def get_previous_steps_summary_from_dir(prd_dir: Path, up_to_step: int) -> str:
    parts: list[str] = []
    for step in list_steps_from_dir(prd_dir):
        if step.step_num >= up_to_step:
            break
        what_match = re.search(
            r"\*\*What to build:\*\*\s*\n(.+?)(?=\n\*\*|\n###|\Z)",
            step.content,
            re.DOTALL,
        )
        what_text = what_match.group(1).strip() if what_match else ""
        parts.append(f"### Step {step.step_num}: {step.title}\n{what_text}")
    return "\n\n".join(parts)


def get_future_steps_titles(source: PrdSource | Path, after_step: int) -> str:
    if isinstance(source, PrdSource):
        if source.mode == "dir":
            return get_future_steps_titles_from_dir(source.path, after_step)
        source = source.path
    titles: list[str] = []
    for step in _parse_steps_legacy(Path(source)):
        if step.step_num > after_step:
            titles.append(f"- Step {step.step_num}: {step.title}")
    return "\n".join(titles) if titles else "(none — this is the final step)"


def get_future_steps_titles_from_dir(prd_dir: Path, after_step: int) -> str:
    titles: list[str] = []
    for step in list_steps_from_dir(prd_dir):
        if step.step_num > after_step:
            titles.append(f"- Step {step.step_num}: {step.title}")
    return "\n".join(titles) if titles else "(none — this is the final step)"


def count_steps_from_dir(prd_dir: Path) -> int:
    return len(list_steps_from_dir(prd_dir))


def validate_prd_dir(prd_dir: Path, min_step_chars: int = _MIN_STEP_CHARS) -> list[str]:
    """Return validation error messages for public/prd/ layout."""
    prd_dir = Path(prd_dir)
    errors: list[str] = []
    index_path = prd_dir / "index.json"
    if not index_path.is_file():
        return [f"Missing {index_path}"]
    try:
        index = load_prd_index(prd_dir)
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON in {index_path}: {exc}"]

    for required in ("overview.md", "non_functional.md", "out_of_scope.md"):
        path = prd_dir / required
        if not path.is_file():
            errors.append(f"Missing {path}")
        elif len(path.read_text(encoding="utf-8").strip()) < 50:
            errors.append(f"{path} is too short")

    steps = index.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("index.json must contain a non-empty 'steps' array")
        return errors

    for entry in steps:
        step_num = entry.get("step")
        rel = entry.get("file") or f"steps/step_{step_num}.md"
        step_path = prd_dir / rel
        if not step_path.is_file():
            errors.append(f"Missing step file {step_path}")
            continue
        if len(step_path.read_text(encoding="utf-8").strip()) < min_step_chars:
            errors.append(f"{step_path} is too short (< {min_step_chars} chars)")
    return errors


def read_prd_text_for_validation(source: PrdSource) -> str:
    """Concatenate PRD text for blacklist / leakage scanning."""
    if source.mode == "legacy":
        return source.path.read_text(encoding="utf-8")
    prd_dir = source.path
    parts = [
        (prd_dir / "overview.md").read_text(encoding="utf-8"),
    ]
    for step in list_steps_from_dir(prd_dir):
        parts.append(step.content)
    parts.append((prd_dir / "non_functional.md").read_text(encoding="utf-8"))
    parts.append((prd_dir / "out_of_scope.md").read_text(encoding="utf-8"))
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Unified API (auto-select dir vs legacy)
# ---------------------------------------------------------------------------


def get_step(source: PrdSource | str | Path, step_num: int) -> PrdStep | None:
    if isinstance(source, PrdSource):
        if source.mode == "dir":
            return get_step_from_dir(source.path, step_num)
        source = source.path
    return _get_step_legacy(Path(source), step_num)


def parse_steps(source: PrdSource | str | Path) -> list[PrdStep]:
    if isinstance(source, PrdSource):
        if source.mode == "dir":
            return list_steps_from_dir(source.path)
        source = source.path
    return _parse_steps_legacy(Path(source))


def get_previous_steps_summary(source: PrdSource | str | Path, up_to_step: int) -> str:
    if isinstance(source, PrdSource):
        if source.mode == "dir":
            return get_previous_steps_summary_from_dir(source.path, up_to_step)
        source = source.path
    return _get_previous_steps_summary_legacy(Path(source), up_to_step)


def count_steps(source: PrdSource | str | Path) -> int:
    return len(parse_steps(source))


def get_step_content(source: PrdSource | str | Path, step_num: int) -> str | None:
    step = get_step(source, step_num)
    return step.content if step else None


def step_file_path(source: PrdSource, step_num: int) -> Path | None:
    if source.mode != "dir":
        return None
    return _step_file_path(source.path, step_num)


# ---------------------------------------------------------------------------
# Legacy single-file PRD
# ---------------------------------------------------------------------------


def _parse_steps_legacy(prd_path: Path) -> list[PrdStep]:
    text = prd_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    steps: list[PrdStep] = []
    matches = list(_STEP_HEADING_RE.finditer(text))

    for i, match in enumerate(matches):
        step_num = int(match.group(1))
        title = match.group(2).strip()
        start_offset = match.start()
        start_line = text[:start_offset].count("\n")

        if i + 1 < len(matches):
            end_offset = matches[i + 1].start()
        else:
            end_offset = _find_section_end(text, match.end())

        end_line = text[:end_offset].count("\n")
        content = text[match.start():end_offset].rstrip("\n") + "\n"

        steps.append(PrdStep(
            step_num=step_num,
            title=title,
            content=content,
            start_line=start_line,
            end_line=end_line,
        ))

    return steps


def _find_section_end(text: str, after_pos: int) -> int:
    next_h2 = re.search(r"^## ", text[after_pos:], re.MULTILINE)
    if next_h2:
        return after_pos + next_h2.start()
    return len(text)


def _get_step_legacy(prd_path: Path, step_num: int) -> PrdStep | None:
    for step in _parse_steps_legacy(prd_path):
        if step.step_num == step_num:
            return step
    return None


def replace_step(prd_path: str | Path, step_num: int, new_content: str) -> bool:
    """Replace a step's content in a legacy single-file PRD. Returns True on success."""
    prd_path = Path(prd_path)
    text = prd_path.read_text(encoding="utf-8")
    steps = _parse_steps_legacy(prd_path)

    target = None
    for s in steps:
        if s.step_num == step_num:
            target = s
            break

    if target is None:
        return False

    lines = text.splitlines(keepends=True)
    if not new_content.endswith("\n"):
        new_content += "\n"

    new_lines = lines[:target.start_line] + [new_content] + lines[target.end_line:]
    prd_path.write_text("".join(new_lines), encoding="utf-8")
    return True


def _get_previous_steps_summary_legacy(prd_path: Path, up_to_step: int) -> str:
    steps = _parse_steps_legacy(prd_path)
    parts: list[str] = []

    for step in steps:
        if step.step_num >= up_to_step:
            break
        what_match = re.search(
            r"\*\*What to build:\*\*\s*\n(.+?)(?=\n\*\*|\n###|\Z)",
            step.content,
            re.DOTALL,
        )
        what_text = what_match.group(1).strip() if what_match else ""
        parts.append(f"### Step {step.step_num}: {step.title}\n{what_text}")

    return "\n\n".join(parts)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: parse_prd.py <public_dir|prd_path> [step_num]", file=sys.stderr)
        sys.exit(1)

    arg_path = Path(sys.argv[1])
    if arg_path.is_dir() and (arg_path / "index.json").exists():
        source = PrdSource(mode="dir", path=arg_path)
    elif arg_path.is_dir():
        resolved = resolve_prd_source(arg_path)
        if not resolved:
            print(f"Error: no PRD found under {arg_path}", file=sys.stderr)
            sys.exit(1)
        source = resolved
    elif arg_path.is_file():
        source = PrdSource(mode="legacy", path=arg_path)
    else:
        print(f"Error: {arg_path} does not exist", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) >= 3:
        step_num = int(sys.argv[2])
        step = get_step(source, step_num)
        if step:
            print(f"Step {step.step_num}: {step.title}")
            print(f"Mode: {source.mode}")
            print("---")
            print(step.content)
        else:
            print(f"Step {step_num} not found", file=sys.stderr)
            sys.exit(1)
    else:
        steps = parse_steps(source)
        print(f"Mode: {source.mode}")
        print(f"Found {len(steps)} steps:")
        for s in steps:
            print(f"  Step {s.step_num}: {s.title}")


if __name__ == "__main__":
    main()
