"""Optional libclang adapter for class-level metrics."""

from __future__ import annotations

from pathlib import Path

from ..models import AnalysisResult, make_finding
from .base import Analyzer


class LibclangAnalyzer(Analyzer):
    name = "libclang"

    def __init__(
        self,
        library_file: str | None = None,
        cxx_standard: str = "c++20",
    ):
        self.library_file = library_file
        self.cxx_standard = cxx_standard
        self._configured = False

    def _configure(self) -> None:
        import clang.cindex as ci

        if not self.library_file or self._configured:
            return
        current = getattr(ci.Config, "library_file", None)
        if current is None:
            ci.Config.set_library_file(self.library_file)
        elif current != self.library_file:
            raise RuntimeError(
                f"libclang already loaded from {current}; "
                f"cannot switch to {self.library_file}"
            )
        self._configured = True

    def available(self) -> bool:
        try:
            import clang.cindex as ci

            self._configure()
            ci.Index.create()
            return True
        except Exception:  # noqa: BLE001 - libclang raises backend-specific errors
            return False

    def analyze(self, path: Path) -> AnalysisResult:
        import clang.cindex as ci

        try:
            self._configure()
            index = ci.Index.create()
            translation_unit = index.parse(
                str(path), args=[f"-std={self.cxx_standard}"]
            )
        except Exception:  # noqa: BLE001 - libclang raises backend-specific errors
            return AnalysisResult(status="error")

        findings = []
        max_class_size = 0
        for cursor in translation_unit.cursor.walk_preorder():
            if cursor.kind not in (
                ci.CursorKind.CLASS_DECL,
                ci.CursorKind.STRUCT_DECL,
            ):
                continue
            if cursor.location.file is None or str(cursor.location.file) != str(path):
                continue
            methods = 0
            fields = 0
            for child in cursor.get_children():
                if child.kind in (
                    ci.CursorKind.CXX_METHOD,
                    ci.CursorKind.CONSTRUCTOR,
                    ci.CursorKind.DESTRUCTOR,
                ):
                    methods += 1
                elif child.kind == ci.CursorKind.FIELD_DECL:
                    fields += 1
            size = methods + fields
            max_class_size = max(max_class_size, size)
            if methods > 20 or fields > 15:
                findings.append(
                    make_finding(
                        file=str(path),
                        rule="god-class",
                        dimension="god_class",
                        severity="warning",
                        message=(
                            f"Class '{cursor.spelling}' has {methods} methods "
                            f"and {fields} fields."
                        ),
                        start_line=cursor.location.line or 1,
                        evidence={
                            "class": cursor.spelling,
                            "methods": methods,
                            "fields": fields,
                        },
                        suggested_fix=(
                            "Split the class by responsibility and extract "
                            "cohesive collaborators."
                        ),
                        impact={
                            "defects": 0.7,
                            "time": 0.7,
                            "predictability": 0.6,
                        },
                        effort="L",
                        confidence=0.7,
                        analyzer=self.name,
                    )
                )
        return AnalysisResult(
            findings=findings,
            metrics={"god_class": min(1.0, max_class_size / 40.0)},
        )
