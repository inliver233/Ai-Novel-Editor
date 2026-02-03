# Agent Skills Standard (Codex CLI + Claude Code)

Last reviewed: 2025-12-21

This is the repo source of truth for how we **structure, write, and package `SKILL.md` “Agent Skills”** so they work well across:
- **OpenAI Codex** (Codex CLI / IDE extensions)
- **Anthropic Claude Code** (Claude Code CLI)

This doc covers:
- The portable `SKILL.md` contract (YAML + operational body)
- Artifact organization (`scripts/`, `references/`, `assets/`)
- “Progressive disclosure” (what gets loaded when)
- Practical, production-grade examples (real upstream Skills) and what we should copy as patterns (not necessarily as code)

---

## What is a Skill?

A **Skill** is a small, filesystem-based bundle:
- A required `SKILL.md` (YAML frontmatter + Markdown instructions)
- Optional supporting files (scripts, references, templates/assets)

Skills are meant to be **discoverable** and **load on-demand**.

### Progressive disclosure (portable mental model)

Think in “levels” of what the agent loads:

1) **Level 1 — Metadata (always loaded)**
   - YAML frontmatter fields like `name` and `description`
   - Used for discovery: *what the skill does* + *when to use it*

2) **Level 2 — Instructions (loaded when triggered/invoked)**
   - The Markdown body of `SKILL.md`
   - Contains the real workflow, checklists, and guardrails

3) **Level 3 — Resources & code (loaded as needed)**
   - Additional markdown, templates, examples, schemas, etc.
   - Executable scripts that the agent runs for deterministic behavior

Practical takeaway: **don’t stuff everything into `SKILL.md`**. Keep it sharp; push long/rarely-needed content into separate files.

---

## Canonical artifact layout (recommended)

There’s nothing “magic” about the folder names beyond conventions; both Codex and Claude Code primarily care that `SKILL.md` exists.

Recommended layout (portable):

```text
my-skill/
  SKILL.md                # required
  scripts/                # optional: executable helpers (deterministic, black-box)
  references/             # optional: longer docs / checklists / specs
  assets/                 # optional: templates, examples, fixtures
```

Key idea: **operational instructions** go in `SKILL.md`; **determinism** goes in `scripts/`; **depth** goes in `references/`; **reusability** goes in `assets/`.

---

## Patterns from production-grade upstream Skills (annotated)

These are concrete examples of Skills that ship with real artifacts and “run it” workflows. Use these as *patterns* when authoring our own.

### Example A — “Black-box helper script” pattern (Claude Code: `webapp-testing`)

Upstream repo: `anthropics/skills`

Key artifact layout:

```text
skills/webapp-testing/
  SKILL.md
  scripts/
    with_server.py
  examples/
    console_logging.py
    element_discovery.py
    static_html_automation.py
```

Core pattern:
- `SKILL.md` stays short and operational.
- A “big” helper lives in `scripts/` and is treated as a black box (run `--help` first; don’t ingest source unless necessary).
- `examples/` provides runnable “recipes” that are easy to adapt without rewriting the workflow.

#### What the `SKILL.md` emphasizes (verbatim excerpt)

```md
**Always run scripts with `--help` first** to see usage. DO NOT read the source until you try running the script first...
These scripts can be very large and thus pollute your context window.
They exist to be called directly as black-box scripts rather than ingested into your context window.
```

#### What `scripts/with_server.py` does (key behavior)

The helper script:
- Starts one or more servers (`--server` repeated)
- Waits for ports to become ready (`--port` repeated)
- Runs a test/automation command
- Ensures processes are terminated (cleanup in `finally`)

Selected excerpt (verbatim):

```py
parser.add_argument('--server', action='append', dest='servers', required=True, help='Server command (can be repeated)')
parser.add_argument('--port', action='append', dest='ports', type=int, required=True, help='Port for each server (must match --server count)')
...
process = subprocess.Popen(server['cmd'], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
...
result = subprocess.run(args.command)
...
process.terminate()
```

This “black-box helper + examples” pattern is ideal for:
- E2E test harnesses
- Local integration test harnesses
- UI testing via Playwright/Cypress

---

### Example B — “Cloud training + pre-baked scripts” pattern (HF: `model-trainer`)

