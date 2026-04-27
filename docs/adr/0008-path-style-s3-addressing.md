# 0008 — Path-style S3 addressing

- Status: Accepted
- Date: 2026-04-27

## Context

S3 has two URL conventions for addressing buckets:

- **Virtual-host style**: `https://<bucket>.<endpoint>/<key>` — the bucket lives in the subdomain.
- **Path style**: `https://<endpoint>/<bucket>/<key>` — the bucket is a path component.

`boto3` defaults to virtual-host style for AWS endpoints (where wildcard SSL is handled by AWS) and tries to use it for custom endpoints too unless told otherwise. For non-AWS S3-compatible servers fronted by a single hostname (MinIO, Railway-issued domains, on-prem gateways), virtual-host style requires:

- A wildcard DNS record covering bucket subdomains, **and**
- A wildcard SSL certificate matching that DNS.

Railway's auto-issued domains do **not** satisfy either. The first request to `https://tg-tail-media.storage-production-2cd5.up.railway.app/...` fails with TLS or DNS errors that surface to `boto3` as a generic 400.

## Decision

Configure the `aioboto3` client with `botocore.config.Config(s3={"addressing_style": "path"}, signature_version="s3v4")`. Applied unconditionally — the same code talks to local MinIO, Railway-hosted MinIO, AWS S3, and R2.

## Consequences

- **Works against any S3-compatible endpoint.** Trade-off is none on AWS proper (path-style is supported there too, just not the default).
- **No reliance on cert/DNS magic at the storage host.** Removes one failure mode that's invisible until the first bucket request.
- **`signature_version="s3v4"` is set explicitly.** The default has changed across botocore versions; pinning avoids surprises when MinIO upgrades.
- **Retry policy (`max_attempts=3, mode=standard`) is set in the same `Config`.** Centralized — easier to revisit than per-call backoff loops in `S3Client`.

## Why this is a separate ADR

It looks like a one-line config tweak, but it's the kind of decision that's deeply non-obvious in a code review six months from now. The constraint comes from the deployment platform, not from the SDK or from S3.
