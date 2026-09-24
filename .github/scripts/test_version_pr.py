"""Exercise stamping with real local git repositories and a recording gh stub."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
MANIFESTS = [
    '.claude-plugin/plugin.json', '.cursor-plugin/plugin.json',
    '.claude-plugin/marketplace.json', '.cursor-plugin/marketplace.json',
    'skills/omni-integrations/.claude-plugin/plugin.json',
    'skills/omni-integrations/.cursor-plugin/plugin.json',
]


class StampPRTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.log = self.root / 'gh.log'
        self.env = dict(os.environ, GH_LOG=str(self.log), TEST_PR='')
        self.run_cmd('git', 'init', '--bare', str(self.root / 'remote.git'))
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.com')
        for name in MANIFESTS + ['versions.json', '.github/scripts/stamp_versions.py',
                                 '.github/scripts/open_version_pr.sh']:
            dest = self.repo / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / name, dest)
        for name in MANIFESTS:
            (self.repo / name).write_text('{"version": "0.0.0"}\n')
        self.git('add', '.')
        self.git('commit', '-m', 'initial')
        self.git('remote', 'add', 'origin', str(self.root / 'remote.git'))
        self.git('push', '-u', 'origin', 'main')
        self.main_sha = self.git('rev-parse', 'main').stdout.strip()
        bindir = self.root / 'bin'
        bindir.mkdir()
        gh = bindir / 'gh'
        gh.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$GH_LOG"\n'
                      'if [ "$1 $2" = "pr list" ]; then printf "%s" "$TEST_PR"; fi\n')
        gh.chmod(0o755)
        self.env['PATH'] = str(bindir) + os.pathsep + self.env['PATH']

    def run_cmd(self, *args):
        return subprocess.run(args, cwd=self.repo, env=self.env, check=True,
                              text=True, capture_output=True)

    def git(self, *args):
        return self.run_cmd('git', *args)

    def stamp(self):
        self.run_cmd('bash', '.github/scripts/open_version_pr.sh')

    def test_create_and_refresh_without_pushing_main(self):
        self.stamp()
        log = self.log.read_text()
        self.assertIn('pr create --base main --head automation/stamp-versions', log)
        self.assertIn('workflow run versions.yml --ref automation/stamp-versions', log)
        self.assertIn('workflow run skills-ci.yml --ref automation/stamp-versions', log)
        self.assertEqual(self.git('rev-parse', 'origin/main').stdout.strip(), self.main_sha)
        self.run_cmd('python3', '.github/scripts/stamp_versions.py', '--check')
        changed = self.git('diff', '--name-only', 'origin/main...HEAD').stdout.splitlines()
        self.assertEqual(set(changed), set(MANIFESTS))

        # Simulate a later main commit and ensure the same PR is refreshed.
        self.git('checkout', 'main')
        (self.repo / 'versions.json').write_text(json.dumps({'version': '9.0.0'}))
        self.git('add', 'versions.json')
        self.git('commit', '-m', 'new version')
        self.git('push', 'origin', 'main')
        new_main = self.git('rev-parse', 'main').stdout.strip()
        self.env['TEST_PR'] = '123'
        self.log.write_text('')
        self.stamp()
        self.assertIn('pr edit 123', self.log.read_text())
        self.assertNotIn('pr create', self.log.read_text())
        self.assertEqual(self.git('rev-parse', 'HEAD^').stdout.strip(), new_main)
        self.assertEqual(self.git('rev-parse', 'origin/main').stdout.strip(), new_main)
        self.run_cmd('python3', '.github/scripts/stamp_versions.py', '--check')

    def test_matching_manifests_do_not_create_pr_or_dispatch(self):
        self.run_cmd('python3', '.github/scripts/stamp_versions.py')
        self.git('add', '.')
        self.git('commit', '-m', 'already stamped')
        self.git('push', 'origin', 'main')
        self.stamp()
        self.assertFalse(self.log.exists())


if __name__ == '__main__':
    unittest.main()
