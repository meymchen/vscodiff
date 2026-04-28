# Contributing to vscodiff

Welcome! This project is a Python implementation of VS Code's diff algorithm. 
Here are the guidelines for contributing.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/meymchen/vscodiff.git
cd vscodiff

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
uv sync --all-extras
```

## Code Style

This project uses **ruff** for linting and formatting:

```bash
# Check for issues
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

## Type Checking

We use **ty** for type checking:

```bash
uv run ty check .
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=vscodiff --cov-report=term-missing
```

## Commit Messages

- Use clear, descriptive commit messages
- Start with a verb (Add, Fix, Update, Remove, etc.)
- Keep the first line under 72 characters
- Add a blank line followed by details if needed

## Pull Requests

1. Fork the repository
2. Create a new branch for your feature/fix
3. Make your changes with passing tests and type checks
4. Submit a pull request with a clear description

## Reporting Issues

Bug reports and feature requests are welcome on [GitHub Issues](https://github.com/meymchen/vscodiff/issues).
