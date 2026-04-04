import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { message } = body;

    if (!message) {
      return NextResponse.json(
        { error: 'Message is required' },
        { status: 400 }
      );
    }

    // Simulate processing delay
    await new Promise(resolve => setTimeout(resolve, 1000));

    // Mock response based on message content
    const responses = [
      `I've analyzed your query about "${message}". Based on Halal certification standards, the key requirements are: 1) Ingredients must be Halal, 2) Processing equipment must be purified, 3) No cross-contamination with non-Halal items.`,
      `Regarding "${message}", HDC guidelines state that certification requires documentation from approved Halal bodies. You should check with JAKIM for imported products.`,
      `For "${message}", the LLM suggests consulting the official Halal manual. The answer is derived from our knowledge base of HDC/JAKIM documents.`,
      `Your question about "${message}" is relevant to Halal compliance. Our Qdrant vector database matched it with 3 similar cases; all passed certification after ingredient verification.`,
    ];

    const randomResponse = responses[Math.floor(Math.random() * responses.length)];

    return NextResponse.json({
      reply: randomResponse,
      timestamp: new Date().toISOString(),
      sources: [
        'HDC Halal Certification Manual 2024',
        'JAKIM Halal Standards',
        'Islamic Dietary Guidelines',
      ],
    });
  } catch (error) {
    console.error('Chat API error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}