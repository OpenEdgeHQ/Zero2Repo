# case009 F18 / CoW probe (deferred)

Plan item: run F18 / `_helpers.py` copy-on-write probes on an existing
case009 image and record fail / skip / degrade. Do **not** add
`judge_profile=cow` or extra capabilities to every judge container.

This round does not start that image. Current cases are not used as the
acceptance gate. When someone later runs the probe, record:

- whether `require_cow_clone` / loopback setup succeeded
- whether tests skipped for missing CoW / missing privilege
- whether ordinary dedup degraded to a non-CoW copy

Revisit only as a separate privileged-job item.
