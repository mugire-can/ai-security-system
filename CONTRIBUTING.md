# Contributing to AI Security Camera System

Thank you for your interest in contributing! We welcome contributions from everyone.

## Getting Started

1. **Fork** the repository
2. **Clone** your fork: `git clone https://github.com/your-username/ai-security-system.git`
3. **Create a branch**: `git checkout -b feature/your-feature-name`
4. **Install dependencies**: `pip install -r requirements.txt`
5. **Make your changes** and commit with clear messages
6. **Push** to your fork and open a **Pull Request**

## Development Setup

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Copy .env.example to .env and configure
cp .env.example .env
```

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ -v --cov=src

# Run a specific test file
python -m pytest tests/test_behaviour_analyser.py -v
```

## Code Style

- Follow PEP 8 conventions
- Use type hints for function arguments and return values
- Add docstrings to public functions and classes
- Keep functions focused and single-purpose

## Commit Message Guidelines

- Use clear, descriptive messages
- Reference issues: `Fixes #123`
- Examples:
  - `Fix: correct person detection threshold in YOLO pipeline`
  - `Feature: add Slack integration for alerts`
  - `Docs: update installation instructions for Windows`

## Reporting Issues

When reporting bugs, include:
- Python version
- OS (Windows/Linux/macOS)
- Error traceback
- Steps to reproduce
- Expected vs. actual behavior

## Pull Request Process

1. Update documentation for any changed features
2. Add tests for new functionality
3. Ensure all tests pass: `pytest tests/ -v`
4. Keep commit history clean
5. Write a clear description of changes in the PR

## Questions?

Open an issue with the `question` label or discuss in the PR.

Happy coding! 🚀
