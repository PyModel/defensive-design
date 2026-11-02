# Security policy

## Supported versions

Only the current `main` branch is supported. Fixes are not backported to earlier
skill versions; reinstall from `main` to pick them up.

## Reporting a vulnerability

Report privately through GitHub:
[Report a vulnerability](https://github.com/PyModel/defensive-design/security/advisories/new).
Do not open a public issue or pull request for an unfixed vulnerability.

Include the affected file and revision, the trigger, the impact, and a minimal
reproduction.

## In scope

- Skill instructions (`skills/defensive-design/`) that would lead an agent to take an
  unsafe or unauthorized action, or to approve insecure code.
- Package contents: anything installed that should not be, such as maintainer files or
  secrets.
- The illustrative HTTP example (`references/resilient_http_example.py`), when one of
  its documented guarantees can be bypassed.
- The maintainer scripts, CI workflow and hash-locked dependencies.

Code an agent writes for you after reading the skill is your code. Report flaws in
it to the project that ships it, unless the skill's guidance caused the flaw.
