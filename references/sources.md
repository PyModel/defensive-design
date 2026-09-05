# Primary Sources and Applicability

Reviewed for this revision on 2026-09-04. These anchors support design reasoning, not a
claim of certification or universal compatibility. Check platform-specific claims
against the installed runtime and dependency versions before implementation. Prefer a
stable final standard over a draft unless the task explicitly targets the draft.

| Source | Guidance used | Applicability limit |
|---|---|---|
| [Agent Skills specification](https://agentskills.io/specification) | Portable SKILL.md metadata, progressive disclosure, relative supporting resources | Format conformance does not establish behavior in every agent host |
| [Anthropic skill authoring](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) | Concise core, task-appropriate freedom, on-demand references, real task evaluations | Host-specific instructions remain host-specific |
| [OpenAI Codex skills](https://developers.openai.com/codex/skills/) | Optional host metadata and skill invocation | agents/openai.yaml is an optional adapter, not a universal host API |
| [NIST SSDF project](https://csrc.nist.gov/projects/ssdf) | Risk- and outcome-based practices, applicability and profiles rather than mandatory mechanisms | Select applicable outcomes; this skill does not provide conformance assessment |
| [OWASP Secure Product Design](https://cheatsheetseries.owasp.org/cheatsheets/Secure_Product_Design_Cheat_Sheet.html) | Trust boundaries, least privilege, explicit threats and secure failure | Product threat analysis is not a substitute for physical hazard analysis |
| [OWASP AI Agent Security](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html) | Independent tool policy, untrusted context, bounded authority and execution | Prompt text alone cannot enforce authorization or contain code execution |
| [Google SRE: Handling Overload](https://sre.google/sre-book/handling-overload/) | Capacity protection, retry budgets and amplification | Use local workload evidence; do not copy example thresholds |
| [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html) | HTTP idempotency and Retry-After semantics | HTTP-specific; resource semantics and effect certainty still govern recovery |
| [Python asyncio task documentation](https://docs.python.org/3/library/asyncio-task.html) | Cooperative cancellation, event-loop clock and timeout_at | The illustrative Python example is not hard real-time or CPU preemption |
| [HTTPX timeouts](https://www.python-httpx.org/advanced/timeouts/) | Connect/read/write/pool phase limits | Per-phase inactivity limits are not a complete operation deadline |
| [W3C WCAG: Status Messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html) | Accessible presentation of operation states | Apply the relevant platform's accessibility mechanisms; this is not a full accessibility audit |
| [GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use) | Full commit pins, least privilege, untrusted workflow inputs | Pinning is one control, not proof a dependency or workflow is safe |

The adaptation tables and templates are this project's synthesis. They are not copied
standards checklists and intentionally do not require a particular language, database,
architecture style, cloud, telemetry vendor, or agent provider.
