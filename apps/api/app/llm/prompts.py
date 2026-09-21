"""Versioned prompt files: app/llm/prompts/<name>/<version>.md

File format:
    ---
    name: page_ocr
    version: v1
    role: page_ocr
    description: ...
    ---
    ## system
    ...
    ## user
    ... {{variable}} ...

Variables are substituted literally. Untrusted content should be placed inside clearly
delimited tags in the template so the model treats it as data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

PROMPTS_DIR = Path(__file__).with_name("prompts")
_VAR = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


class PromptError(ValueError):
    pass


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    role: str
    system: str
    user: str

    @property
    def variables(self) -> set[str]:
        return set(_VAR.findall(self.system)) | set(_VAR.findall(self.user))

    def render(self, variables: dict[str, str]) -> tuple[str, str]:
        missing = self.variables - variables.keys()
        if missing:
            raise PromptError(f"prompt {self.name}/{self.version} missing variables: {sorted(missing)}")

        def sub(text: str) -> str:
            return _VAR.sub(lambda m: str(variables[m.group(1)]), text)

        return sub(self.system), sub(self.user)


def parse_prompt_file(text: str) -> Prompt:
    if not text.startswith("---"):
        raise PromptError("prompt file must start with front matter")
    _, front, body = text.split("---", 2)
    meta = yaml.safe_load(front) or {}
    sections = re.split(r"^##\s+(system|user)\s*$", body, flags=re.MULTILINE)
    parts: dict[str, str] = {}
    for i in range(1, len(sections) - 1, 2):
        parts[sections[i]] = sections[i + 1].strip()
    if "system" not in parts or "user" not in parts:
        raise PromptError("prompt file needs '## system' and '## user' sections")
    for key in ("name", "version", "role"):
        if key not in meta:
            raise PromptError(f"front matter missing '{key}'")
    return Prompt(str(meta["name"]), str(meta["version"]), str(meta["role"]), parts["system"], parts["user"])


class PromptRegistry:
    def __init__(self, root: Path = PROMPTS_DIR) -> None:
        self.root = root

    def get(self, name: str, version: str | None = None) -> Prompt:
        folder = self.root / name
        if not folder.is_dir():
            raise PromptError(f"unknown prompt: {name}")
        if version is None:
            versions = sorted(folder.glob("v*.md"), key=lambda p: int(p.stem[1:]))
            if not versions:
                raise PromptError(f"no versions for prompt: {name}")
            path = versions[-1]
        else:
            path = folder / f"{version}.md"
        prompt = parse_prompt_file(path.read_text(encoding="utf-8"))
        if prompt.name != name or prompt.version != path.stem:
            raise PromptError(f"prompt metadata does not match file path: {path}")
        return prompt


@lru_cache
def default_registry() -> PromptRegistry:
    return PromptRegistry()
