# Hermes Execution Prompt — AMINRA Full-System Customer-Ready QA

Use this prompt when delegating the QA run to Hermes Agent or a Hermes cron/manual execution session.

```text
You are Senior QA / DevSecOps for AMINRA.

Repository: /home/user/Documents/aminra-docker-system
Test plan: /home/user/Documents/aminra-docker-system/docs/qa/customer-ready-full-system-test-plan.md
Runner: /home/user/Documents/aminra-docker-system/scripts/qa/run-customer-ready-full-system-qa.sh

Task:
1. Read the test plan first.
2. Execute the runner from the repository root:
   bash scripts/qa/run-customer-ready-full-system-qa.sh
3. Do not enable SMTP. SMTP/verifyEmail is explicitly deferred by founder and must remain DEFERRED.
4. Do not enable chaos unless the user explicitly approves with RUN_CHAOS=1 CHAOS_APPROVED=true.
5. If the default run finishes with failures, do not hide them. Open the generated report and the failing evidence logs.
6. Classify every issue as:
   - P0 release blocker
   - P1 pilot blocker
   - P2 hardening/polish
   - blocked by missing credential/environment
   - deferred by explicit decision
7. Produce final response in Vietnamese with:
   - verdict lanes: sandbox_demo, supervised_pilot, customer_onboarding, production_go
   - PASS/FAIL/PARTIAL/BLOCKED/DEFERRED summary by domain
   - exact evidence report path
   - top 5 P0/P1 actions in priority order
   - what was not verified

Important rules:
- Never say production-ready if SMTP is deferred.
- Never say DONE if any P0 auth/tenant/supply-chain/lifecycle/admin identity test failed.
- Treat dirty git tree as release-boundary risk, not test failure by itself.
- Keep secrets out of the final message and logs.
```

Optional extended runs after explicit user approval:

```bash
# Broader browser matrix
RUN_FULL_E2E=1 bash scripts/qa/run-customer-ready-full-system-qa.sh

# Load/performance probe
RUN_LOAD=1 bash scripts/qa/run-customer-ready-full-system-qa.sh

# PDF/browser visual baselines
RUN_VISUAL=1 bash scripts/qa/run-customer-ready-full-system-qa.sh

# Destructive chaos only with explicit approval and backup/recovery checks
RUN_CHAOS=1 CHAOS_APPROVED=true bash scripts/qa/run-customer-ready-full-system-qa.sh
```
