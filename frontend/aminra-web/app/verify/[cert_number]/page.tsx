"use client";

import { use } from "react";
import { VerifyContent } from "./VerifyContent";

export default function VerifyPage({
  params,
}: {
  params: Promise<{ cert_number: string }>;
}) {
  const { cert_number } = use(params);
  return <VerifyContent cert_number={cert_number} />;
}
