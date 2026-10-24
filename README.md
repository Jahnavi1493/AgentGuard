# AgentGuard

AgentGuard is a small policy-enforcement layer that sits between an AI agent and its tools. It validates each proposed tool call, applies a simple JSON policy, writes an append-only audit trail, and blocks or pauses unsafe actions before they can run. The project is intentionally small and readable so first-year students can understand every file and explain the enforcement logic without needing advanced infrastructure.

## FLAGGED vs DENIED vs PREVENTED

This project distinguishes between three ideas:

- FLAGGED: the system notices a suspicious action and reports it.
- DENIED: the request is rejected, but the tool may still have been reachable in a different design.
- PREVENTED: a raw tool is never called because the agent can only reach it through the guardrail layer.

Only PREVENTED protects in the security sense, and that is what the tests check.

## Setup

```bash
pip install -r requirements.txt
```

## Commands

```bash
make test
make eval
make dashboard
```

## Verified results

The following commands were run from the repo root and passed with fresh evidence:

```bash
$ python3 -m pytest -q
28 passed in 0.62s
```

```bash
$ python3 runner.py --mode protected --auto-review deny
Protected mode: decision_accuracy=1.0
Protected mode: block_enforcement_violations=0
Protected mode: review_total=3
```

```bash
$ python3 runner.py --mode unprotected
Unprotected mode: would_have_been_blocked_but_ran=3
Unprotected mode: would_have_needed_review_but_ran=3
Unprotected mode: out_of_policy_executions=6
```

```bash
$ python3 -m streamlit run dashboard.py --server.headless true --server.port 8502
HTTP/1.1 200 OK
```

## Final checklist

- [x] Guardrail blocks unsafe tool calls before execution.
- [x] REVIEW requests pause execution and require an explicit approve/deny/timed-out outcome.
- [x] Raw tool exposure is hidden behind the checkpoint.
- [x] Policy ordering is BLOCK > REVIEW > ALLOW.
- [x] Audit entries are written before execution and include all required fields.
- [x] The sandbox is portable and path validation blocks escapes.
- [x] Dashboard boots in headless mode and exposes the expected tabs.
- [x] Automated checks pass with fresh command output.

## Limitations

- This is a simulation; the tools are not real file system, email, or database integrations.
- An ALLOW decision only means the request matches the policy; it does not guarantee the action is safe in a production environment.
- The guardrail does not stop prompt injection by itself; it only enforces policy on tool calls that pass through the checkpoint.
- The protection only works while tools are reachable solely through the checkpoint and not via raw references.
- Human approvers can make mistakes, so REVIEW is a policy pause rather than a guarantee of correctness.
