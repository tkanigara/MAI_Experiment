"""Shared test-only authentication override.

Runtime builds never read an environment bypass. Tests opt in programmatically
so API suites can focus on their existing contracts; authentication behavior
has dedicated coverage in test_auth.py.
"""

from dashboard import main


main.app.state.auth_test_user = {
    "id": "00000000-0000-0000-0000-000000000001",
    "email": "tester@mai.co.id",
    "name": "MAI Test User",
    "picture": None,
}
