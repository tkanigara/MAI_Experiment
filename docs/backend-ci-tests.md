# Backend tests in GitLab CI

Run from the repository root on Python 3.11:

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p "test_*.py"
```

The backend suite uses standard-library unittest.TestCase classes, assertions,
mock patches and cleanup. Parameterized cases are separate test methods so
unittest discovers and executes every case. No pytest dependency or fixture
loader is required, and the existing GitLab test command can stay unchanged.

`tests/test_support.py` supplies offline Gemini stubs and per-test dashboard
authentication setup. Model responses must be mocked explicitly: accidental
live model calls fail rather than use real Gemini credentials. Authentication
tests remove the test identity to verify anonymous access, CSRF, Google login,
service-token permissions and logout. Patches are restored after each test.

Do not disable staging authentication or add production secrets to CI just to
pass unit tests. These tests do not apply migrations or modify staging services.
Real OAuth, Meta sync and QStash/Slides integration still need separate staging
smoke tests with configured services.

The GitLab CI configuration is managed outside this repository (including
origin/staging as checked on 2026-10-15). No pipeline configuration change is
needed for this unittest-compatible version; update the application/test code
and rerun the existing backend job.