Upstream repo: `huggingface/skills`

Key artifact layout:

```text
hf-llm-trainer/skills/model-trainer/
  SKILL.md
  scripts/
    convert_to_gguf.py
    dataset_inspector.py
    estimate_cost.py
    train_dpo_example.py
    train_grpo_example.py
    train_sft_example.py
  references/
    gguf_conversion.md
    hardware_guide.md
    hub_saving.md
    reliability_principles.md
    trackio_guide.md
    training_methods.md
    training_patterns.md
    troubleshooting.md
```

Core pattern:
- `SKILL.md` is the **policy + runtime contract** (what tool to use, what NOT to do, guardrails, async behavior).
- `scripts/` contains **ready-to-submit** training scripts (PEP 723 “UV script” style) and utilities (cost estimate, dataset inspection, conversion).
- `references/` keeps “deep” details that should not clutter the main skill instructions.

#### “Job config” vs “training config”: how this skill configures training

This upstream skill splits configuration across two layers:

1) **Job submission config** (in the MCP call):
   - `flavor`, `timeout`, `secrets`, and the **training script** content (inline string or URL)
2) **Trainer config** (inside the training script):
   - TRL config objects: `SFTConfig`, `DPOConfig`, `GRPOConfig` (output_dir, hub push settings, hyperparams, evaluation, reporting)

This is a good portable pattern: the job runner is “outer config”; the trainer is “inner config”.

#### Why “local file paths” don’t work (important operational rule)

The upstream `SKILL.md` explicitly says local paths won’t work because Jobs run in isolated containers without access to your filesystem; scripts must be inline or URL-addressable.

This pattern generalizes to many “remote execution” contexts:
- CI runners
- remote build services
- cloud sandboxes

#### What a “production-ready” training script looks like (`train_dpo_example.py`)

It uses PEP 723 header dependencies + a compact “trainer config” block.

Selected excerpt (verbatim):

```py
config = DPOConfig(
    output_dir="qwen-dpo-aligned",
    push_to_hub=True,
    hub_model_id="username/qwen-dpo-aligned",
    hub_strategy="every_save",
    beta=0.1,
    num_train_epochs=1,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=5e-7,
    eval_strategy="steps",
    eval_steps=100,
    report_to="trackio",
)
```

If you are designing your own training skill, this block is your “training_config” (even though it’s Python, not YAML).

---

### Example C — “Conversion pipeline helper” pattern (HF: `convert_to_gguf.py`)

Upstream file: `hf-llm-trainer/skills/model-trainer/scripts/convert_to_gguf.py`

Core pattern:
- Provide a single-entry script that:
  1) loads models,
  2) merges adapters,
  3) installs/initializes conversion tools,
  4) generates artifacts,
  5) uploads outputs + a README
- Configure via **environment variables** (simple, works in ephemeral job containers)

#### What the script expects (environment config)

Selected excerpt (verbatim):

```py
ADAPTER_MODEL = os.environ.get("ADAPTER_MODEL", "evalstate/qwen-capybara-medium")
BASE_MODEL = os.environ.get("BASE_MODEL", "Qwen/Qwen2.5-0.5B")
OUTPUT_REPO = os.environ.get("OUTPUT_REPO", "evalstate/qwen-capybara-medium-gguf")
```

#### What the script actually does (operational steps)

The script implements a complete GGUF build pipeline:
- Loads base model
- Loads LoRA adapter and merges (`merge_and_unload`)
- Saves merged model to `/tmp/merged_model`
- Installs build tools (`apt-get install build-essential cmake`)
- Clones llama.cpp and uses its conversion script to create `*-f16.gguf`
- Builds `llama-quantize` and generates quantizations
- Uploads GGUFs and generates a README in the target repo

Important: this is “production-grade” because it is end-to-end and self-contained, but it is also **high-impact**:
- It runs package installs (`apt-get`, `pip`) and clones repos.
- It assumes a Debian-like environment (apt) and network access.

When we create similar “pipeline” skills, we should include explicit safety notes: environment assumptions, compute cost, and where outputs go.

---

## Unit-testing Skills: production patterns (what artifacts to include)

Unit-testing skills are usually less about clever prompting and more about **reliable execution + stable outputs**.

