#!/bin/bash
# Production Test Script for Aminra System
# Run after deploying to Render and Vercel

echo "🔍 Aminra Production System Test"
echo "================================"

# Get URLs from user
read -p "Enter Render backend URL (e.g., https://aminra-backend.onrender.com): " RENDER_URL
read -p "Enter Vercel frontend URL (e.g., https://aminra-web-ui.vercel.app): " VERCEL_URL

echo ""
echo "Testing Backend: $RENDER_URL"
echo "Testing Frontend: $VERCEL_URL"
echo ""

# Test 1: Backend Health
echo "1. Testing Backend Health..."
if curl -s -f "$RENDER_URL/health" > /dev/null; then
    echo "   ✅ Backend is healthy"
else
    echo "   ❌ Backend health check failed"
    exit 1
fi

# Test 2: Database Connection
echo "2. Testing Database Connection..."
STATS_RESPONSE=$(curl -s "$RENDER_URL/stats")
if echo "$STATS_RESPONSE" | grep -q "status.*green"; then
    VECTORS=$(echo "$STATS_RESPONSE" | grep -o '"vectors":[0-9]*' | cut -d: -f2)
    echo "   ✅ Qdrant connected (vectors: $VECTORS)"
else
    echo "   ❌ Database connection failed"
    echo "   Response: $STATS_RESPONSE"
fi

# Test 3: RAG Pipeline (quick test)
echo "3. Testing RAG Pipeline..."
START_TIME=$(date +%s)
RAG_RESPONSE=$(curl -s -X POST "$RENDER_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{"question":"TCVN 12944 là gì?", "top_k": 2}' \
  -w "\nHTTP_STATUS:%{http_code}" 2>/dev/null)

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

HTTP_STATUS=$(echo "$RAG_RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
RAG_CONTENT=$(echo "$RAG_RESPONSE" | grep -v "HTTP_STATUS:")

if [ "$HTTP_STATUS" = "200" ]; then
    ANSWER_LENGTH=$(echo "$RAG_CONTENT" | jq -r '.answer' | wc -c)
    CHUNKS_USED=$(echo "$RAG_CONTENT" | jq -r '.chunks_used')
    echo "   ✅ RAG working (time: ${DURATION}s, chunks: $CHUNKS_USED, answer length: $ANSWER_LENGTH)"
    
    # Check if answer is meaningful
    if [ "$ANSWER_LENGTH" -lt 100 ]; then
        echo "   ⚠️  Warning: Answer is very short"
    fi
else
    echo "   ❌ RAG test failed (HTTP $HTTP_STATUS)"
    echo "   Response: $RAG_CONTENT"
fi

# Test 4: Frontend Accessibility
echo "4. Testing Frontend Accessibility..."
if curl -s -f "$VERCEL_URL" > /dev/null; then
    echo "   ✅ Frontend is accessible"
else
    echo "   ❌ Frontend not accessible"
fi

# Test 5: Backend Response Time
echo "5. Measuring Response Time..."
for i in {1..3}; do
    TIME_TAKEN=$(curl -s -X POST "$RENDER_URL/chat" \
      -H "Content-Type: application/json" \
      -d '{"question":"Test query '${i}'", "top_k": 1}' \
      -o /dev/null -w "%{time_total}" 2>/dev/null)
    echo "   Query $i: $(printf "%.2f" $TIME_TAKEN)s"
done

echo ""
echo "================================="
echo "🎯 Production Test Summary"
echo ""

# Final recommendations
if [ "$DURATION" -gt 25 ]; then
    echo "⚠️  PERFORMANCE WARNING: Backend response >25s"
    echo "   Recommendations:"
    echo "   1. Reduce TOP_K to 3 in backend .env"
    echo "   2. Upgrade Render to Starter plan ($7/month)"
    echo "   3. Use faster LLM model (deepseek/deepseek-chat)"
fi

if [ ! -z "$VECTORS" ] && [ "$VECTORS" -lt 10 ]; then
    echo "⚠️  DATA WARNING: Only $VECTORS vectors in database"
    echo "   Recommendations:"
    echo "   1. Ingest more TCVN documents"
    echo "   2. Use: curl -X POST $RENDER_URL/ingest -F 'file=@filename.pdf'"
fi

echo ""
echo "✅ Test completed!"
echo "Frontend: $VERCEL_URL"
echo "Backend: $RENDER_URL"
echo ""
echo "Next steps:"
echo "1. Test the chat interface at $VERCEL_URL"
echo "2. Ingest more documents using /ingest endpoint"
echo "3. Monitor logs on Render dashboard"
echo "4. Set up alerts for downtime"