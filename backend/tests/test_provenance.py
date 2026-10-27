import json
from io import BytesIO
import urllib.request
from app.runtime import execution_provenance


def test_provenance_whitelists_verified_identity_and_never_persists_token(tmp_path, monkeypatch):
    path = tmp_path / 'event.json'; path.write_text('{"schedule":"50 3 * * 1-5"}')
    for key, value in {'GITHUB_EVENT_NAME': 'schedule', 'GITHUB_EVENT_PATH': str(path), 'GITHUB_RUN_ID': '123',
                       'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_SHA': 'abc', 'GITHUB_REPOSITORY': 'owner/repo',
                       'SCHEDULER_EVIDENCE_TOKEN': 'test-private-token'}.items():
        monkeypatch.setenv(key, value)
    class Opener:
        def open(self, request, timeout):
            assert request.full_url == 'https://api.github.com/repos/owner/repo/actions/runs/123'
            assert timeout == 5
            return BytesIO(json.dumps({'id': 123, 'event': 'schedule', 'head_sha': 'abc',
                                       'run_attempt': 1, 'created_at': '2026-10-27T03:50:00Z'}).encode())
    monkeypatch.setattr(urllib.request, 'build_opener', lambda handler: Opener())
    evidence = execution_provenance()
    assert evidence['scheduleEvidence'] == 'VERIFIED'
    assert 'test-private-token' not in json.dumps(evidence)


def test_missing_telemetry_token_is_unverified_without_network(monkeypatch):
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'schedule')
    monkeypatch.delenv('SCHEDULER_EVIDENCE_TOKEN', raising=False)
    monkeypatch.setattr(urllib.request, 'build_opener', lambda *args: (_ for _ in ()).throw(AssertionError('No network expected')))
    assert execution_provenance()['scheduleEvidence'] == 'UNVERIFIED'
