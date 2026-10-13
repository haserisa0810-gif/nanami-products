"""Offline safety checks; no credentials, customer data or API calls."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, Mock
import pytest


def module(name):
    path = Path(__file__).resolve().parents[1] / 'ops/capacity' / name
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


monitor, config = module('monitor.py'), module('policies.py')
ENV = {'GOOGLE_CLOUD_PROJECT': 'nanami-astro', 'DATABASE_URL': 'private-secret'}


@pytest.mark.parametrize('failure', [None, 'not_readonly', 'query', 'negative'])
def test_probe_is_readonly_and_always_closes(monkeypatch, failure):
    con, cur = MagicMock(), MagicMock()
    con.cursor.return_value.__enter__.return_value = cur
    cur.fetchone.side_effect = [('off' if failure == 'not_readonly' else 'on',), (-1 if failure == 'negative' else 20,)]
    if failure == 'query':
        cur.execute.side_effect = RuntimeError('sensitive SQL error')
    monkeypatch.setattr(monitor.psycopg2, 'connect', lambda *a, **k: con)
    if failure:
        with pytest.raises((RuntimeError, ValueError)):
            monitor.database_size('private-secret')
    else:
        assert monitor.database_size('private-secret') == 20
        assert [call.args[0] for call in cur.execute.call_args_list] == ["SET LOCAL statement_timeout = '5s'", "SET LOCAL lock_timeout = '1s'", 'SHOW transaction_read_only', 'SELECT pg_database_size(current_database())']
    con.set_session.assert_called_once_with(readonly=True, autocommit=False)
    con.rollback.assert_called_once()
    con.close.assert_called_once()


def test_success_only_publishes_aggregate_size():
    writer, emit = Mock(), Mock()
    assert monitor.run(ENV, probe=lambda _: 20, writer=writer, emit=emit) == 0
    writer.assert_called_once_with('nanami-astro', {'postgres_database_bytes': 20, 'check_success': 1})
    assert 'private-secret' not in repr(emit.call_args_list)


def test_failed_probe_does_not_fake_zero_usage_or_leak_data():
    def fail(_):
        raise RuntimeError('private-secret customer-details')
    writer, emit = Mock(), Mock()
    assert monitor.run(ENV, probe=fail, writer=writer, emit=emit) == 1
    writer.assert_called_once_with('nanami-astro', {'check_success': 0})
    assert 'private-secret' not in repr(emit.call_args_list)
    assert 'customer-details' not in repr(emit.call_args_list)


def test_metric_failure_is_nonzero_and_does_not_expose_token():
    writer, emit = Mock(side_effect=RuntimeError('Bearer private-secret')), Mock()
    assert monitor.run(ENV, probe=lambda _: 20, writer=writer, emit=emit) == 1
    assert 'private-secret' not in repr(emit.call_args_list)


def test_missing_config_never_connects():
    probe, writer = Mock(), Mock()
    assert monitor.run({}, probe=probe, writer=writer, emit=Mock()) == 1
    probe.assert_not_called()
    writer.assert_not_called()


def test_metric_publisher_uses_metadata_token_and_sends_no_database_secret():
    session = Mock()
    session.get.return_value.json.return_value = {'access_token': 'temporary-token'}
    monitor.publish('nanami-astro', {'postgres_database_bytes': 20, 'check_success': 1}, session=session)
    session.get.return_value.raise_for_status.assert_called_once()
    session.post.return_value.raise_for_status.assert_called_once()
    sent = session.post.call_args.kwargs
    assert sent['headers'] == {'Authorization': 'Bearer temporary-token'}
    assert {item['metric']['type']: item['points'][0]['value']['int64Value'] for item in sent['json']['timeSeries']} == {
        monitor.PREFIX + 'postgres_database_bytes': '20', monitor.PREFIX + 'check_success': '1',
    }
    assert all(item['resource'] == {'type': 'global', 'labels': {'project_id': 'nanami-astro'}} for item in sent['json']['timeSeries'])
    assert 'private-secret' not in repr(sent['json'])


def test_publisher_rejects_project_injection_before_request():
    session = Mock()
    with pytest.raises(ValueError):
        monitor.publish('nanami-astro/other-project', {'check_success': 1}, session=session)
    session.get.assert_not_called()
    session.post.assert_not_called()


def test_policies_cover_capacity_failures_and_missed_checks():
    policies = config.policies('nanami-astro', 'projects/nanami-astro/notificationChannels/123', 700_000_000, 850_000_000)
    assert [p['conditions'][0]['conditionThreshold']['thresholdValue'] for p in policies[:2]] == [700_000_000, 850_000_000]
    assert policies[2]['conditions'][0]['conditionThreshold']['comparison'] == 'COMPARISON_LT'
    assert policies[3]['conditions'][0]['conditionAbsent']['duration'] == '43200s'
    assert all(p['notificationChannels'] == ['projects/nanami-astro/notificationChannels/123'] for p in policies)


@pytest.mark.parametrize('channel,warning,critical', [('projects/wrong-project/notificationChannels/1', 7, 8), ('projects/nanami-astro/notificationChannels/1', 8, 7), ('projects/nanami-astro/notificationChannels/1', 0, 8)])
def test_misconfigured_destination_or_thresholds_are_rejected(channel, warning, critical):
    with pytest.raises(ValueError):
        config.policies('nanami-astro', channel, warning, critical)
