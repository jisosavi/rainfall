#!/usr/bin/env python3
"""Check that README.md, roadmap.md and roadmap-implemented.md match the code.

Run from anywhere before pushing:

    python3 scripts/check_docs.py

Standard library only: it reads the source files as text and never imports the app, so it
works without the backend's packages installed. Exit code 1 if any check FAILs; WARNs are
reported but don't fail. Use --strict to fail on warnings too.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
DOCS = ["README.md", "roadmap.md", "roadmap-implemented.md"]

# Commits whose title starts like this are docs-only and needn't appear in the implemented log.
DOCS_ONLY_PREFIXES = ("README", "Roadmap", "roadmap", "Docs", "docs")


class Report:
    def __init__(self) -> None:
        self.failures = 0
        self.warnings = 0

    def section(self, title: str) -> None:
        print(f"\n{title}")

    def ok(self, message: str) -> None:
        print(f"  ok    {message}")

    def warn(self, message: str) -> None:
        self.warnings += 1
        print(f"  WARN  {message}")

    def fail(self, message: str) -> None:
        self.failures += 1
        print(f"  FAIL  {message}")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return ""


def check_env_vars(report: Report, readme: str) -> None:
    report.section("Environment variables (backend/app/config.py)")
    config = read(BACKEND / "app/config.py")
    example = read(BACKEND / ".env.example")
    names = re.findall(r'alias="([A-Z0-9_]+)"', config)
    for name in names:
        if f"`{name}`" not in readme:
            report.fail(f"{name} is a setting but missing from the README variables table")
        elif name not in example:
            report.warn(f"{name} is documented in the README but missing from backend/.env.example")
        else:
            report.ok(name)
    for name in set(re.findall(r"^\| `([A-Z][A-Z0-9_]+)` \|", readme, re.M)) - set(names):
        report.fail(f"README documents {name}, which no longer exists in config.py")


def check_routes(report: Report, readme: str) -> None:
    report.section("API endpoints (backend/app/api/routes)")
    for path in sorted((BACKEND / "app/api/routes").glob("*.py")):
        source = read(path)
        prefix_match = re.search(r'APIRouter\([^)]*prefix="([^"]*)"', source)
        prefix = prefix_match.group(1) if prefix_match else ""
        for method, route in re.findall(r'@router\.(get|post|put|delete)\("([^"]*)"', source):
            endpoint = f"{method.upper()} {prefix}{route}"
            # Path parameter names needn't match ({id} vs {station_id}); the README may add a
            # query string, e.g. `GET /api/stations?date=`.
            pattern = re.escape(endpoint).replace(r"\{", "{").replace(r"\}", "}")
            pattern = re.sub(r"\{[^}]*\}", r"\{[^}]+\}", pattern)
            if re.search(pattern + r"(\?|`)", readme):
                report.ok(endpoint)
            else:
                report.fail(f"{endpoint} ({path.name}) is missing from the README API table")


def check_migrations(report: Report, readme: str, implemented: str) -> None:
    report.section("Database migrations (backend/migrations/versions)")
    texts = readme + implemented
    for path in sorted((BACKEND / "migrations/versions").glob("[0-9][0-9][0-9][0-9]_*.py")):
        number = path.name[:4]
        if number == "0001":
            report.ok(f"{number} (initial schema)")
        elif re.search(rf"\b{number}\b", texts):
            report.ok(f"{number} {path.stem[5:]}")
        else:
            report.fail(f"migration {number} ({path.name}) isn't mentioned in README.md or roadmap-implemented.md")


def check_sources(report: Report, readme: str) -> None:
    report.section("Data sources (ingestion modules, README, About popup)")
    main = read(BACKEND / "app/ingest/__main__.py")
    match = re.search(r"ALL_SOURCES\s*=\s*\[([^\]]*)\]", main)
    sources = re.findall(r'"(\w+)"', match.group(1)) if match else []
    if not sources:
        report.fail("couldn't find ALL_SOURCES in backend/app/ingest/__main__.py")
    strings = read(FRONTEND / "src/strings.ts")
    about_sources = set(re.findall(r"source:\s*'(\w+)'", strings))
    headings = {"fmi": "FMI", "met": "MET Norway", "smhi": "SMHI", "dmi": "DMI"}
    for source in sources:
        problems = []
        if not (BACKEND / f"app/ingest/{source}.py").exists():
            problems.append(f"no backend/app/ingest/{source}.py")
        if f"### {headings.get(source, source.upper())}" not in readme:
            problems.append("no README data-conventions section")
        if source not in about_sources:
            problems.append("no row in the About popup data table (frontend/src/strings.ts)")
        if problems:
            report.fail(f"{source}: " + "; ".join(problems))
        else:
            report.ok(source)
    for source in about_sources - set(sources):
        report.fail(f"About popup lists '{source}', which isn't an ingestion source")


def check_cli(report: Report, readme: str) -> None:
    report.section("Ingestion command options (python -m app.ingest)")
    main = read(BACKEND / "app/ingest/__main__.py")
    for option in re.findall(r'add_argument\("(--[a-z-]+)"', main):
        if option in readme:
            report.ok(option)
        else:
            report.fail(f"{option} isn't mentioned in the README")


def check_schedule(report: Report, readme: str) -> None:
    report.section("Cron schedule (README vs About popup)")
    about = read(FRONTEND / "src/components/AboutDialog.vue")
    runs = re.findall(r"\[(\d+),\s*(\d+)\]", about.split("RUNS_UTC", 1)[1].split("]\n", 1)[0] + "]") if "RUNS_UTC" in about else []
    if not runs:
        report.fail("couldn't find RUNS_UTC in AboutDialog.vue")
        return
    minutes = {m for _, m in runs}
    hours = ",".join(h for h, _ in runs)
    expected = f"{minutes.pop() if len(minutes) == 1 else '?'} {hours} * * *"
    if f"`{expected}`" in readme:
        report.ok(f"About popup times match the README schedule `{expected}`")
    else:
        report.fail(f"About popup says `{expected}` (RUNS_UTC), but the README doesn't document that schedule")


def check_implemented_log(report: Report, implemented: str) -> None:
    report.section("Implemented log (roadmap-implemented.md vs git history)")
    titles = [t.strip() for t in git("log", "--format=%s").splitlines() if t.strip()]
    if not titles:
        report.warn("couldn't read git history; skipped")
        return
    # The last column holds commit title(s); several are separated by ";".
    cells = re.findall(r"^\|[^|]*\|[^|]*\|\s*([^|]+?)\s*\|\s*$", implemented, re.M)
    referenced = {ref.strip() for cell in cells for ref in cell.split(";")} - {"Commit", "—", "---", ""}
    for ref in sorted(referenced):
        if any(t.startswith(ref) for t in titles):
            report.ok(f"'{ref}'")
        else:
            report.fail(f"'{ref}' is referenced but no commit title starts like that")
    # Recent feature commits (the last 10) should be in the log.
    for title in titles[:10]:
        if title.startswith(DOCS_ONLY_PREFIXES):
            continue
        if not any(title.startswith(ref) for ref in referenced):
            report.warn(f"recent commit '{title}' isn't referenced in roadmap-implemented.md")


def check_roadmap(report: Report, roadmap: str) -> None:
    report.section("Roadmap (roadmap.md)")
    done = re.findall(r"^\s*- \[x\] (.+)$", roadmap, re.M | re.I)
    for item in done:
        report.warn(f"finished item still in roadmap.md, move it to roadmap-implemented.md: {item[:70]}")
    if not done:
        report.ok("no finished items left in roadmap.md")


def check_links(report: Report) -> None:
    report.section("Relative links in Markdown files")
    bad = 0
    for name in DOCS:
        text = read(ROOT / name)
        for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text):
            if re.match(r"^[a-z]+:", target):  # http:, https:, mailto:
                continue
            if not (ROOT / target).exists():
                report.fail(f"{name} links to {target}, which doesn't exist")
                bad += 1
    if not bad:
        report.ok("all relative links resolve")


def check_worktree(report: Report) -> None:
    report.section("Working tree")
    status = git("status", "--porcelain")
    if status.strip():
        count = len(status.strip().splitlines())
        report.warn(f"{count} uncommitted change(s): they won't be pushed")
    else:
        report.ok("clean")
    ahead = git("rev-list", "--count", "@{u}..HEAD").strip()
    if ahead and ahead != "0":
        report.ok(f"{ahead} local commit(s) ready to push")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = parser.parse_args()

    readme = read(ROOT / "README.md")
    implemented = read(ROOT / "roadmap-implemented.md")
    roadmap = read(ROOT / "roadmap.md")
    report = Report()

    check_env_vars(report, readme)
    check_routes(report, readme)
    check_migrations(report, readme, implemented)
    check_sources(report, readme)
    check_cli(report, readme)
    check_schedule(report, readme)
    check_implemented_log(report, implemented)
    check_roadmap(report, roadmap)
    check_links(report)
    check_worktree(report)

    print(f"\n{report.failures} failure(s), {report.warnings} warning(s)")
    return 1 if report.failures or (args.strict and report.warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
