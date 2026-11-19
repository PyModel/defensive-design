# Primary Sources and Applicability

Reviewed on 2026-09-04; the language-semantics rows were checked on 2026-09-22, and the Bash, PostgreSQL and asyncio task-reference rows on 2026-11-10. These anchors support design reasoning, not a
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
| [Python asyncio task documentation](https://docs.python.org/3/library/asyncio-task.html) | Cooperative cancellation, event-loop clock and timeout_at; the event loop keeps only weak references to tasks, so keep a reference to each one | The illustrative Python example is not hard real-time or CPU preemption |
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
| [Bash manual: the set builtin](https://www.gnu.org/software/bash/manual/html_node/The-Set-Builtin.html) | Contexts where `-e` does not exit; `pipefail`; `-u` | Bash-specific; check the shell the script actually runs under |
| [PostgreSQL: transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html) | Read Committed is the default; after a serialization failure, retry the whole transaction | PostgreSQL-specific; check the engine and version in use |
| [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html) | Problem details for HTTP APIs, cited by the failure taxonomy | HTTP-specific; one representation option, not a requirement |
| [W3C WCAG: Status Messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html) | Accessible presentation of operation states | Apply the relevant platform's accessibility mechanisms; this is not a full accessibility audit |
| [GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use) | Full commit pins, least privilege, untrusted workflow inputs | Pinning is one control, not proof a dependency or workflow is safe |

The adaptation tables and templates are this project's synthesis. They are not copied
standards checklists and intentionally do not require a particular language, database,
architecture style, cloud, telemetry vendor, or agent provider.

## Production architecture additions reviewed on 2026-11-18

Use the stable protocol/standard and the actual platform version. In the NIST
publication listing checked for this revision, SSDF 1.1 is final and 1.2 is a draft;
do not label draft guidance a final requirement. The new architecture, interface,
security and operational tables are project synthesis, with these primary anchors:

| Source | Guidance used | Applicability limit |
|---|---|---|
| [SEI Quality Attribute Workshop](https://www.sei.cmu.edu/library/quality-attribute-workshop-collection/) | Business-driven, prioritized quality scenarios and visible assumptions/tradeoffs | A concise decision can use scenarios without requiring a formal workshop |
| [Cockburn: hexagonal architecture](https://alistair.cockburn.us/hexagonal-architecture) | Application policy separated from external adapters | Does not require one interface per class or a distributed deployment |
| [Azure architecture styles](https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/) | Conditional choices, benefits, constraints and operating complexity | The catalog is not exhaustive and Azure services are not required |
| [Azure CQRS](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs) | Separate read/write models; one store can suffice | CQRS does not mandate messaging, event sourcing or separate databases |
| [Azure event sourcing](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing) | Authoritative event history, projections, evolution and replay costs | An audit requirement alone does not prove event sourcing is appropriate |
| [AWS transactional outbox](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html) | Atomic state/publication intent; consumers must handle duplicates | Transport features do not prove exactly-once external effects |
| [AWS saga orchestration](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/saga-orchestration.html) | Compensation, idempotency and lack of global isolation | Compensation is a new fallible action, not a distributed rollback |
| [AWS ADR process](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html) | Decision context, consequences, ownership and supersession | Local reversible changes do not need a heavyweight approval process |
| [API implementation](https://learn.microsoft.com/en-us/azure/architecture/best-practices/api-implementation) | Version, tenant, conditional-write and asynchronous operation contracts | Apply the chosen protocol; schema generation alone proves no business invariant |
| [Asynchronous request-reply](https://learn.microsoft.com/en-us/azure/architecture/patterns/asynchronous-request-reply) | Acceptance separated from completion with operation status | Durable processing depends on the actual acceptance and persistence boundary |
| [AWS timeouts, retries and jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/) | Bounded recovery, ambiguous effects, layered amplification | Derive budgets locally and preserve provider-specific semantics |
| [AWS exponential backoff and jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/) | Randomized bounded delays and synchronized-client behavior | Jitter alone does not bound total attempts, work or incident load |
| [Google SRE: implementing SLOs](https://sre.google/workbook/implementing-slos/) | User-oriented good/eligible events and accountable reliability decisions | Availability targets do not relax correctness or security invariants |
| [Google SRE: alerting on SLOs](https://sre.google/workbook/alerting-on-slos/) | Budget consumption, multiple windows and response urgency | Do not copy example targets or thresholds without workload evidence |
| [Google SRE: canarying releases](https://sre.google/workbook/canarying-releases/) | Canary/control comparison and scoped rollout evidence | A small binary cohort does not isolate shared database changes |
| [AWS restore testing](https://docs.aws.amazon.com/wellarchitected/latest/framework/rel09-bp04.html) | Recover and validate backups against recovery objectives | Provider payments and other external effects are outside a database restore |
| [PostgreSQL ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html) | Operation-specific locks, table changes and constraint validation | Inspect the deployed PostgreSQL version; additive syntax is not an online guarantee |
| [PostgreSQL continuous archiving](https://www.postgresql.org/docs/current/continuous-archiving.html) | Recoverable WAL state and separately managed configuration | PostgreSQL-specific; snapshot recovery does not undo other systems |
| [NIST SSDF publications](https://csrc.nist.gov/projects/ssdf/publications) | Distinguish final SSDF from drafts and profiles | A source mapping is not a compliance assessment |
| [OWASP ASVS](https://owasp.org/projects/asvs) | Verifiable application security requirements | Select the relevant version and controls; no certification implied |
| [CISA Secure by Design](https://www.cisa.gov/securebydesign) | Secure defaults and reducing preventable user burden | Translate principles into the product's actual control boundaries |
| [OWASP SSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) | Destination/address validation and network containment | A URL filter alone is not evidence of controlled egress |
| [OWASP authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html) | Deny by default, least privilege and resource-specific checks | Delayed work needs an explicit delegation or service-obligation policy |
| [OWASP sessions](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) and [CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) | Session lifecycle, cookie protections and state-changing request defenses | Choose defenses for the real browser and authentication flow |
| [OAuth security BCP, RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html) | Client-profile-specific PKCE, redirect, transaction and refresh-token protections | Verify provider support; document protocol gaps rather than invent capabilities |
| [Native OAuth, RFC 8252](https://www.rfc-editor.org/rfc/rfc8252.html) | External browser and public native-client behavior | Embedded shared secrets do not establish confidentiality |
| [JWT BCP, RFC 8725](https://www.rfc-editor.org/rfc/rfc8725.html) | Algorithm, issuer, audience and token-purpose verification | JWT rules do not imply every access token uses JWT |
| [OWASP secrets management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html) | Rotation, revocation, retention and recovery lifecycle | Key retirement must account for required data recovery |
| [SLSA artifact verification](https://slsa.dev/spec/v1.2/verifying-artifacts) | Bind artifact digest, expected builder/source and allowed inputs | Signature validity or attestation presence alone does not establish trusted origin |
| [HTTPX environment variables](https://www.python-httpx.org/environment_variables/) | `trust_env=False` opts an offline client out of host proxy/CA settings | The URL-construction property test performs no network I/O; application proxy policy is unchanged |
