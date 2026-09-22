# Primary Sources and Applicability

Reviewed on 2026-09-04; the language-semantics rows were checked on 2026-09-22. These anchors support design reasoning, not a
claim of certification or universal compatibility. Check platform-specific claims
against the installed runtime and dependency versions before implementation. Prefer a
stable final standard over a draft unless the task explicitly targets the draft.

| Source | Guidance used | Applicability limit |
|---|---|---|
| [Agent Skills specification](https://agentskills.io/specification) | Portable SKILL.md metadata, progressive disclosure, relative supporting resources | Format conformance does not establish behavior in every agent host |
| [Anthropic skill authoring](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) | Concise core, task-appropriate freedom, on-demand references, real task evaluations | Host-specific instructions remain host-specific |
| [OpenAI skills (Codex)](https://learn.chatgpt.com/docs/build-skills) | Optional `agents/openai.yaml` interface, policy and dependency metadata | agents/openai.yaml is an optional adapter, not a universal host API |
| [NIST SSDF project](https://csrc.nist.gov/projects/ssdf) | Risk- and outcome-based practices, applicability and profiles rather than mandatory mechanisms | Select applicable outcomes; this skill does not provide conformance assessment |
| [OWASP Secure Product Design](https://cheatsheetseries.owasp.org/cheatsheets/Secure_Product_Design_Cheat_Sheet.html) | Trust boundaries, least privilege, explicit threats and secure failure | Product threat analysis is not a substitute for physical hazard analysis |
| [OWASP AI Agent Security](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html) | Independent tool policy, untrusted context, bounded authority and execution | Prompt text alone cannot enforce authorization or contain code execution |
| [Google SRE: Handling Overload](https://sre.google/sre-book/handling-overload/) | Capacity protection, retry budgets and amplification | Use local workload evidence; do not copy example thresholds |
| [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html) | HTTP idempotency and Retry-After semantics | HTTP-specific; resource semantics and effect certainty still govern recovery |
| [Python asyncio task documentation](https://docs.python.org/3/library/asyncio-task.html) | Cooperative cancellation, event-loop clock and timeout_at | The illustrative Python example is not hard real-time or CPU preemption |
| [HTTPX timeouts](https://www.python-httpx.org/advanced/timeouts/) | Connect/read/write/pool phase limits; the connect limit also bounds the TLS handshake (httpcore `connection.py` passes the connect timeout to `start_tls`) | Per-phase inactivity limits are not a complete operation deadline |
| [Python assert statement](https://docs.python.org/3/reference/simple_stmts.html#the-assert-statement) | No code is emitted for `assert` under `-O` | Other runtimes differ; check the project's build flags |
| [Java assertions guide](https://docs.oracle.com/javase/8/docs/technotes/guides/language/assert.html) | Assertions are disabled at runtime by default | Deployment flags may enable them; do not rely on either for input validation |
| [C assert (cppreference)](https://en.cppreference.com/w/c/error/assert) | `assert` does nothing when `NDEBUG` is defined | Build configuration decides; check the actual release flags |
| [Rust reference: overflow](https://doc.rust-lang.org/reference/expressions/operator-expr.html) | Integer operators panic on overflow in debug builds; `-C overflow-checks` controls it | Release profile settings decide; use checked/wrapping/saturating operations explicitly |
| [Rust `debug_assert!`](https://doc.rust-lang.org/std/macro.debug_assert.html) | Enabled only in non-optimized builds by default | `-C debug-assertions` can change it; not an input-validation mechanism |
| [.NET `Debug.Assert`](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.debug.assert) | Works only in debug builds by default; `Trace.Assert` for release | Build configuration decides |
| [Go specification: integer overflow](https://go.dev/ref/spec#Integer_overflow) | Signed and unsigned overflow wraps deterministically and never panics | Use explicit range checks where overflow is reachable |
| [Java Language Specification §4.2.2](https://docs.oracle.com/javase/specs/jls/se21/html/jls-4.html) | Integer operators do not indicate overflow | Use `Math.*Exact` or wider types where the range is reachable |
| [MDN: `Number.MAX_SAFE_INTEGER`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/MAX_SAFE_INTEGER) | Integers are exact only up to 2^53 − 1 | Use `BigInt` or a decimal library for larger or exact quantities |
| [TypeScript handbook: type assertions](https://www.typescriptlang.org/docs/handbook/2/everyday-types.html) | `as` assertions are removed at compile time with no runtime check | Validate runtime data separately from static types |
| [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html) | Problem details for HTTP APIs, cited by the failure taxonomy | HTTP-specific; one representation option, not a requirement |
| [W3C WCAG: Status Messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html) | Accessible presentation of operation states | Apply the relevant platform's accessibility mechanisms; this is not a full accessibility audit |
| [GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use) | Full commit pins, least privilege, untrusted workflow inputs | Pinning is one control, not proof a dependency or workflow is safe |

The adaptation tables and templates are this project's synthesis. They are not copied
standards checklists and intentionally do not require a particular language, database,
architecture style, cloud, telemetry vendor, or agent provider.
