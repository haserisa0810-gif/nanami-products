"""Generate reviewable alert configurations without calling external APIs."""
import argparse
import json
from pathlib import Path
import re

PREFIX = 'custom.googleapis.com/nanami_capacity/'


def policies(project, channel, warning, critical):
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,61}[a-z0-9]', project):
        raise ValueError('Invalid project')
    if not re.fullmatch(rf'projects/{re.escape(project)}/notificationChannels/[0-9]+', channel):
        raise ValueError('Notification channel must belong to this project')
    if not (type(warning) is int and type(critical) is int and 0 < warning < critical):
        raise ValueError('Invalid thresholds')
    output = []
    for label, threshold in [('warning', warning), ('critical', critical)]:
        output.append({
            'displayName': 'nanami capacity ' + label, 'enabled': True, 'combiner': 'OR',
            'notificationChannels': [channel],
            'documentation': {'mimeType': 'text/markdown', 'content': f'PostgreSQL database size exceeded {threshold:,} bytes. Check the Neon plan and project-wide usage, including other branches. This is NOT project-wide quota usage. No automatic deletion or plan changes.'},
            'conditions': [{'displayName': label, 'conditionThreshold': {
                'filter': f'metric.type="{PREFIX}postgres_database_bytes" AND resource.type="global"',
                'comparison': 'COMPARISON_GT', 'thresholdValue': threshold, 'duration': '0s',
                'aggregations': [{'alignmentPeriod': '21600s', 'perSeriesAligner': 'ALIGN_MAX'}],
                'trigger': {'count': 1},
            }}],
        })
    output.append({
        'displayName': 'nanami capacity check failed', 'enabled': True, 'combiner': 'OR',
        'notificationChannels': [channel],
        'documentation': {'mimeType': 'text/markdown', 'content': 'Database capacity probe failed. Check Cloud Run Job, connectivity and permissions. Do not expose credentials/customer data.'},
        'conditions': [{'displayName': 'failed probe', 'conditionThreshold': {
            'filter': f'metric.type="{PREFIX}check_success" AND resource.type="global"',
            'comparison': 'COMPARISON_LT', 'thresholdValue': 1, 'duration': '0s',
            'aggregations': [{'alignmentPeriod': '3600s', 'perSeriesAligner': 'ALIGN_MIN'}],
            'trigger': {'count': 1},
        }}],
    })
    output.append({
        'displayName': 'nanami capacity check missing', 'enabled': True, 'combiner': 'OR',
        'notificationChannels': [channel],
        'documentation': {'mimeType': 'text/markdown', 'content': 'No capacity probe has been recorded for 12 hours. Check Scheduler, Job executions and metrics publishing.'},
        'conditions': [{'displayName': 'missing probe', 'conditionAbsent': {
            'filter': f'metric.type="{PREFIX}check_success" AND resource.type="global"',
            'duration': '43200s', 'trigger': {'count': 1},
        }}],
    })
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--channel', required=True)
    parser.add_argument('--warning-bytes', type=int, required=True)
    parser.add_argument('--critical-bytes', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for index, policy in enumerate(policies(args.project, args.channel, args.warning_bytes, args.critical_bytes)):
        (args.output / f'policy-{index}.json').write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding='utf-8')
