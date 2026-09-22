# Code-Level Design

Read this when the change is a function, type, class, module, or library interface, or
when a defect lives in how code is shaped rather than in a remote dependency. These are
design questions answered with the language's native facilities, not a mandate to add
types, wrappers, or checks to trusted local code.

## Choose the level that owns the invariant

A control belongs at the lowest level that owns every participant in the invariant.
Moving it higher adds coordination; moving it lower leaves some writers unchecked.

| Level | Owns | Typical native enforcement | Escalate when |
|---|---|---|---|
| Expression / function | Arithmetic, bounds, preconditions, return contract | Checked operations, total functions, early rejection | A caller can reach the state without this function |
| Type / value | Which values can exist | Constructors, validated types, enums/sum types, immutability | Values are created or mutated outside the type |
| Module / package | Invariants across several types and call orders | Narrow interface, private state, one entry point per state transition | Another module or process writes the same state |
| Process / application | Shared memory, lifecycle, local resources | Ownership, locks/actors scoped to the process, structured cleanup | State is durable or shared by independent processes |
| Durable store / distributed system | Invariants across processes, replicas, or time | Constraints, transactions, conditional writes, fencing | See the main workflow and the other references |

Do not escalate by habit: a process-local invariant does not need a database, and a
database invariant cannot be protected by a class constructor alone.

## Separate caller bugs from operational outcomes

| Situation | Nature | Handling |
|---|---|---|
| Untrusted input violates the contract at a trust boundary | Expected operational outcome | Stable `invalid` result or error; never a crash, never an assertion |
| Dependency, I/O, or environment fails | Expected operational outcome | Classify with the [failure taxonomy](failure-taxonomy.md) |
| Trusted internal caller breaks a documented precondition | Programmer error (`contract_violation`) | Fail fast and loudly in the language's idiom; do not retry, degrade, or disguise it as user input error |
| State that the design makes impossible is observed | Corruption or bug (`invariant_violation`) | Stop the unsafe path, preserve evidence, escalate |

A precondition check guarding security, validation, or data integrity must survive
production builds. Assertions are not that mechanism: Python emits no code for
`assert` under `-O`, Java disables assertions at runtime by default, C/C++ `assert`
does nothing when `NDEBUG` is defined, .NET `Debug.Assert` works only in debug builds by
default, and Rust's `debug_assert!` is enabled only in non-optimized builds by default.
Use explicit checks that raise, return, or panic in every build; keep assertions for
internal consistency that tests exercise.

## Parse once at the boundary

Validate untrusted data where it enters, then convert it into a value the rest of the
code can trust: a parsed type, a constructor-checked object, a schema-validated record,
or a documented normalized form. Downstream code then relies on the type instead of
repeating ad hoc checks, and cannot forget one.

- A static type or cast does not validate runtime data. A TypeScript `as` assertion
  (removed at compile time, with no runtime check), an unchecked Java generic cast, or
  deserializing into a struct/class without validating its fields trusts whatever
  arrived.
- Canonicalize before validating and never re-parse the raw value later; see the
  [secure coding overlay](secure-coding-overlay.md) for sink-specific rules.
- Redundant checks deeper inside trusted code are not defense in depth when they can
  disagree with the boundary check. Prefer one authoritative check plus types that
  carry its result.

## Make invalid states unrepresentable, proportionally

Where a value can be in several states, prefer a representation where each state carries
exactly its valid data: a sum type, sealed hierarchy, tagged union, or state-specific
type instead of several nullable fields and boolean flags. Handle every case
exhaustively with the language's compile-time check where one exists, and make the
fallthrough branch fail loudly rather than silently pick a default.

Apply this where invalid combinations are reachable and consequential. Do not introduce
a type hierarchy for a local value with two call sites.

## Own resources and effects explicitly

- Tie cleanup to ownership with the native construct: `with`/context managers,
  `try`-with-resources, `using`, `defer`, RAII/`Drop`, or structured concurrency scopes.
  Every early return, error, and cancellation path must release what was acquired.
- Keep mutation local and visible. Shared mutable aliases, mutable default arguments,
  and returned references to internal state let callers break invariants the module owns.
- Absence is a value. Use the language's optional/nullable type or an explicit result
  instead of sentinel values that collide with valid data (`-1`, `""`, `0`, epoch time).
- Do not swallow errors. An ignored error return, an empty catch, or `unwrap()`,
  force-unwrap (`!`, `!!`) or `Optional.get()` on a fallible value in library code
  converts a recoverable outcome into silent corruption or an unexplained crash for
  the caller.

## Concurrency inside one process

A check-then-act sequence is a race whenever another thread, task, callback, or signal
can run between the check and the act. In single-threaded async code this includes
every `await`/yield point: state read before an await may be stale after it. Re-check
after resuming, hold the owning lock or actor across the whole transition, or make the
transition one atomic operation. Data races on shared memory are undefined or
unspecified behavior in several languages; use the language's synchronization or
ownership model rather than timing.

## Numbers, time, and text

Check only what the contract touches:

- **Integers:** overflow semantics differ by language and build. Rust integer
  operators panic on overflow in debug builds; C signed overflow is undefined behavior;
  Java and Go integer operators wrap without signalling overflow; Python integers are
  unbounded; JavaScript numbers represent integers exactly only up to 2^53 − 1
  (`Number.MAX_SAFE_INTEGER`). Use checked, saturating, or wider arithmetic where the
  range is reachable.
- **Money and exact quantities:** use integer minor units or a decimal type; fix the
  rounding mode and the order of operations; test boundary values.
- **Floating point:** handle NaN, infinity, signed zero, and tolerance-based comparison.
- **Time:** use a monotonic clock for durations and deadlines, wall-clock time only for
  display and records; store instants with an explicit zone/offset; inject the clock
  for tests.
- **Text:** define the encoding, normalization form, and case rules that affect
  identity, comparison, length limits, and security decisions.

## Design interfaces that are hard to misuse

- Prefer named or typed parameters over positional booleans and interchangeable
  primitives (`transfer(from, to, amount)` with three integers invites swapped arguments).
- Make the safe path the default and the dangerous path explicit and greppable.
- Return errors the caller must handle in the language's idiom; document which outcomes
  are expected results and which indicate a bug.
- Keep the interface small enough that its invariants fit in the caller's head; a
  function that requires a specific call order should encode that order in its types
  or state, not in a comment.

## Verify at this level

Boundary values and properties for arithmetic and parsers; one test per reachable
state and transition; negative tests for each rejected input class; cleanup on every
exit path including cancellation; deterministic interleaving tests for check-then-act
across threads or awaits. Run the repository's type checker, linter, and sanitizers
(for example address/undefined-behavior/thread sanitizers where the toolchain provides
them) when they exist; report them `blocked` rather than passing when unavailable.
