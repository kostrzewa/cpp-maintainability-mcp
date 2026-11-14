#!/usr/bin/env python3
"""Sample files for maintainability labelling and fit scoring weights.

Usage:
  scripts/calibrate.py sample --repo /path/to/cpp-project
  # fill in the "label" field in calibration/labels.json with one of:
  # excellent, good, fair, poor, bad
  scripts/calibrate.py fit --repo /path/to/cpp-project
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpp_maintainability_mcp.config import Config
from cpp_maintainability_mcp.engine import MaintainabilityEngine
from cpp_maintainability_mcp.models import GRADES, FileScore
from cpp_maintainability_mcp.scoring import ScoringEngine


def load_config(repo: Path, history: Path) -> Config:
    path = repo / "cpp-maintainability.json"
    config = Config.load(path) if path.exists() else Config()
    config.history_path = str(history)
    return config


def scan(repo: Path) -> list[FileScore]:
    with tempfile.TemporaryDirectory() as tmp:
        config = load_config(repo, Path(tmp) / "history.sqlite3")
        engine = MaintainabilityEngine(config=config)
        project = engine.scan([str(repo)], repo=str(repo))
        engine.close()
        return project.files


def top_dir(file: str, repo: Path) -> str:
    try:
        relative = Path(file).resolve().relative_to(repo.resolve())
    except ValueError:
        return "."
    return relative.parts[0] if len(relative.parts) > 1 else "."


def sample_files(
    files: list[FileScore], repo: Path, count: int, seed: int
) -> list[FileScore]:
    rng = random.Random(seed)
    by_grade: dict[str, list[FileScore]] = {grade: [] for grade in GRADES}
    for file in files:
        by_grade[file.grade].append(file)
    per_grade = max(1, count // len(GRADES))
    selected: list[FileScore] = []
    for grade in GRADES:
        candidates = by_grade[grade][:]
        rng.shuffle(candidates)
        by_directory: dict[str, list[FileScore]] = {}
        for file in candidates:
            by_directory.setdefault(top_dir(file.file, repo), []).append(file)
        directories = list(by_directory)
        rng.shuffle(directories)
        picked: list[FileScore] = []
        while len(picked) < per_grade and any(by_directory.values()):
            for directory in directories:
                if by_directory[directory] and len(picked) < per_grade:
                    picked.append(by_directory[directory].pop())
        selected.extend(picked)
    return selected


def write_labels(repo: Path, files: list[FileScore], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "repo": str(repo.resolve()),
        "grades": list(GRADES),
        "files": [
            {
                "path": str(Path(file.file).resolve().relative_to(repo.resolve())),
                "score": file.score,
                "grade": file.grade,
                "top_findings": [
                    {
                        "rule": finding.rule,
                        "line": finding.start_line,
                        "message": finding.message,
                    }
                    for finding in file.findings[:3]
                ],
                "label": None,
            }
            for file in files
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {path} with {len(files)} files.")
    print("Fill in each 'label' with one of:", ", ".join(GRADES))
    print("Then run: scripts/calibrate.py fit --repo", repo)


def load_labels(path: Path) -> list[tuple[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    labels = []
    for item in payload.get("files", []):
        label = item.get("label")
        if label in GRADES:
            labels.append((item["path"], label))
    return labels


def random_weights(base: dict[str, float], rng: random.Random) -> dict[str, float]:
    names = list(base)
    values = [max(1e-3, base[name] * rng.uniform(0.5, 1.5)) for name in names]
    total = sum(values)
    return {name: value / total for name, value in zip(names, values)}


def random_thresholds(
    base: dict[str, tuple[float, float]], rng: random.Random
) -> dict[str, tuple[float, float]]:
    result = {}
    for name, (good, bad) in base.items():
        factor = rng.uniform(0.75, 1.25)
        new_good = max(0.0, good * factor)
        new_bad = max(new_good + 1e-6, bad * factor)
        result[name] = (new_good, new_bad)
    return result


def accuracy(
    config: Config,
    labeled: list[tuple[FileScore, str]],
) -> float:
    engine = ScoringEngine(config)
    correct = sum(
        1
        for file, label in labeled
        if engine.score_file(file.file, file.metrics, file.findings).grade == label
    )
    return correct / len(labeled) if labeled else 0.0


def search(
    base: Config,
    labeled: list[tuple[FileScore, str]],
    iterations: int,
    seed: int,
    tune_thresholds: bool,
) -> tuple[dict[str, float], dict[str, tuple[float, float]], float]:
    rng = random.Random(seed)
    best_weights = dict(base.weights)
    best_thresholds = dict(base.thresholds)
    best_score = accuracy(base, labeled)
    for _ in range(iterations):
        weights = random_weights(base.weights, rng)
        thresholds = (
            random_thresholds(base.thresholds, rng)
            if tune_thresholds
            else base.thresholds
        )
        candidate = replace(base, weights=weights, thresholds=thresholds)
        score = accuracy(candidate, labeled)
        if score > best_score:
            best_score = score
            best_weights = weights
            best_thresholds = thresholds
    return best_weights, best_thresholds, best_score


def confusion(
    config: Config, labeled: list[tuple[FileScore, str]]
) -> dict[str, dict[str, int]]:
    engine = ScoringEngine(config)
    matrix = {label: {predicted: 0 for predicted in GRADES} for label in GRADES}
    for file, label in labeled:
        predicted = engine.score_file(
            file.file, file.metrics, file.findings
        ).grade
        matrix[label][predicted] += 1
    return matrix


def fit(
    repo: Path,
    labels_path: Path,
    output: Path,
    seed: int,
    iterations: int,
    tune_thresholds: bool,
) -> None:
    labels = load_labels(labels_path)
    if len(labels) < 5:
        raise SystemExit(
            f"Need at least 5 labelled files in {labels_path}; found {len(labels)}."
        )
    files = {str(Path(file.file).resolve()): file for file in scan(repo)}
    labeled = []
    for relative, label in labels:
        resolved = str((repo / relative).resolve())
        if resolved in files:
            labeled.append((files[resolved], label))
    if len(labeled) < 5:
        raise SystemExit("Could not match enough labelled files to the scan.")

    base = load_config(repo, Path(tempfile.gettempdir()) / "calibration.sqlite3")
    rng = random.Random(seed)
    shuffled = labeled[:]
    rng.shuffle(shuffled)
    folds = [shuffled[i::5] for i in range(5)]
    fold_scores = []
    for index in range(5):
        train = [
            item
            for fold_index, fold in enumerate(folds)
            if fold_index != index
            for item in fold
        ]
        test = folds[index]
        weights, thresholds, _ = search(
            base, train, max(100, iterations // 5), seed + index, tune_thresholds
        )
        candidate = replace(base, weights=weights, thresholds=thresholds)
        fold_scores.append(accuracy(candidate, test))
    print(
        "5-fold accuracy:",
        f"{sum(fold_scores) / len(fold_scores):.3f}",
        [round(score, 3) for score in fold_scores],
    )

    weights, thresholds, train_accuracy = search(
        base, labeled, iterations, seed, tune_thresholds
    )
    best = replace(base, weights=weights, thresholds=thresholds)
    print(f"Train accuracy: {train_accuracy:.3f}")
    print("Confusion matrix (rows = label, columns = predicted):")
    matrix = confusion(best, labeled)
    print("            " + " ".join(f"{grade[:5]:>6}" for grade in GRADES))
    for label in GRADES:
        row = " ".join(f"{matrix[label][grade]:>6}" for grade in GRADES)
        print(f"{label:<12}{row}")

    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "weights": {name: round(value, 4) for name, value in weights.items()},
        "thresholds": {
            name: [round(good, 4), round(bad, 4)]
            for name, (good, bad) in thresholds.items()
        },
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote candidate config to {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    sample = subparsers.add_parser("sample")
    sample.add_argument("--repo", type=Path, default=Path.cwd())
    sample.add_argument("--count", type=int, default=40)
    sample.add_argument("--seed", type=int, default=0)
    sample.add_argument(
        "--labels", type=Path, default=Path("calibration/labels.json")
    )

    fit_parser = subparsers.add_parser("fit")
    fit_parser.add_argument("--repo", type=Path, default=Path.cwd())
    fit_parser.add_argument(
        "--labels", type=Path, default=Path("calibration/labels.json")
    )
    fit_parser.add_argument(
        "--output",
        type=Path,
        default=Path("calibration/cpp-maintainability.json"),
    )
    fit_parser.add_argument("--seed", type=int, default=0)
    fit_parser.add_argument("--iterations", type=int, default=2000)
    fit_parser.add_argument("--tune-thresholds", action="store_true")

    args = parser.parse_args()
    repo = args.repo.resolve()
    if args.command == "sample":
        files = scan(repo)
        selected = sample_files(files, repo, args.count, args.seed)
        write_labels(repo, selected, args.labels)
    else:
        fit(
            repo,
            args.labels,
            args.output,
            args.seed,
            args.iterations,
            args.tune_thresholds,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
