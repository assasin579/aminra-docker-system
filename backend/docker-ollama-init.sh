#!/bin/bash
# Initialize Ollama container: start server and pull models

echo "Starting Ollama server..."
ollama serve &

# Wait for server to start
sleep 15

# Check if qwen2.5:7b model already exists
echo "Checking for existing models..."
ollama list | grep -q "qwen2.5:7b"
if [ $? -ne 0 ]; then
    echo "Model qwen2.5:7b not found. Pulling..."
    ollama pull qwen2.5:7b
else
    echo "Model qwen2.5:7b already exists."
fi

# Optional: pull additional models
# ollama pull mistral

echo "Ollama initialization complete."

# Keep container running
wait
