/**
 * Tests for the upgraded /verify/[cert_number] page — blockchain anchor card.
 */
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { VerifyContent } from "@/app/verify/[cert_number]/page";

function renderPage(certNumber: string) {
  // Test the inner content component directly — avoids React 19 `use(Promise)`
  // suspension which doesn't always settle cleanly in jsdom.
  return render(<VerifyContent cert_number={certNumber} />);
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});
afterEach(() => {
  vi.unstubAllGlobals();
});

const respond = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

const baseCert = {
  cert_number: "HALAL-2026-0042",
  company_name: "Halal Foods Co",
  provider_name: "Halal Cert Vietnam",
  issue_date: "2026-04-25",
  expiry_date: "2027-04-25",
  status: "active",
  valid: true,
};

describe("VerifyPage — blockchain section", () => {
  test("shows pending message when blockchain.anchored=false", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, {
        ...baseCert,
        blockchain: {
          anchored: false,
          note: "Anchor pending — within 24 hours.",
        },
      }),
    );
    renderPage("HALAL-2026-0042");

    expect(await screen.findByText(/Anchor pending/i)).toBeInTheDocument();
    // No PolygonScan button
    expect(
      screen.queryByText(/Verify on PolygonScan/i),
    ).not.toBeInTheDocument();
  });

  test("shows Polygon badge + tx hash + PolygonScan link when anchored", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, {
        ...baseCert,
        blockchain: {
          anchored: true,
          chain: "polygon",
          merkle_root: "0x" + "4f3a".repeat(16),
          tx_hash: "0x" + "9e7c".repeat(16),
          block_number: 50_123_456,
          anchored_at: "2026-04-25T23:05:00Z",
          explorer_url: "https://polygonscan.com/tx/0x" + "9e7c".repeat(16),
          leaf_hash: "9a7b".repeat(16),
          merkle_proof: [
            { sibling: "1".repeat(64), position: "right" },
            { sibling: "2".repeat(64), position: "left" },
          ],
        },
      }),
    );
    renderPage("HALAL-2026-0042");

    expect(await screen.findByText(/Anchored on Polygon/i)).toBeInTheDocument();
    expect(screen.getByText(/50,123,456/)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Verify on PolygonScan/i });
    expect(link).toHaveAttribute(
      "href",
      "https://polygonscan.com/tx/0x" + "9e7c".repeat(16),
    );
    expect(link).toHaveAttribute("target", "_blank");
  });

  test("shows Bitcoin badge when chain=bitcoin", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, {
        ...baseCert,
        blockchain: {
          anchored: true,
          chain: "bitcoin",
          tx_hash: "abc" + "d".repeat(61),
          block_number: 850_000,
          anchored_at: "2026-05-01T00:00:00Z",
          explorer_url:
            "https://www.blockchain.com/btc/tx/abc" + "d".repeat(61),
        },
      }),
    );
    renderPage("HALAL-2026-0042");

    expect(await screen.findByText(/Anchored on Bitcoin/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Verify on Blockchain.com/i }),
    ).toBeInTheDocument();
  });

  test("proof JSON is collapsed in details by default + has merkle_proof in DOM", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, {
        ...baseCert,
        blockchain: {
          anchored: true,
          chain: "polygon",
          tx_hash: "0xabc",
          block_number: 1,
          merkle_root: "0xroot",
          leaf_hash: "aabbcc",
          merkle_proof: [{ sibling: "sib", position: "right" }],
        },
      }),
    );
    renderPage("HALAL-2026-0042");

    const summary = await screen.findByText(/Merkle proof/i);
    expect(summary).toBeInTheDocument();
    // The details element should be collapsed by default — preview is in DOM but hidden visually
    expect(screen.getByText(/aabbcc/)).toBeInTheDocument();
  });

  test("cert without blockchain field still renders (backwards compat)", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, baseCert), // no blockchain field at all
    );
    renderPage("HALAL-2026-0042");

    expect(await screen.findByText(/Halal Foods Co/)).toBeInTheDocument();
    // Should NOT crash; blockchain section simply absent
    expect(
      screen.queryByText(/Blockchain verification/i),
    ).not.toBeInTheDocument();
  });

  test("revoked cert shows revocation reason banner", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, {
        ...baseCert,
        status: "revoked",
        valid: false,
        revocation: {
          reason: "Vi phạm tiêu chuẩn JAKIM",
          revoked_at: "2026-04-25T10:00:00Z",
        },
      }),
    );
    renderPage("HALAL-2026-0042");

    expect(await screen.findByText(/Lý do thu hồi:/i)).toBeInTheDocument();
    expect(screen.getByText(/Vi phạm tiêu chuẩn JAKIM/)).toBeInTheDocument();
    expect(screen.getByText(/Thu hồi ngày/)).toBeInTheDocument();
  });

  test("non-revoked invalid cert does NOT show revocation banner", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, { ...baseCert, status: "expired", valid: false }),
    );
    renderPage("HALAL-2026-0042");

    await screen.findByText(/Halal Foods Co/);
    expect(screen.queryByText(/Lý do thu hồi:/i)).not.toBeInTheDocument();
  });
});
