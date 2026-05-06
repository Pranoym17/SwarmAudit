# SwarmAudit Example Report Excerpt

Repository: `https://github.com/psf/requests`

This excerpt comes from a local smoke test using the mock-first MVP pipeline.

## Summary

- Files scanned: `41`
- Files skipped: `122`
- Total findings: `217`
- Findings displayed: `34`
- Hidden lower-priority findings: `183`

## Severity Summary

- CRITICAL: `0`
- HIGH: `4`
- MEDIUM: `121`
- LOW: `92`

## Agent Summary

- Security Agent: `4`
- Performance Agent: `115`
- Quality Agent: `48`
- Docs Agent: `50`

## Example Finding

### [HIGH] TLS certificate verification disabled

- File: `tests/test_requests.py:2908-2908`
- Agent: `Security Agent`

Disabling TLS verification can allow man-in-the-middle attacks.

**Why it matters:** Attackers often search repos for exposed credentials and unsafe execution paths.

**Suggested fix:**

```text
Remove verify=False and use a trusted CA bundle if needed.
```

## Display Policy

SwarmAudit preserves full finding totals but displays a prioritized subset for readability. High-severity findings are shown first, repeated low-severity findings are summarized, and report warnings explain when lower-priority findings are hidden from the demo view.
