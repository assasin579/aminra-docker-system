import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    const API_BASE_URL =
      process.env.BACKEND_URL || "http://aminra-backend:8000";
    const formData = await request.formData();
    const file = formData.get("file") as File;

    if (!file) {
      return NextResponse.json({ error: "No file provided" }, { status: 400 });
    }

    // Check file type
    const allowedTypes = [".pdf", ".docx", ".pptx", ".txt", ".md", ".odt"];
    const fileExtension = file.name
      .toLowerCase()
      .slice(file.name.lastIndexOf("."));

    if (!allowedTypes.includes(fileExtension)) {
      return NextResponse.json(
        {
          error: `File type ${fileExtension} not supported. Allowed: ${allowedTypes.join(", ")}`,
        },
        { status: 400 },
      );
    }

    // Forward to backend API
    const backendFormData = new FormData();
    backendFormData.append("file", file);

    // Add doc_type if provided
    const docType = formData.get("doc_type");
    if (docType) {
      backendFormData.append("doc_type", docType as string);
    }

    // Add language
    backendFormData.append("lang", "vi");

    // Forward JWT if present so backend can save to DB
    const headers: Record<string, string> = {};
    const authHeader = request.headers.get("Authorization");
    if (authHeader) headers["Authorization"] = authHeader;

    const response = await fetch(`${API_BASE_URL}/evaluate`, {
      method: "POST",
      headers,
      body: backendFormData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: errorData.detail || "Backend processing failed" },
        { status: response.status },
      );
    }

    const result = await response.json();
    return NextResponse.json(result);
  } catch (error) {
    console.error("Upload API error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 },
    );
  }
}
