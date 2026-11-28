import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error

HERE=Path(__file__).resolve().parents[1]
HELPER=HERE / 'github-registry/github_source.py'
spec=importlib.util.spec_from_file_location('github_source_under_test', HELPER)
source=importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)
SHA='a'*40

class GitHubSourceTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(source.os.environ)
        environment.start(); self.addCleanup(environment.stop)
        source.os.environ.pop('GITHUB_TOKEN', None)  # FIX-GTS-295: requests stay plain URLs here

    def test_package_workflows_fetch_only_github_runtime(self):
        root = HERE.parent
        for folder in (root / '.github/workflows', HERE / 'github-registry'):
            for channel in ('release', 'debug'):
                workflow = (folder / ('ci-package-' + channel + '.yml')).read_text()
                # FIX-RT-902: the fork's diagnostic workflow deliberately never
                # fetches the upstream runtime or calls its registry.
                if folder == root / '.github/workflows' and channel == 'debug':
                    self.assertEqual(workflow.count('git remote add origin https://github.com/gperea602/RyGT.git'), 1)
                    self.assertNotIn('RyGT-Team/RyGT', workflow)
                    self.assertNotIn('RyGT-Team/shadGT', workflow)
                    self.assertNotIn('registry_ci.py', workflow)
                    self.assertIn("github.repository == 'gperea602/RyGT'", workflow)
                    self.assertIn("github.ref == 'refs/heads/feat/giulio-racing-ai'", workflow)
                    self.assertIn("https://github.com/gperea602/shadGT.git", workflow)
                    self.assertIn('pin["commit"] == "bbd838b3cdfe215184495fd9b5cf6967a4ecd1de"', workflow)
                    self.assertIn("branches: [feat/giulio-racing-ai]", workflow)
                    self.assertIn("git rev-parse HEAD", workflow)
                else:
                    self.assertEqual(workflow.count('git remote add origin https://github.com/RyGT-Team/RyGT.git'), 3)
                self.assertNotIn('gitlab.com/rygt-team/RyGTS.git', workflow)

    def test_exact_revision_waits_for_github(self):
        missing=urllib.error.HTTPError('url',404,'Not Found',{},None)
        response=io.BytesIO(json.dumps({'sha':SHA}).encode())
        with patch.object(source.urllib.request,'urlopen',side_effect=[missing,response]) as get, patch.object(source.time,'sleep') as sleep:
            self.assertEqual(source.wait_for_commit('https://api.github.com/repos/RyGT-Team/RyGT',SHA,attempts=2),SHA)
        self.assertEqual(get.call_count,2)
        self.assertTrue(get.call_args.args[0].endswith('/commits/'+SHA))
        sleep.assert_called_once_with(5)
    def test_bad_revision_never_fetches(self):
        with patch.object(source.urllib.request,'urlopen') as get:
            for bad in ['', 'HEAD', '../main', 'A'*40, 'a'*39]:
                with self.assertRaises(ValueError):source.wait_for_commit('api',bad)
            get.assert_not_called()
    def test_missing_revision_does_not_fall_back(self):
        missing=urllib.error.HTTPError('url',404,'Not Found',{},None)
        with patch.object(source.urllib.request,'urlopen',side_effect=missing), patch.object(source.time,'sleep'):
            with self.assertRaisesRegex(RuntimeError,'did not provide'):source.wait_for_commit('api',SHA,attempts=1)
    def test_auth_failure_is_not_retried(self):
        denied=urllib.error.HTTPError('url',403,'Forbidden',{},None)
        with patch.object(source.urllib.request,'urlopen',side_effect=denied) as get, patch.object(source.time,'sleep') as sleep:
            with self.assertRaises(urllib.error.HTTPError):source.wait_for_commit('api',SHA)
            self.assertEqual(get.call_count,1)
            sleep.assert_not_called()
    def test_wrong_commit_is_rejected(self):
        response=io.BytesIO(json.dumps({'sha':'b'*40}).encode())
        with patch.object(source.urllib.request,'urlopen',return_value=response):
            with self.assertRaises(ValueError):source.wait_for_commit('api',SHA)

class GithubRequestTest(unittest.TestCase):
    def test_token_only_for_the_api(self):
        api = 'https://api.github.com/repos/RyGT-Team/RyGT/commits/development'
        with patch.dict(source.os.environ, {'GITHUB_TOKEN': 'abc'}):
            request = source.github_request(api)
            self.assertEqual(request.full_url, api)
            self.assertEqual(request.get_header('Authorization'), 'Bearer abc')
            raw = 'https://raw.githubusercontent.com/RyGT-Team/RyGT/x/renderer/source.json'
            self.assertEqual(source.github_request(raw), raw)
        with patch.dict(source.os.environ, {}, clear=True):
            self.assertEqual(source.github_request(api), api)
