#!/bin/sh
# Claude reads files with recorded answers unless a key is given in .env, so a laptop run
# costs nothing and works offline. Recorded answers only cover the demo files.
if [ -n "$ANTHROPIC_API_KEY" ]; then
  unset SKILL1_REPLAY_DIR
fi
exec "$@"
