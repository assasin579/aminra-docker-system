/** Public proxy paths stay compatible while callers share one route definition. */
export const documentApiPath = (suffix = "") => `/api/api/documents${suffix}`;
export const dossierApiPath = (suffix = "") => `/api/dossiers${suffix}`;
