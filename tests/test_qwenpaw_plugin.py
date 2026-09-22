"""Unit tests for .qwenpaw-plugin/plugin.py.

Two decisions in that file carry risk, so they are covered here instead of
in a live QwenPaw. The slash-command parser decides what counts as command
control data and what stays untrusted target text, and ``register()`` decides
whether the packaged skills are worth installing at all: the host installs a
plugin with ``shutil.copytree``, which only follows the package's ``skills``
symlink when the checkout kept it a link, and the host reports a successful
install even when it lands zero skills.

Standard library only, like the rest of the suite. The module is imported by
path and the host API is a recording stub, so ``agentscope`` never enters the
picture.  python3 -m unittest discover -s tests
"""
import importlib.util
import logging
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PATH = ROOT / ".qwenpaw-plugin" / "plugin.py"


def load_plugin():
    """Import the plugin entry file without QwenPaw present."""
    spec = importlib.util.spec_from_file_location("sepia_plugin", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin = load_plugin()


class RecordingApi:
    """Stand-in for PluginApi, recording what the plugin registers."""

    def __init__(self):
        self.providers = []
        self.commands = []

    def register_skill_provider(self, skills_dir=None, **kwargs):
        self.providers.append((Path(skills_dir), kwargs))

    def register_slash_command(self, name=None, **kwargs):
        self.commands.append((name, kwargs))


def build_package(root, skills, follow_symlink=True):
    """Lay out a clone-shaped package whose skills entry points at skills/."""
    canonical = root / "skills"
    for name in skills:
        skill_dir = canonical / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    package = root / ".qwenpaw-plugin"
    package.mkdir()
    link = package / "skills"
    if follow_symlink:
        link.symlink_to("../skills")
    else:
        # What git writes into a checkout without symlink support: a plain
        # file holding the link text, which the host then copies as-is.
        link.write_text("../skills", encoding="utf-8")
    return link


class SplitFlagsCase(unittest.TestCase):
    """The untrusted-data boundary of /sepia."""

    def split(self, raw):
        return plugin._split_flags(raw)

    def test_plain_text_is_untouched(self):
        self.assertEqual(self.split("tighten this paragraph"),
                         ("tighten this paragraph", {}))

    def test_trailing_op_is_split_off(self):
        self.assertEqual(self.split("fix the ending --op review"),
                         ("fix the ending", {"op": "review"}))

    def test_flag_looking_text_mid_sentence_is_data(self):
        text, flags = self.split("--op recreate this sentence too --op write")
        self.assertEqual(flags, {"op": "write"})
        self.assertEqual(text, "--op recreate this sentence too")

    def test_repeated_flag_keeps_the_rightmost(self):
        self.assertEqual(self.split("text --op write --op review"),
                         ("text", {"op": "review"}))

    def test_terminator_protects_an_option_looking_tail(self):
        text, flags = self.split("please preserve --op recreate --")
        self.assertEqual(text, "please preserve --op recreate")
        self.assertEqual(flags, {})

    def test_malformed_value_reaches_validation_instead_of_text(self):
        text, flags = self.split("prose --op de2")
        self.assertEqual(text, "prose")
        self.assertEqual(flags, {"op": "de2"})
        self.assertNotIn("de2", text)

    def test_language_is_normalised(self):
        self.assertEqual(self.split("prose --lang ZH"),
                         ("prose", {"lang": "zh"}))


class RegisterCase(unittest.TestCase):
    """What happens when the packaged skills do not resolve."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def register_with(self, follow_symlink=True, skills=None):
        skills = skills or list(plugin.PACKAGED_SKILLS)
        skills_dir = build_package(self.root, skills, follow_symlink)
        api = RecordingApi()
        with mock.patch.object(plugin, "SKILLS_DIR", skills_dir):
            plugin.SepiaPlugin().register(api)
        return api

    def test_resolvable_package_registers_skills_and_command(self):
        api = self.register_with()
        self.assertEqual(len(api.providers), 1)
        self.assertEqual(api.commands[0][0], "sepia")
        enabled = api.providers[0][1]
        self.assertTrue(enabled["enabled_by_default"])
        self.assertEqual(enabled["channels"], ["all"])

    def test_flattened_symlink_registers_nothing(self):
        # Silent zero-skill installs are the failure being guarded: the host
        # would log a warning, register the command, and report success.
        with self.assertLogs(plugin.logger, level=logging.ERROR) as logs:
            api = self.register_with(follow_symlink=False)
        self.assertEqual(api.providers, [])
        self.assertEqual(api.commands, [])
        self.assertIn("git clone", "\n".join(logs.output))

    def test_partial_package_names_the_missing_skills(self):
        skills = [name for name in plugin.PACKAGED_SKILLS if name != "sepia"]
        with self.assertLogs(plugin.logger, level=logging.ERROR) as logs:
            api = self.register_with(skills=skills)
        self.assertEqual(api.providers, [])
        self.assertIn("sepia", "\n".join(logs.output))


class PromptPathCase(unittest.TestCase):
    """The prompt has to name files the agent can actually open."""

    def test_packaged_paths_are_absolute(self):
        for name in plugin.PACKAGED_SKILLS:
            self.assertTrue(Path(plugin._skill_path(name)).is_absolute(), name)

    def test_operations_all_have_an_entry(self):
        expected = {"sepia"} | {f"sepia-{op}" for op in plugin.OPERATIONS}
        self.assertEqual(set(plugin.PACKAGED_SKILLS), expected)


class RepositoryPackageCase(unittest.TestCase):
    """The package in this checkout is the one users install."""

    @unittest.skipUnless(
        (ROOT / ".qwenpaw-plugin" / "skills" / "sepia" / "SKILL.md").is_file(),
        "this checkout has no symlink support, so the package cannot resolve",
    )
    def test_every_advertised_skill_ships(self):
        self.assertEqual(plugin._missing_packaged_skills(), [])


if __name__ == "__main__":
    unittest.main()
