# Perf Benchmarks (9.1)

This folder documents the *fixed*, reproducible benchmark datasets used to measure and track performance across refactors.

## Datasets (write-once, reproducible)

All datasets are generated via `tools.generate_benchmark_project` and contain **synthetic** text only.

- **small**: ~50 novel documents, total正文 ~50k chars
  - Spec (current generator): `acts=1`, `chapters_per_act=5`, `scenes_per_chapter=9`, `total_chars=50_000` (≈51 novel docs)
  - Command: `py -3.11 -m tools.generate_benchmark_project --size small --out tests/fixtures/projects/small`

- **medium**: ~300 novel documents, total正文 ~300k chars
  - Spec (current generator): `acts=2`, `chapters_per_act=10`, `scenes_per_chapter=14`, `total_chars=300_000` (≈302 novel docs)
  - Command: `py -3.11 -m tools.generate_benchmark_project --size medium --out tests/fixtures/projects/medium`

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
