"use client";

import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

export function useBoqJob(projectId: string) {
  const client = useQueryClient();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (action: () => Promise<unknown>) => {
    setSaving(true); setError(null);
    try {
      const result = await action();
      await client.invalidateQueries({ queryKey: ["boq", projectId] });
      return result;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The BOQ could not be updated.");
      throw reason;
    } finally {
      setSaving(false);
    }
  }, [client, projectId]);

  return { run, saving, error, setError };
}
