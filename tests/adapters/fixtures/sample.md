# Governance Standards Guide

This document defines the AI governance standards for our platform.

## Security Standards

All systems must follow these security requirements.

### Authentication

Use OIDC Client Credentials for service-to-service auth.
Never store secrets in code. Use environment variables.

### Authorization

Apply RBAC with least-privilege scopes.
Each MCP tool must declare its required scope.

## Library Policy

Only use approved libraries from the catalog.

### Approved Libraries

- requests: approved for HTTP client use
- fastmcp: approved for MCP server implementation

### Forbidden Libraries

- legacy-sdk: forbidden due to known CVE-2023-1234
