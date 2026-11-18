"""Render a PDF report of automated test results, for non-technical readers.

The report combines a static introduction, written in Markdown, with the results
of one or more pytest runs, as recorded by the pytest-json-report plugin
(`pytest --json-report --json-report-file=<path>`). Test descriptions are the
docstrings of the test functions and section titles the docstrings of the test
modules; both are read from the test source files, which must therefore match the
code that produced the results.

Requires the `report` dependency group and the Pango system library, e.g.:

    uv run --group report python scripts/render_test_report.py \\
        --results unit.json integration.json e2e.json \\
        --release v1.2.0 \\
        --output test-report.pdf
"""

import argparse
import ast
import dataclasses
import datetime as dt
import json
import sys
from pathlib import Path

import jinja2
import markdown
import weasyprint

TEMPLATE_DIR = Path(__file__).parent / "test-report"
TEMPLATE_NAME = "report.j2.html"
DEFAULT_INTRO_PATH = TEMPLATE_DIR / "intro.md"

SUITE_UNIT = "Unit"
SUITE_INTEGRATION = "Integration"
SUITE_E2E = "End-to-end"
SUITE_ORDER = (SUITE_UNIT, SUITE_INTEGRATION, SUITE_E2E)

STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

# pytest-json-report outcomes which count as a failure of the test
FAILURE_OUTCOMES = ("failed", "error", "xpassed")
# pytest-json-report outcomes which count as a test that did not run
SKIP_OUTCOMES = ("skipped", "xfailed")

MAX_FAILURE_MESSAGE_LENGTH = 400


@dataclasses.dataclass
class TestCase:
    """Single execution of a test function, one per set of parameters."""

    parameters: str | None
    outcome: str
    message: str | None


@dataclasses.dataclass
class TestFunction:
    """Test function, with the results of all of its executions."""

    name: str
    suite: str
    description: str | None
    cases: list[TestCase] = dataclasses.field(default_factory=list)

    @property
    def status(self) -> str:
        outcomes = {case.outcome for case in self.cases}
        if outcomes & set(FAILURE_OUTCOMES):
            return STATUS_FAILED
        if outcomes <= set(SKIP_OUTCOMES):
            return STATUS_SKIPPED
        return STATUS_PASSED

    @property
    def num_passed_cases(self) -> int:
        return sum(1 for case in self.cases if case.outcome == "passed")

    @property
    def failed_cases(self) -> list[TestCase]:
        return [case for case in self.cases if case.outcome in FAILURE_OUTCOMES]

    @property
    def skipped_cases(self) -> list[TestCase]:
        return [case for case in self.cases if case.outcome in SKIP_OUTCOMES]


@dataclasses.dataclass
class TestModule:
    """Test module, rendered as one section of the report."""

    path: str
    title: str
    description: str | None
    functions: dict[str, TestFunction] = dataclasses.field(default_factory=dict)

    @property
    def anchor(self) -> str:
        return self.path.replace("/", "-").replace(".", "-")

    @property
    def suites(self) -> list[str]:
        suites = {function.suite for function in self.functions.values()}
        return [suite for suite in SUITE_ORDER if suite in suites]

    @property
    def status(self) -> str:
        statuses = {function.status for function in self.functions.values()}
        if STATUS_FAILED in statuses:
            return STATUS_FAILED
        if statuses == {STATUS_SKIPPED}:
            return STATUS_SKIPPED
        return STATUS_PASSED


@dataclasses.dataclass
class SuiteSummary:
    """Counts of test functions and executions of one test suite."""

    name: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    cases: int = 0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--results",
        nargs="+",
        required=True,
        type=Path,
        help="JSON files written by pytest-json-report, one per pytest run",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path of the PDF file to write",
    )
    parser.add_argument(
        "--intro",
        default=DEFAULT_INTRO_PATH,
        type=Path,
        help="Markdown file with the introduction of the report (default: %(default)s)",
    )
    parser.add_argument(
        "--source-root",
        default=Path.cwd(),
        type=Path,
        help=(
            "Directory against which the test paths of the results are resolved, "
            "usually the repository root (default: the current directory)"
        ),
    )
    parser.add_argument(
        "--release",
        help="Release identifier shown in the report, e.g. a git tag",
    )
    parser.add_argument(
        "--commit",
        help="Commit identifier shown in the report",
    )
    parser.add_argument(
        "--html-output",
        type=Path,
        help="Also write the intermediate HTML document to this path",
    )
    parser.add_argument(
        "--require-docstrings",
        action="store_true",
        help="Exit with an error, instead of a warning, if any test lacks a docstring",
    )
    return parser.parse_args()


def get_suite_name(keywords: list[str]) -> str:
    if "e2e" in keywords:
        return SUITE_E2E
    if "integration" in keywords:
        return SUITE_INTEGRATION
    return SUITE_UNIT


