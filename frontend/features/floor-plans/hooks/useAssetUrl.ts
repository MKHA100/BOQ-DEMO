"use client";

import { useEffect, useState } from "react";
import { apiRequestHeaders, apiUrl } from "@/shared/services/apiClient";

const assetUrls = new Map<string, string>();
const assetRequests = new Map<string, Promise<string | null>>();

function loadAsset(path: string): Promise<string | null> {
  const saved = assetUrls.get(path);
  if (saved) return Promise.resolve(saved);
  const pending = assetRequests.get(path);
  if (pending) return pending;
  const request = fetch(apiUrl(path), { headers: apiRequestHeaders(), cache: "force-cache" })
    .then(async (response) => {
      if (!response.ok) throw new Error("Asset unavailable");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      assetUrls.set(path, url);
      return url;
    })
    .catch(() => null)
    .finally(() => assetRequests.delete(path));
  assetRequests.set(path, request);
  return request;
}

export function useAssetUrl(path: string | null | undefined): string | null {
  const [url, setUrl] = useState<string | null>(() => path ? assetUrls.get(path) || null : null);

  useEffect(() => {
    let active = true;
    if (!path) { setUrl(null); return () => undefined; }
    const saved = assetUrls.get(path);
    if (saved) { setUrl(saved); return () => { active = false; }; }
    void loadAsset(path).then((next) => { if (active) setUrl(next); });
    return () => { active = false; };
  }, [path]);

  return url;
}
