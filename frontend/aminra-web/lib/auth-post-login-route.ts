type PostLoginProfile = {
  role?: "business" | "provider" | string | null;
  realm_roles?: string[] | null;
};

const DEFAULT_BUSINESS_ROUTE = "/dashboard/business";
const DEFAULT_PROVIDER_ROUTE = "/dashboard/provider";
const DEFAULT_ADMIN_ROUTE = "/admin";

function isSafeRelativePath(path: string | null | undefined): path is string {
  return !!path && path.startsWith("/") && !path.startsWith("//");
}

function hasPlatformAdminRole(profile: PostLoginProfile): boolean {
  return Array.isArray(profile.realm_roles) && profile.realm_roles.includes("platform_admin");
}

function defaultRouteFor(profile: PostLoginProfile): string {
  if (hasPlatformAdminRole(profile)) return DEFAULT_ADMIN_ROUTE;
  if (profile.role === "provider") return DEFAULT_PROVIDER_ROUTE;
  return DEFAULT_BUSINESS_ROUTE;
}

export function resolvePostLoginReturnTo(
  requestedReturnTo: string | null | undefined,
  profile: PostLoginProfile,
): string {
  const fallback = defaultRouteFor(profile);
  if (!isSafeRelativePath(requestedReturnTo)) return fallback;

  if (hasPlatformAdminRole(profile)) {
    if (
      requestedReturnTo.startsWith("/business/login") ||
      requestedReturnTo.startsWith("/dashboard/business") ||
      requestedReturnTo.startsWith("/provider/login") ||
      requestedReturnTo.startsWith("/dashboard/provider")
    ) {
      return DEFAULT_ADMIN_ROUTE;
    }
    return requestedReturnTo;
  }

  if (
    profile.role === "provider" &&
    (requestedReturnTo.startsWith("/business/login") ||
      requestedReturnTo.startsWith("/dashboard/business"))
  ) {
    return DEFAULT_PROVIDER_ROUTE;
  }

  if (
    profile.role === "business" &&
    (requestedReturnTo.startsWith("/provider/login") ||
      requestedReturnTo.startsWith("/dashboard/provider"))
  ) {
    return DEFAULT_BUSINESS_ROUTE;
  }

  return requestedReturnTo;
}
