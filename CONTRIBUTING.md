# Contributing Guide

## Development Setup

1. Create Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and modify values.
4. Run app:

```bash
streamlit run app.py
```

## Pull Request Rules

- Keep PR small and focused.
- Add or update tests for behavior changes.
- Do not submit real API keys or private interview data.
- Ensure local checks pass:

```bash
pytest
```

## Coding Style

- Use clear function names and type hints where practical.
- Keep business logic isolated from UI rendering code.
- Prefer explicit error messages for API failures.
