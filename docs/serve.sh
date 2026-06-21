#!/bin/bash
# View the gesh-core docs locally (private — never published).
#   ./docs/serve.sh            → serves on http://127.0.0.1:8090
#   ./docs/serve.sh 9001       → custom port
# Stop with Ctrl-C, or:  lsof -ti tcp:8090 | xargs kill
PORT="${1:-8090}"
cd "$(dirname "$0")"
echo "gesh-core docs → http://127.0.0.1:${PORT}/  (architecture.html · consensus-comparison.html)"
exec python3 -m http.server "$PORT" --bind 127.0.0.1
