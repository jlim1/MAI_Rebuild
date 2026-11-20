"""Prompt locally instead of putting API keys in a shell command or file."""
import getpass
import os
from pathlib import Path
import sys
import warnings


def main():
    if not sys.stdin.isatty():
        raise SystemExit('Run this launcher in a terminal, or launch the offline demo instead.')
    root = Path(__file__).resolve().parent
    os.chdir(root)
    if not (root / 'frontend' / 'dist' / 'index.html').is_file():
        raise SystemExit('Build the frontend first (on Windows, run setup.cmd).')
    import uvicorn

    print('Ask Mai is optional. Keys entered here stay in this server process.\n'
          'Press Enter to keep an existing setting or skip a provider.')
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            for provider, env_name in [('OpenAI', 'OPENAI_API_KEY'), ('Anthropic', 'ANTHROPIC_API_KEY')]:
                key = getpass.getpass(f'{provider} API key (hidden): ').strip()
                if key:
                    os.environ[env_name] = key
        except getpass.GetPassWarning:
            raise SystemExit('A hidden prompt is unavailable here. No server was started.') from None
        except (KeyboardInterrupt, EOFError):
            raise SystemExit('\nSetup cancelled. No server was started.') from None
    print('Open http://127.0.0.1:8000. Press Ctrl+C to stop.')
    uvicorn.run('backend.app:app', host='127.0.0.1', port=8000, proxy_headers=False)


if __name__ == '__main__':
    main()
