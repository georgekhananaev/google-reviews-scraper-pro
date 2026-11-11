# Contributing

Thanks for wanting to help out! Bug reports, fixes and new ideas are all welcome.

## Setting up

You'll need Python 3.10 or newer and Google Chrome.

```bash
git clone https://github.com/<your-username>/google-reviews-scraper-pro.git
cd google-reviews-scraper-pro
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt pytest
cp config.sample.yaml config.yaml
```

## Running the tests

```bash
python -m pytest -q
```

CI runs the same command on Ubuntu and Windows across several Python versions. The MongoDB and S3 tests skip themselves when those backends are turned off in your config, so you don't need either one to run the suite.

## Reporting a broken selector

Google changes the Maps page from time to time, and that's the most common reason the scraper stops finding reviews. If that happens:

1. Run `python start.py selector-health` and copy the output.
2. Open an issue and include:
   - the output from step 1,
   - a Google Maps URL for a public business where it fails,
   - your Maps language/locale, OS and Python version,
   - the relevant lines from `logs/` (please remove anything personal first).

Before opening an issue, have a look at [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md). The fix is often in there.

## Sending a pull request

- Keep it focused: one fix or feature per PR.
- Add or update tests for the behavior you change.
- Run `python -m pytest -q` before pushing.
- Describe what changed and why, and link the issue it fixes.

## Security issues

Please don't report security problems in public issues. See [SECURITY.md](SECURITY.md) for how to report them privately.

## Code of conduct

By taking part in this project you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
