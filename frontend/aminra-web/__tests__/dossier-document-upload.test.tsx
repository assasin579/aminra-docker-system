import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import DossierDocumentUpload from "../components/dossiers/DossierDocumentUpload";
beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
it.each([200,409])("uploads within the pinned dossier and handles response %s", async status => {
  vi.mocked(fetch).mockResolvedValue({ ok: status===200, status, json: async () => ({ detail:"Bộ yêu cầu chưa được chốt" }) } as Response);
  const done=vi.fn();render(<DossierDocumentUpload dossierId="own-dossier" token="session" slots={[{doc_type:"manual",required:true}]} onUploaded={done} />);
  const file=new File(["QA evidence"],"qa.txt",{type:"text/plain"});
  fireEvent.change(screen.getByLabelText("Tệp tài liệu"),{target:{files:[file]}});
  fireEvent.submit(screen.getByRole("form",{name:"Bổ sung tài liệu hồ sơ"}));
  await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(1));
  const options=vi.mocked(fetch).mock.calls[0][1]; const body=options?.body as FormData;
  expect(body.get("dossier_id")).toBe("own-dossier");expect(body.get("doc_type")).toBe("manual");expect((body.get("file") as File).name).toBe("qa.txt");
  if(status===200)await waitFor(()=>expect(done).toHaveBeenCalledOnce());
  else {expect(await screen.findByRole("alert")).toHaveTextContent("Bộ yêu cầu chưa được chốt");expect(done).not.toHaveBeenCalled();}
});
