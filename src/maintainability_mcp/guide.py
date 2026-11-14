"""Pre-generation guidance: conventions, guidelines, and prior findings."""

from __future__ import annotations

import re
from pathlib import Path

from .config import Config
from .history import HistoryStore

GUIDELINES = [
    {"id": "F.1", "text": "Package meaningful operations as carefully named functions.", "tags": {"refactor", "design"}},
    {"id": "F.2", "text": "A function should perform a single logical operation.", "tags": {"refactor", "design"}},
    {"id": "F.3", "text": "Keep functions short and simple.", "tags": {"refactor", "size"}},
    {"id": "F.4", "text": "If a function might have to be evaluated at compile time, declare it constexpr.", "tags": {"performance"}},
    {"id": "C.1", "text": "Organize related data into structures (structs or classes).", "tags": {"design"}},
    {"id": "C.2", "text": "Use class if the class has an invariant; use struct if the data members can vary independently.", "tags": {"design"}},
    {"id": "C.9", "text": "Minimize the exposure of members.", "tags": {"design", "encapsulation"}},
    {"id": "I.1", "text": "Make interfaces explicit with concepts.", "tags": {"design", "templates"}},
    {"id": "I.4", "text": "Make interfaces precisely and strongly typed.", "tags": {"design", "types"}},
    {"id": "R.1", "text": "Manage resources automatically using resource handles and RAII.", "tags": {"resource", "memory"}},
    {"id": "R.3", "text": "A raw pointer (a T*) is non-owning.", "tags": {"resource", "memory"}},
    {"id": "R.11", "text": "Avoid calling new and delete explicitly.", "tags": {"resource", "memory"}},
    {"id": "ES.5", "text": "Keep scopes small.", "tags": {"refactor", "size"}},
    {"id": "ES.20", "text": "Always initialize an object.", "tags": {"safety"}},
    {"id": "ES.23", "text": "Prefer the {} initializer syntax.", "tags": {"safety"}},
    {"id": "ES.45", "text": "Avoid magic constants; use symbolic constants.", "tags": {"readability", "intent"}},
    {"id": "SL.1", "text": "Use libraries wherever possible.", "tags": {"design"}},
    {"id": "SL.2", "text": "Prefer the standard library to other libraries.", "tags": {"design"}},
    {"id": "NL.1", "text": "Don't say in comments what can be clearly stated in code.", "tags": {"intent", "readability"}},
    {"id": "NL.2", "text": "State intent in comments.", "tags": {"intent", "readability"}},
    {"id": "SF.3", "text": "Use header files for all declarations used in multiple source files.", "tags": {"headers", "build"}},
    {"id": "SF.5", "text": "A .cpp file must include the header file(s) that defines its interface.", "tags": {"headers", "build"}},
    {"id": "SF.7", "text": "Don't write using namespace at global scope in a header file.", "tags": {"headers", "build"}},
    {"id": "SF.8", "text": "Use #include guards for all .h files.", "tags": {"headers", "build"}},
    {"id": "CP.2", "text": "Avoid data races.", "tags": {"concurrency", "safety"}},
    {"id": "CP.20", "text": "Use RAII, never plain lock()/unlock().", "tags": {"concurrency", "resource"}},
    {"id": "CP.21", "text": "Use std::lock() or std::scoped_lock to acquire multiple mutexes.", "tags": {"concurrency"}},
    {"id": "CP.43", "text": "Minimize the time spent in a critical section.", "tags": {"concurrency", "performance"}},
    {"id": "CP.44", "text": "Remember to name your lock_guards and unique_locks.", "tags": {"concurrency"}},
    {"id": "CP.50", "text": "Define a mutex together with the data it protects.", "tags": {"concurrency", "design"}},
]

CORE_IDS = {"F.1", "F.2", "F.3", "C.1", "C.9", "R.1", "R.11", "ES.5", "ES.45", "NL.2", "SF.7", "SF.8"}


def _tags_for_task(task: str) -> set[str]:
    task = task.lower()
    tags = set()
    if any(word in task for word in ("refactor", "clean", "simplify", "maintain")):
        tags |= {"refactor", "size", "design"}
    if any(word in task for word in ("memory", "resource", "raii", "leak", "pointer")):
        tags |= {"resource", "memory"}
    if any(word in task for word in ("thread", "concurr", "mutex", "lock", "race")):
        tags |= {"concurrency"}
    if any(word in task for word in ("header", "include", "build", "compile")):
        tags |= {"headers", "build"}
    if any(word in task for word in ("performance", "speed", "latency")):
        tags |= {"performance"}
    if any(word in task for word in ("comment", "intent", "readab", "name")):
        tags |= {"intent", "readability"}
    return tags


class GuideEngine:
    def __init__(self, config: Config, history: HistoryStore):
        self.config = config
        self.history = history

    def guide(
        self,
        paths: list[str],
        task: str = "",
        standards: list[str] | None = None,
        repo: str = ".",
    ) -> dict:
        conventions = detect_conventions(paths)
        tags = _tags_for_task(task)
        selected = [
            guideline
            for guideline in GUIDELINES
            if guideline["id"] in CORE_IDS or (tags & guideline["tags"])
        ]
        if standards:
            wanted = {item.lower() for item in standards}
            selected = [
                guideline
                for guideline in selected
                if guideline["id"].lower() in wanted
                or any(word in guideline["text"].lower() for word in wanted)
            ]
        return {
            "task": task,
            "conventions": conventions,
            "guidelines": selected,
            "prior_findings": self.history.recent_findings(repo, limit=10),
            "checklist": [
                "Keep functions small and single-purpose.",
                "Use RAII and avoid raw owning pointers.",
                "Prefer the standard library over hand-rolled loops.",
                "Name constants instead of using magic numbers.",
                "Keep headers self-contained and include-guarded.",
                "Leave enough rationale for the next reader.",
            ],
        }


def detect_conventions(paths: list[str]) -> dict:
    roots = []
    for item in paths:
        path = Path(item)
        roots.append(path if path.is_dir() else path.parent)
    candidates = (
        ".clang-tidy",
        ".clang-format",
        "compile_commands.json",
        "CMakeLists.txt",
        "CONTRIBUTING.md",
        "README.md",
    )
    found: dict[str, str] = {}
    for name in candidates:
        for root in roots:
            candidate = root / name
            if candidate.exists():
                found[name] = str(candidate)
                break
    checks = None
    if ".clang-tidy" in found:
        text = Path(found[".clang-tidy"]).read_text(errors="replace")
        match = re.search(r"Checks:\s*['\"]?([^'\"\n]+)", text)
        if match:
            checks = match.group(1).strip()
    return {
        "files": found,
        "clang_tidy_checks": checks,
        "build_system": "cmake" if "CMakeLists.txt" in found else None,
    }