Recommended artifact set for a unit-testing skill:

```text
my-unit-testing-skill/
  SKILL.md
  scripts/
    run_unit_tests.sh          # one command interface; repo-specific detection inside
    collect_coverage.sh        # optional
  assets/
    test_plan_template.md      # what to test / what to ignore / acceptance criteria
    test_matrix_template.csv   # platforms x versions x suites
  references/
    testing-policy.md          # can link to repo docs instead of copying
```

Design rules (hard-earned in production):
- **One stable entrypoint**: `scripts/run_unit_tests.*` should be the only thing the agent has to remember.
- **Machine-readable output**: if possible, emit JUnit XML and/or coverage JSON so automation can consume it.
- **No guessing**: detect language/package manager (pytest/jest/go test/cargo test) explicitly; fail loudly if unknown.
- **Tight loop**: rerun the narrowest target first (single file / suite / failed tests), then broaden.

---

## Repo conventions (this repository)

These conventions are the default for **team-shared** Skills in this repo.

### Skill roots (checked into git)

- **Codex**: `.codex/skills/<skill-name>/SKILL.md`
- **Claude Code**: `.claude/skills/<skill-name>/SKILL.md`

If a Skill is intended to work in both tools, keep the Skill content aligned across both roots. Prefer keeping differences limited to tool-specific frontmatter fields (e.g., `metadata.short-description` vs `allowed-tools`).

### Naming

- Use `kebab-case` for `name`, keep ≤ 64 chars.
- Prefix repo Skills with `ad-` (agent-designer), e.g. `ad-plan`, `ad-issue-csv`, to reduce collisions with user/global Skills.

### What belongs in-repo vs personal

- **Repo Skills**: stable, reusable team workflows that should behave consistently for everyone cloning the repo.
- **Personal Skills**: individual preferences and experiments (Codex: `~/.codex/skills/`, Claude Code: `~/.claude/skills/`).

### Add a new Skill (checklist)

1. Create the Skill directory under the appropriate root(s).
2. Write `SKILL.md` with valid YAML frontmatter (`name`, `description`) and an operational body (workflow + verification).
3. Add deterministic helpers in `scripts/` and put long docs in `references/`/`assets/`.
4. Sanity-check:
   - the `name` is unique (at least within this repo)
   - the `description` includes clear trigger keywords/filetypes
   - scripts are safe-by-default and don’t require global installs

### Related repo patterns

- **Codex prompt snippets** (explicit user-invoked): `.codex/prompts/*.md`
- **Claude Code explicit workflows** (user-invoked): `.claude/commands/*.md` (slash commands)

---

## `SKILL.md` format (portable contract)

### Required YAML frontmatter

Minimum:

```yaml
---
name: my-skill-name
description: What it does. Use when <triggers / keywords / scenarios>.
---
```

### Naming rules (choose the strict subset for portability)

To avoid “works in one tool but not the other”, follow the stricter constraints:
- `name`: lowercase letters, numbers, hyphens only; keep ≤ 64 chars
- `description`: single paragraph; include both **what** + **when**; keep it short and keyword-rich

### Optional tool-specific frontmatter (use sparingly)

**Codex (optional UI hint):**

```yaml
metadata:
  short-description: Optional user-facing label
```

**Claude Code (optional tool restriction):**

```yaml
allowed-tools: Read, Grep, Glob
```

Notes:
- `allowed-tools` is Claude Code–specific.
- If you don’t specify `allowed-tools`, Claude Code follows its normal permission model.

---

## Authoring `SKILL.md` (best practices)

### 1) Make the description “selectable”

The description is the *primary trigger surface* for both tools. Write it like a search query:
- Include the artifact types: `pdf`, `xlsx`, `OpenAPI`, `terraform`, `kubernetes`, etc.
- Include the user’s likely phrasing: “review PR”, “debug flaky test”, “migrate schema”, …
- Include the boundary: “use when …”, “do not use when …”

Bad:
```yaml
description: Helps with data
```

Good:
```yaml
description: Analyze Excel .xlsx exports and generate summaries/charts. Use when working with spreadsheets, pivot tables, or CSV/XLSX files.
```

### 2) Keep `SKILL.md` body operational

