# Issue CSV Rules

This repo uses Issue CSV as the execution contract for each plan.

## Required columns
All columns are required and must be populated:
- ID: unique issue ID (e.g. A1, A2, or project-prefixed like LMEM-010)
- Title: short title
- Description: scope/boundary
- Acceptance: done criteria
- Test_Method: how to verify (tool, command, or manual)
- Tools: MCP/tool to use (or "manual"/"none"); use `docs/mcp-tools.md` for valid `server:tool` names
- Dev_Status: TODO | DOING | DONE
- Review1_Status: TODO | DOING | DONE
- Regression_Status: TODO | DOING | DONE
- Files: paths or scope (use a sentinel if none)
- Dependencies: other IDs or external deps (use "none" if none)
- Notes: extra context (use "none" if none)

## Sentinel values
Use these when a field is required but not applicable:
- Files: N/A | external | TBD | module:<name> | <glob>
- Dependencies: none
- Notes: none
- Tools: manual | none

## Test_Method guidance
Every issue must specify how it will be verified. Use the narrowest reliable method:
- Unit / Integration: prefer if a test harness exists and the change is logic-heavy.
- API / Contract: for backend or service changes (e.g., curl, Postman, AUTOCURL).
- UI / E2E: for frontend flows (e.g., Playwright or Chrome DevTools MCP).
- Manual: only if automation is impractical; include the exact steps.

Review status meanings:
- Review1_Status: verification after the issue is implemented.
- Regression_Status: verification after all issues are complete (full pass/smoke).
Only mark Review1/Regression as DONE after the declared Test_Method runs and passes, or if manual/not feasible is explicitly recorded with risk noted.

## CSV formatting
- If a field contains commas, wrap the field in double quotes.
- Use "|" inside a field to list multiple values.

## Example row
ID,Title,Description,Acceptance,Test_Method,Tools,Dev_Status,Review1_Status,Regression_Status,Files,Dependencies,Notes
A1,Login error handling,"Handle invalid token in /auth/login","Returns 401 + error code","AUTOCURL mock token",AUTOCURL,TODO,TODO,TODO,"src/auth/login.ts | src/auth/token.ts",none,none
