# 🤝 Contributing to Telegram 7z Bot

Thanks for taking the time to contribute! 🎉

## Getting Started

1. **Fork** the repository and clone your fork:

   ```bash
   git clone https://github.com/YOUR_USERNAME/Telegram_7z_Bot.git
   cd Telegram_7z_Bot
   ```

2. **Set up the environment**:

   ```bash
   cp env.example .env
   # Edit .env and add your test bot token
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Create a branch**:

   ```bash
   git checkout -b feature/your-feature
   ```

## Running the Bot

```bash
python bot.py
```

The bot requires `7z` (p7zip) and optionally `aria2` installed on your system.

## Running Tests

Tests use the standard library `unittest`:

```bash
python -m unittest discover tests -v
```

If the `tests/` directory does not exist yet, CI runs an import check instead of failing.

## Code Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use type hints where possible
- Add docstrings to functions and classes
- Keep functions small and focused
- Use meaningful variable names

## Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code restructuring
- `style:` Formatting changes
- `test:` Adding tests
- `chore:` Maintenance tasks
- `ci:` CI/CD changes

## Opening a Pull Request

1. Push your branch and open a pull request against `master`
2. Describe what you changed and why
3. Make sure CI passes
4. Keep PRs small and focused — one change per PR

## Questions?

Ask in [GitHub Discussions](https://github.com/HoomanJCode/Telegram_7z_Bot/discussions).