#!/bin/sh
# Read Docker secret files into environment variables
if [ -f "$OPENROUTER_API_KEY_FILE" ]; then
    export OPENROUTER_API_KEY=$(cat "$OPENROUTER_API_KEY_FILE")
fi
if [ -f "$DEEPSEEK_API_KEY_FILE" ]; then
    export DEEPSEEK_API_KEY=$(cat "$DEEPSEEK_API_KEY_FILE")
fi
if [ -f "$POSTGRES_PASSWORD_FILE" ]; then
    export POSTGRES_PASSWORD=$(cat "$POSTGRES_PASSWORD_FILE")
fi
exec "$@"
