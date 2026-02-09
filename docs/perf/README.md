# Perf Benchmarks (9.1)

This folder documents the *fixed*, reproducible benchmark datasets used to measure and track performance across refactors.

## Datasets (write-once, reproducible)

All datasets are generated via the repo-root `tools/` package (`tools.generate_benchmark_project`) and contain **synthetic** text only.
Recommended invocation: `python -m tools.generate_benchmark_project ...`
Generation is fixed at the command level; use the commands below to reproduce the fixtures.

- **small**: ~50 novel documents, total正文 ~50k chars
  - Spec (current generator): `acts=1`, `chapters_per_act=5`, `scenes_per_chapter=9`, `total_chars=50_000` (≈51 novel docs)
  - Command: `python -m tools.generate_benchmark_project --size small --out tests/fixtures/projects/small`

- **medium**: ~300 novel documents, total正文 ~300k chars
  - Spec (current generator): `acts=2`, `chapters_per_act=10`, `scenes_per_chapter=14`, `total_chars=300_000` (≈302 novel docs)
  - Command: `python -m tools.generate_benchmark_project --size medium --out tests/fixtures/projects/medium`

- **large**: ~1000 novel documents, total正文 ~1.5M chars
  - Spec (current generator): `acts=4`, `chapters_per_act=25`, `scenes_per_chapter=9`, `total_chars=1_500_000` (≈1004 novel docs)
  - Command: `py -3.11 -m tools.generate_benchmark_project --size large --out tests/fixtures/projects/large`

## Output constraints
- Output must be a **valid project directory** (contains at least `project.db`).
- Must not contain any real user content; generated text is synthetic.

## Metrics (measured per dataset)
- **cold_start**: process start → main window `show()` completed
- **open_project**: open project action → project tree + editor becomes interactive
- **outline_refresh**: trigger outline refresh → refresh completed
- **ai_completion_mock**: trigger completion → UI renders a suggestion (ghost/inline/popup)

### Metric definitions
**cold_start**
- Start: enter `main()` (see `src/main.py`)
- End: after `main_window.show()` returns (see `src/main.py`)
- Unit: seconds (wall-clock, monotonic timer preferred)

**open_project**
- Start: enter `ProjectController.on_open_project()` (see `src/gui/controllers/project_controller.py`)
- End: after `project_structure_changed.emit()` and the project tree + editor accept input (see `src/gui/controllers/project_controller.py`)
- Unit: seconds (wall-clock, monotonic timer preferred)

**outline_refresh**
- Start: enter the outline refresh entrypoint (see `src/gui/panels/outline_panel.py`)
- End: after outline model/view updates are applied (see `src/gui/panels/outline_panel.py`)
- Unit: seconds (wall-clock, monotonic timer preferred)

**ai_completion_mock**
- Start: enter the completion trigger (see `src/gui/editor/smart_completion_manager.py`)
- End: after a suggestion is rendered (ghost/inline/popup) (see `src/gui/editor/smart_completion_manager.py`)
- Unit: seconds (wall-clock, monotonic timer preferred)

## UI freeze monitoring (tick jitter)
- Measure UI "freeze" via a 60Hz `QTimer` and record tick-to-tick interval jitter.
- Record: maximum tick interval (milliseconds).
- Budget (idle/light interaction): maximum tick interval ≤ 120ms.
- Heavy operations (index/import/rebuild) may exceed 120ms, but must show progress + be cancellable, and must be logged.

## Budgets (default targets)
Budgets are fixed targets: record baseline first, then iteratively compress.

- cold_start: small ≤ 2.0s; medium ≤ 3.5s; large ≤ 6.0s
- open_project: small ≤ 1.0s; medium ≤ 2.5s; large ≤ 5.0s
- outline_refresh: small ≤ 150ms; medium ≤ 400ms; large ≤ 900ms
- ai_completion_mock: small/medium/large ≤ 800ms

## Recording (fixed)
- Runtime perf log (JSON lines): `~/.ai-novel-editor/logs/perf.log`
- Repo-tracked baselines: `docs/perf/baseline.json` + `docs/perf/current.json` (aggregated stats + machine summary only; no user text)