def get_case_message(test_result: dict) -> str | None:
    """Extract a one-paragraph explanation of a failed or skipped test execution.

    Failures are explained by the message of the exception that ended the failed
    stage (setup, call or teardown). Skips are explained by their reason, which
    pytest-json-report stores as the string representation of a
    `(path, line number, reason)` tuple.
    """
    for stage_name in ("setup", "call", "teardown"):
        stage = test_result.get(stage_name, {})
        outcome = stage.get("outcome")
        if outcome in ("failed", "error"):
            crash = stage.get("crash") or {}
            message = crash.get("message") or str(stage.get("longrepr", ""))
            message = message.strip().splitlines()[0] if message.strip() else ""
            return message[:MAX_FAILURE_MESSAGE_LENGTH] or None
        if outcome == "skipped":
            try:
                reason = ast.literal_eval(stage.get("longrepr", ""))[2]
            except (ValueError, SyntaxError, IndexError, TypeError):
                reason = str(stage.get("longrepr", ""))
            return reason.removeprefix("Skipped: ").strip() or None
    return None


def load_module_docstrings(
    source_path: Path,
) -> tuple[str | None, dict[str, str | None]]:
    """Read the docstrings of a test module and of its top-level functions.

    Returns a tuple with the docstring of the module and a mapping of function
    names to their docstrings. Docstrings are cleaned of indentation, as
    `inspect.cleandoc` does, and missing ones are `None`.
    """
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    function_docstrings = {
        node.name: ast.get_docstring(node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    return ast.get_docstring(tree), function_docstrings


def collect_test_modules(
    results_paths: list[Path], source_root: Path
) -> list[TestModule]:
    """Group the test results of all pytest runs by module and test function.

    Modules are ordered by path, which places the end-to-end tests, kept in their
    own directory, after the others. Test functions keep their order of
    execution.
    """
    modules: dict[str, TestModule] = {}
    docstrings: dict[str, tuple[str | None, dict[str, str | None]]] = {}
    for results_path in results_paths:
        results = json.loads(results_path.read_text(encoding="utf-8"))
        for test_result in results["tests"]:
            module_path, _, test_id = test_result["nodeid"].partition("::")
            function_name, _, parameters = test_id.partition("[")
            if module_path not in docstrings:
                docstrings[module_path] = load_module_docstrings(
                    source_root / module_path
                )
            module_docstring, function_docstrings = docstrings[module_path]
            if module_path not in modules:
                title, _, description = (module_docstring or "").partition("\n\n")
                modules[module_path] = TestModule(
                    path=module_path,
                    title=title.replace("\n", " ").strip()
                    or Path(module_path).stem,
                    description=description.strip() or None,
                )
            module = modules[module_path]
            if function_name not in module.functions:
                module.functions[function_name] = TestFunction(
                    name=function_name,
                    suite=get_suite_name(test_result.get("keywords", [])),
                    description=function_docstrings.get(function_name),
                )
            module.functions[function_name].cases.append(
                TestCase(
                    parameters=parameters.removesuffix("]") or None,
                    outcome=test_result["outcome"],
                    message=get_case_message(test_result)
                    if test_result["outcome"] != "passed"
                    else None,
                )
            )
    return [modules[path] for path in sorted(modules)]


def summarize_suites(modules: list[TestModule]) -> list[SuiteSummary]:
    """Count passed, failed and skipped test functions of each suite.

    Returns one summary per suite with at least one test, in the order of
    `SUITE_ORDER`, followed by a summary of all suites named `Total`.
    """
    summaries = {name: SuiteSummary(name=name) for name in SUITE_ORDER}
    total = SuiteSummary(name="Total")
    for module in modules:
        for function in module.functions.values():
            for summary in (summaries[function.suite], total):
                summary.cases += len(function.cases)
                match function.status:
                    case "passed":
                        summary.passed += 1
                    case "failed":
                        summary.failed += 1
                    case _:
                        summary.skipped += 1
    return [summary for summary in summaries.values() if summary.total > 0] + [total]


def main() -> int:
    args = parse_arguments()
    modules = collect_test_modules(args.results, args.source_root)
    if not modules:
        print("The results files contain no tests.", file=sys.stderr)
        return 1
    undocumented = [
        f"{module.path}::{function.name}"
        for module in modules
        for function in module.functions.values()
        if not function.description
    ]
    for test_name in undocumented:
        print(f"Missing docstring: {test_name}", file=sys.stderr)
    if undocumented and args.require_docstrings:
        print(f"{len(undocumented)} tests lack a docstring.", file=sys.stderr)
        return 1
    run_timestamps = [
        json.loads(path.read_text(encoding="utf-8"))["created"]
        for path in args.results
    ]
    environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
    )
    html = environment.get_template(TEMPLATE_NAME).render(
        intro=markdown.markdown(
            args.intro.read_text(encoding="utf-8"), extensions=["extra"]
        ),
        modules=modules,
        summaries=summarize_suites(modules),
        release=args.release,
        commit=args.commit,
        generated_at=dt.datetime.now(dt.UTC),
        run_at=dt.datetime.fromtimestamp(max(run_timestamps), dt.UTC),
    )
    if args.html_output:
        args.html_output.write_text(html, encoding="utf-8")
    weasyprint.HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf(args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
