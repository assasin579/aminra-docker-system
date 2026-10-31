export { DOC_TYPE_LABEL_VI } from "./documentTypes";

export function canEditDossierDocuments(
  user: { role?: string; is_owner?: boolean; permissions?: { can_upload?: boolean } } | null | undefined,
  dossier: { requirements_binding_status: string; status: string } | null,
): boolean {
  return user?.role === "business" && (user.is_owner === true || user.permissions?.can_upload === true)
    && dossier?.requirements_binding_status === "bound"
    && !["cancelled", "cert_issued"].includes(dossier.status);
}
