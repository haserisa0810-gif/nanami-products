"""Standalone read-only database size probe; never imports the web app.

PostgreSQL database size is not Neon's project/account-wide billed usage.
"""
from datetime import datetime, timezone
import json
import os
import re
import sys
import psycopg2
import requests

PREFIX = 'custom.googleapis.com/nanami_capacity/'


def database_size(dsn):
    con = psycopg2.connect(dsn, connect_timeout=10)
    try:
        con.set_session(readonly=True, autocommit=False)
        with con.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SET LOCAL lock_timeout = '1s'")
            cur.execute('SHOW transaction_read_only')
            if cur.fetchone()[0] != 'on':
                raise RuntimeError('Read-only mode unavailable')
            cur.execute('SELECT pg_database_size(current_database())')
            size = cur.fetchone()[0]
            if type(size) is not int or size < 0:
                raise ValueError('Invalid size result')
            return size
    finally:
        try:
            con.rollback()
        finally:
            con.close()


def publish(project, values, session=None):
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,61}[a-z0-9]', project):
        raise ValueError('Invalid project')
    session = session or requests.Session()
    response = session.get('http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token', headers={'Metadata-Flavor': 'Google'}, timeout=10)
    response.raise_for_status()
    token = response.json()['access_token']
    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    series = [{
        'metric': {'type': PREFIX + key},
        'resource': {'type': 'global', 'labels': {'project_id': project}},
        'metricKind': 'GAUGE', 'valueType': 'INT64',
        'points': [{'interval': {'endTime': now}, 'value': {'int64Value': str(value)}}],
    } for key, value in values.items()]
    result = session.post(f'https://monitoring.googleapis.com/v3/projects/{project}/timeSeries', headers={'Authorization': 'Bearer ' + token}, json={'timeSeries': series}, timeout=15)
    result.raise_for_status()


def run(env=None, probe=database_size, writer=publish, emit=print):
    env = os.environ if env is None else env
    project, dsn = env.get('GOOGLE_CLOUD_PROJECT'), env.get('DATABASE_URL')
    if not project or not dsn:
        emit(json.dumps({'severity': 'ERROR', 'event': 'capacity_config_missing'}))
        return 1
    try:
        size = probe(dsn)
    except Exception as exc:
        emit(json.dumps({'severity': 'ERROR', 'event': 'capacity_probe_failed', 'error_type': type(exc).__name__}))
        try:
            writer(project, {'check_success': 0})
        except Exception:
            emit(json.dumps({'severity': 'ERROR', 'event': 'capacity_failure_metric_failed'}))
        return 1
    try:
        writer(project, {'postgres_database_bytes': size, 'check_success': 1})
    except Exception as exc:
        emit(json.dumps({'severity': 'ERROR', 'event': 'capacity_metric_failed', 'error_type': type(exc).__name__}))
        return 1
    emit(json.dumps({'severity': 'INFO', 'event': 'capacity_check_ok', 'database_bytes': size}))
    return 0


if __name__ == '__main__':
    sys.exit(run())
