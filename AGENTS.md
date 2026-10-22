# Easy-AI execution rules

Read README.md, docs/v0.0.0.md and docs/v0.0.0 plan.md before changing behavior. Preserve these sources. D01–D14 are binding. Implement M0 → M8 in sequence; record evidence in docs/implementation-progress.md. A local loop is gate A, never full release gate B.

Use Python as the authoritative compiler; consume actual Blockly JSON fixtures. No fixed MNIST script, synthetic training metrics, or production mock runners. Application dependencies must never install torch. Training environment changes, data downloads and SSH tests require explicit scope and authorization. Never change teacher environments by default.

Do not commit credentials, machine configuration, data or user runs. No main writes, force push, deployment, Release or unsolicited PR. Preserve existing work. Use development branches. Default to one integrator; delegate independent modules only after contracts freeze.

Commands: pnpm install --frozen-lockfile; pnpm setup; pnpm check; pnpm test; pnpm dev; pnpm build. Record PASS/FAIL/NOT RUN honestly. Never weaken security or tests to make a check pass. Desktop must retain nodeIntegration=false, contextIsolation=true, sandbox=true, webSecurity=true and validated IPC sender. Token remains in Main/backend memory, sent through stdin only. Serve local assets through the controlled app protocol.
