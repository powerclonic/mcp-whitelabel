# MCP Tool Reference

All tools are exposed via the FastMCP HTTP transport at `/mcp`.  Clients must supply a valid OIDC Bearer token.

## search_governance

**Scope required**: `query:read`

Natural-language Q&A against the governance knowledge base.

### Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `query` | `string` | ✓ | The question to answer |
| `domain` | `string` | — | Optional domain filter (e.g. `"security"`) |

### Response

```json
{
  "found": true,
  "answer": "Containers must not run as root ...",
  "cited_chunks": [
    {
      "chunk_id": "abc123",
      "origin": "docs/container-policy.md",
      "policy_version": "2024-01-01"
    }
  ]
}
```

When no evidence meets the 0.5 score threshold:

```json
{"found": false, "answer": "insufficient evidence", "cited_chunks": []}
```

---

## check_library_compliance

**Scope required**: `compliance:read`

Validates a library version against the approved catalog.

### Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | ✓ | Library name (e.g. `"requests"`) |
| `version` | `string` | ✓ | Version string (e.g. `"2.31.0"`) |

### Response

```json
{
  "found": true,
  "status": "compliant",
  "justification": "Version 2.31.0 is approved.",
  "cited_chunks": [
    {"chunk_id": "catalog:requests:2.31.0", "origin": "catalog", "policy_version": "2024-01-15"}
  ]
}
```

Possible `status` values: `compliant` | `warning` | `non_compliant`.

---

## check_code_compliance

**Scope required**: `compliance:read`

Evaluates a code snippet against indexed governance standards.

### Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `snippet` | `string` | ✓ | The code snippet to evaluate |
| `domain` | `string` | — | Optional domain filter |

### Response

```json
{
  "found": true,
  "status": "compliant",
  "justification": "No issues found matching indexed standards.",
  "cited_chunks": [...]
}
```

---

## check_infra_compliance

**Scope required**: `compliance:read`

Validates an infrastructure definition (e.g., Dockerfile, Compose, Terraform) against policies.

### Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `definition` | `string` | ✓ | Raw infra definition text |
| `type` | `string` | — | Hint: `"dockerfile"`, `"compose"`, `"terraform"` |

### Response

```json
{
  "found": true,
  "status": "non_compliant",
  "justification": "Violations: Unpinned base image: 'latest' tag is not reproducible",
  "cited_chunks": [...]
}
```

Deterministic checks performed regardless of vector evidence:

- `:latest` image tag
- Unpinned base image (no tag or digest)
- Privileged port exposure (< 1024)
- Hardcoded secrets patterns
