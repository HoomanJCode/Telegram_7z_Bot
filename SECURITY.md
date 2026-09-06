# 🔒 Security Policy

## Supported Versions

Security updates are provided for the latest release and the `master` branch:

| Version        | Supported |
|----------------|-----------|
| Latest release | ✅        |
| `master`       | ✅        |
| Older releases | ❌        |

## Reporting a Vulnerability

If you find a security vulnerability, **do not open a public issue**. Please report it privately:

1. Go to **Security → Report a vulnerability** on the repository: [Report a vulnerability](https://github.com/HoomanJCode/Telegram_7z_Bot/security/advisories/new)
2. Include in your report:
   - Steps to reproduce
   - Affected versions or endpoints
   - Impact and a suggested fix (if known)

You can expect an acknowledgement within 48 hours, followed by a fix as soon as possible. Please allow time for the fix to be released before disclosing the issue publicly.

## Security Notes

- **`BOT_TOKEN` must stay secret** — never commit `.env` or paste tokens into issues, PRs, or chat
- Direct-link files are served by random, unguessable filenames
- Hosted files expire automatically after `STORE_TIME_HOURS` and are removed by the bot's cleanup loop
- Use the whitelist (`WHITELIST`) to restrict who can use the bot
- The web server only serves files from `data/hosted_files` and blocks path traversal
- On VPS deploys, the `.env` file is written with `chmod 600`
- Passwords for encrypted archives are stored locally and never transmitted to third parties