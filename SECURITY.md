# Security Policy

## Supported Versions

This project currently maintains the latest `main` branch.

## Reporting a Vulnerability

If you discover a security issue, please do not open a public issue first.

Please report privately with:

- Reproduction steps
- Impact scope
- Suggested fix (optional)

After receiving a report, maintainers will:

1. Confirm the issue
2. Assess severity
3. Prepare and publish a fix

## Sensitive Data Guidance

- Never commit `.env` or real API credentials
- Do not upload real candidate resumes/audio in public examples
- Use test data for screenshots and demos

## Deployment Recommendations

- Store secrets in platform secret manager
- Enable HTTPS only
- Rotate API keys regularly
- Set data retention policy before production usage
