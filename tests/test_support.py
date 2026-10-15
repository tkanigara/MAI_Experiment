"""Standard-library-only test isolation for both unittest and pytest runners."""

import os
import sys
from types import ModuleType
from unittest import TestCase
from unittest.mock import Mock, patch

# Collection must not load .env or require real Gemini credentials. Tests that
# exercise analysis explicitly inject responses; accidental live calls fail.
for module_name in ("agentic.models.gemini", "models.gemini"):
    module = ModuleType(module_name)
    module.llm = Mock(name="offline_llm")
    module.llm.invoke.side_effect = AssertionError(
        "Mock the LLM response; real Gemini calls are disabled in unit tests."
    )
    sys.modules[module_name] = module


class OfflineTestCase(TestCase):
    def setUp(self):
        from dashboard import main

        self.enterContext(
            patch.object(
                main.app.state,
                "auth_test_user",
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "email": "tester@mai.co.id",
                    "name": "MAI Test User",
                    "picture": None,
                },
                create=True,
            )
        )

    def patch_env(self, key, value):
        self.enterContext(patch.dict(os.environ, {key: value}))

    def remove_env(self, key, raising=True):
        self.enterContext(patch.dict(os.environ))
        if raising:
            del os.environ[key]
        else:
            os.environ.pop(key, None)

    def patch_attribute(self, target, *args):
        patcher = (
            patch(target, args[0])
            if isinstance(target, str)
            else patch.object(target, *args)
        )
        return self.enterContext(patcher)

    def remove_attribute(self, target, name):
        original = getattr(target, name)
        self.addCleanup(setattr, target, name, original)
        delattr(target, name)
