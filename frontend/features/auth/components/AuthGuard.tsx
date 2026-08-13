"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { appRoutes } from "@/shared/constants/appRoutes";
import { getAuthToken, isLocalDevelopmentSession, loadCurrentUser } from "../services/authService";

let verifiedToken: string | null = null;
let verificationPromise: Promise<unknown> | null = null;

function clearStoredSession() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem("construction_plan_extractor_token");
  window.localStorage.removeItem("construction_plan_extractor_user");
}

export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();

  useEffect(() => {
    if (isLocalDevelopmentSession()) return;

    const token = getAuthToken();
    if (!token) {
      router.replace(appRoutes.login);
      return;
    }

    if (verifiedToken === token) return;
    if (!verificationPromise) {
      verificationPromise = loadCurrentUser()
        .then((user) => {
          verifiedToken = token;
          return user;
        })
        .finally(() => {
          verificationPromise = null;
        });
    }

    verificationPromise.catch(() => {
      if (getAuthToken() === token) {
        verifiedToken = null;
        clearStoredSession();
        router.replace(appRoutes.login);
      }
    });
  }, [router]);

  return <>{children}</>;
}