Prefer sections like:
- **When to use / When not to use**
- **Inputs / Outputs**
- **Workflow**
- **Verification**
- **Safety & guardrails**
- **References**

Write steps so the agent can follow them without improvising:
- Use explicit commands where appropriate
- Include stop conditions and success criteria
- Don’t hide critical behavior in vague prose

### 3) Use scripts for determinism

If a workflow benefits from “always do X the same way”, put it in `scripts/` and reference it from `SKILL.md`.
Good scripts:
- Are idempotent when possible
- Fail loudly and explain required inputs
- Avoid global installs or modifying user-wide state unless explicitly intended

### 4) Put long docs in `references/`

Put detailed checklists, style guides, schemas, and “deep” docs in separate files.
In `SKILL.md`, link them explicitly and tell the agent *when to open them*.

### 5) Include verification

Every Skill should state how to verify it worked:
- The narrowest test/command that proves correctness
- How to inspect outputs (paths, logs, expected diff shape)

---

## Codex vs Claude Code: non-trivial differences

### Invocation model

- **Codex**: supports both
  - **explicit** invocation (e.g., `/skills` picker or `$skill-name`)
  - **implicit** selection (Codex chooses a matching skill based on `description`)

- **Claude Code**: Skills are **model-invoked** (Claude decides when to use them based on `description`)
  - For explicit, user-triggered workflows, Claude Code uses **slash commands** (custom prompts in `.claude/commands/`).

### Skill locations & precedence

- **Codex** supports multiple scopes and precedence (repo/user/admin/system). A higher-precedence skill with the same `name` overrides lower-precedence ones.
- **Claude Code** discovers skills from:
  - personal `~/.claude/skills/`
  - project `.claude/skills/`
  - plugin-bundled skills

### Tool permissions

- **Claude Code** supports `allowed-tools` in Skill frontmatter to restrict tool use while a Skill is active.
- **Codex** relies primarily on sandboxing + approvals (per-session / per-command policies). Don’t assume a Codex-equivalent `allowed-tools` exists unless you’ve verified it for your Codex version.

---

## Portable `SKILL.md` template

```markdown
---
name: my-skill-name
description: <What it does>. Use when <specific triggers / keywords / filetypes>.

# Codex (optional)
# metadata:
#   short-description: <Short label>

# Claude Code (optional)
# allowed-tools: Read, Grep, Glob
---

# <Human-readable Skill Title>

## When to use
- …

## When not to use
- …

## Inputs
- …

## Outputs
- …

## Workflow
1) …
2) …

## Verification
- …

## Safety & guardrails
- …

## References
- [REFERENCE.md](references/REFERENCE.md)
- [Template](assets/template.md)
```

---

## Source references (reviewed 2025-12-21)

### Standards / primary docs

- OpenAI Codex “Agent Skills”: https://developers.openai.com/codex/skills
- Codex open-source “Skills (experimental)”: https://github.com/openai/codex/blob/main/docs/skills.md
- Agent Skills specification: https://agentskills.io/specification
- Claude Code “Agent Skills”: https://code.claude.com/docs/en/skills
- Claude Code “Slash commands” (incl. “Skills vs slash commands”): https://code.claude.com/docs/en/slash-commands
- Claude Docs “Agent Skills” overview (progressive disclosure levels): https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview

### Upstream examples referenced above

- Claude Code upstream skill (`webapp-testing`):
  - https://raw.githubusercontent.com/anthropics/skills/main/skills/webapp-testing/SKILL.md
  - https://raw.githubusercontent.com/anthropics/skills/main/skills/webapp-testing/scripts/with_server.py
- HF upstream skill (`model-trainer`):
  - https://raw.githubusercontent.com/huggingface/skills/main/hf-llm-trainer/skills/model-trainer/SKILL.md
  - https://raw.githubusercontent.com/huggingface/skills/main/hf-llm-trainer/skills/model-trainer/scripts/train_dpo_example.py
  - https://raw.githubusercontent.com/huggingface/skills/main/hf-llm-trainer/skills/model-trainer/scripts/train_grpo_example.py
  - https://raw.githubusercontent.com/huggingface/skills/main/hf-llm-trainer/skills/model-trainer/scripts/convert_to_gguf.py
