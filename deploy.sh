#!/bin/bash
set -euo pipefail

echo "Direct production deploy is disabled. Follow docs/PRODUCTION_SAFETY.md." >&2
echo "Use scripts/deploy_candidate.ps1 from a clean, pushed commit." >&2
exit 1
