"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { appRoutes } from "@/shared/constants/appRoutes";
import {
  addManualBoqRow,
  createBoqTemplatePackage,
  downloadBoqExport,
  duplicateBoqTemplatePackage,
  getBoqExports,
  refreshBoq,
  requestBoqExport,
  saveBoqSetup,
  selectBoqTemplate,
  updateBoqRow,
} from "../api";
import { useBoqJob } from "../hooks/useBoqJob";
import { useBoqState } from "../hooks/useBoqState";
import type { BoqExport, BoqRow } from "../types";
import { BoqExportDrawer, type BoqExportMode } from "./BoqExportDrawer";
import { BoqManualItemDrawer, type ManualBoqItemForm } from "./BoqManualItemDrawer";
import { BoqReportTable } from "./BoqReportTable";
import { BoqRowInspector } from "./BoqRowInspector";
import { BoqSettingsDrawer } from "./BoqSettingsDrawer";
import { BoqShell } from "./BoqShell";
import { BoqStatusSummary } from "./BoqStatusSummary";
import { BoqTemplateCreateDialog } from "./BoqTemplateCreateDialog";
import { BoqToolbar } from "./BoqToolbar";

export type BoqPanel = "settings" | "exports" | null;

function sleep(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function rowType(row: BoqRow): string {
  const value = String(row.entity_type || "").toLowerCase();
  if (value.includes("door")) return "door";
  if (value.includes("window")) return "window";
  if (value.includes("wall")) return "wall";
  if (value.includes("floor") || value.includes("room")) return "floor";
  if (row.manual) return "manual";
  return value || "other";
}

export function BoqDashboard({ projectId, initialPanel = null }: { projectId: string; initialPanel?: BoqPanel }) {
  const client = useQueryClient();
  const router = useRouter();
  const [floorId, setFloorId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [elementFilter, setElementFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [panel, setPanel] = useState<BoqPanel>(initialPanel);
  const [manualOpen, setManualOpen] = useState(false);
  const [templateDialogOpen, setTemplateDialogOpen] = useState(false);
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);
  const grouping = "item";
  const query = useBoqState(projectId, floorId, grouping);
  const { run, saving, error, setError } = useBoqJob(projectId);
  const state = query.data;

  useEffect(() => setPanel(initialPanel), [initialPanel]);

  const rows = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return (state?.rows || []).filter((row) => {
      if (elementFilter !== "all" && rowType(row) !== elementFilter) return false;
      if (statusFilter !== "all" && row.status !== statusFilter) return false;
      if (!needle) return true;
      return [row.boq_item_number, row.item_code, row.section, row.description, ...row.floor_names, ...row.source_items.map((item) => item.display_number || item.type_code || "")]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(needle));
    });
  }, [elementFilter, search, state?.rows, statusFilter]);

  const selectedRow = state?.rows.find((row) => row.id === selectedRowId) || null;
  const summary = state?.summary || { rows: 0, ready: 0, needs_review: 0, manual: 0, doors: 0, windows: 0, walls: 0, floors: 0 };
  const totalAmount = Number(state?.report?.summary?.grand_total || 0);

  function closePanel() {
    setPanel(null);
    if (initialPanel) router.replace(appRoutes.workspaceBoq(projectId));
  }

  async function forceRefresh() {
    try {
      await run(() => refreshBoq(projectId, grouping, floorId));
      await query.refetch();
    } catch {
      // useBoqJob exposes the error in the page.
    }
  }

  async function waitForExport(exportRecord: BoqExport): Promise<BoqExport> {
    if (exportRecord.status === "ready" || exportRecord.status === "failed") return exportRecord;
    for (let attempt = 0; attempt < 60; attempt += 1) {
      await sleep(1000);
      const result = await getBoqExports(projectId);
      const next = result.exports.find((item) => item.id === exportRecord.id);
      if (next?.status === "ready" || next?.status === "failed") return next;
    }
    return exportRecord;
  }

  async function createExport(format: "pdf" | "xlsx" | "csv", mode: BoqExportMode, selectedFloorId: string | null) {
    try {
      await run(async () => {
        const result = await requestBoqExport(projectId, format, mode, mode === "selected_floor" ? selectedFloorId : null) as { export: BoqExport };
        const completed = await waitForExport(result.export);
        await query.refetch();
        if (completed.status === "failed") throw new Error(completed.error_message || "The export could not be generated.");
        if (completed.status !== "ready") {
          setPanel("exports");
          return;
        }
        await downloadBoqExport(projectId, completed.id, completed.filename);
      });
    } catch {
      setPanel("exports");
    }
  }

  async function quickExport(format: "pdf" | "xlsx" | "csv") {
    const mode: BoqExportMode = floorId ? "selected_floor" : "combined";
    await createExport(format, mode, floorId);
  }

  async function downloadExisting(item: BoqExport) {
    try {
      await run(() => downloadBoqExport(projectId, item.id, item.filename));
    } catch {
      // useBoqJob displays the error.
    }
  }

  async function createTemplate(name: string, baseTemplateId: string | null) {
    await run(async () => {
      const created = baseTemplateId
        ? await duplicateBoqTemplatePackage(projectId, baseTemplateId, name)
        : await createBoqTemplatePackage(projectId, { name, description: "Custom BOQ template" });
      await selectBoqTemplate(projectId, created.id);
      await query.refetch();
      setTemplateDialogOpen(false);
      router.push(appRoutes.workspaceBoqTemplates(projectId));
    });
  }

  return (
    <BoqShell projectId={projectId}>
      <BoqToolbar
        title={state?.setup.boq_title || "Bill of Quantities"}
        status={state?.stale || state?.active_jobs.length ? "updating" : "ready"}
        templateId={state?.template.id || ""}
        templates={state?.templates || []}
        saving={saving}
        stale={Boolean(state?.stale)}
        onTemplateChange={(templateId) => void run(async () => { await selectBoqTemplate(projectId, templateId); await query.refetch(); }).catch(() => undefined)}
        onAddTemplate={() => { setError(null); setTemplateDialogOpen(true); }}
        onManageTemplates={() => router.push(appRoutes.workspaceBoqTemplates(projectId))}
        onRefresh={() => void forceRefresh()}
        onDownload={(format) => void quickExport(format)}
        onExportHistory={() => { setError(null); setPanel("exports"); }}
        onSettings={() => { setError(null); setPanel("settings"); }}
      />

      <div className="space-y-5 bg-slate-50 p-5 lg:p-6">
        <BoqStatusSummary
          summary={summary}
          totalAmount={totalAmount}
          currency={state?.setup.currency || "Rs"}
          showAmount={Boolean(state?.setup.include_amounts)}
        />
        {error ? <ErrorMessage message={error} /> : null}

        <main className="min-w-0 overflow-hidden rounded-2xl border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-5 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="font-semibold text-slate-950">BOQ items</h3>
              <Button variant="secondary" onClick={() => { setError(null); setManualOpen(true); }}>Add item</Button>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(260px,1fr)_180px_170px_170px]">
              <input className="input" placeholder="Search BOQ" value={search} onChange={(event) => setSearch(event.target.value)} />
              <select className="input" value={floorId || ""} onChange={(event) => setFloorId(event.target.value || null)}>
                <option value="">All floors</option>
                {state?.floors.map((floor) => <option key={floor.id} value={floor.id}>{floor.name}</option>)}
              </select>
              <select className="input" value={elementFilter} onChange={(event) => setElementFilter(event.target.value)}>
                <option value="all">All elements</option>
                <option value="door">Doors ({summary.doors})</option>
                <option value="window">Windows ({summary.windows})</option>
                <option value="wall">Walls ({summary.walls})</option>
                <option value="floor">Floors ({summary.floors})</option>
                <option value="manual">Manual ({summary.manual})</option>
              </select>
              <select className="input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="all">All statuses</option>
                <option value="ready">Ready ({summary.ready})</option>
                <option value="needs_review">Needs Review ({summary.needs_review})</option>
              </select>
            </div>
          </div>

          <BoqReportTable
            rows={rows}
            selectedRowId={selectedRowId}
            showRates={Boolean(state?.setup.include_rates)}
            showAmounts={Boolean(state?.setup.include_amounts)}
            onSelect={(row) => { setError(null); setSelectedRowId(row.id); }}
          />
        </main>

        <div className="flex items-center justify-start rounded-2xl border border-slate-200 bg-white px-5 py-4">
          <Link className="inline-flex h-10 items-center rounded-md border border-slate-200 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50" href={appRoutes.workflowStep(projectId, "review")}>Back to Review</Link>
        </div>
      </div>

      <BoqTemplateCreateDialog
        open={templateDialogOpen}
        templates={state?.templates || []}
        defaultTemplateId={state?.template.id || ""}
        saving={saving}
        onClose={() => setTemplateDialogOpen(false)}
        onCreate={createTemplate}
      />
      <BoqSettingsDrawer
        open={panel === "settings"}
        setup={state?.setup || null}
        saving={saving}
        error={error}
        onClose={closePanel}
        onSave={async (setup) => {
          await run(async () => { await saveBoqSetup(projectId, setup); await query.refetch(); });
          closePanel();
        }}
      />
      <BoqExportDrawer
        open={panel === "exports"}
        floors={state?.floors || []}
        exports={state?.exports || []}
        stale={Boolean(state?.stale)}
        saving={saving}
        error={error}
        onClose={closePanel}
        onCreate={createExport}
        onDownload={downloadExisting}
      />
      <BoqManualItemDrawer
        open={manualOpen}
        saving={saving}
        error={error}
        onClose={() => setManualOpen(false)}
        onAdd={async (form: ManualBoqItemForm) => {
          await run(async () => {
            await addManualBoqRow(projectId, {
              description: form.description.trim(),
              section: form.section.trim() || "Other items",
              item_code: form.item_code.trim() || null,
              quantity: form.quantity,
              unit: form.unit.trim(),
              rate: form.rate === "" ? null : Number(form.rate),
              floor_id: floorId,
            });
            await query.refetch();
          });
          setManualOpen(false);
        }}
      />
      <BoqRowInspector
        row={selectedRow}
        open={Boolean(selectedRow)}
        saving={saving}
        error={error}
        showRates={Boolean(state?.setup.include_rates)}
        showAmounts={Boolean(state?.setup.include_amounts)}
        onClose={() => setSelectedRowId(null)}
        onSave={async (payload) => {
          if (!selectedRow) return;
          await run(async () => {
            await updateBoqRow(projectId, selectedRow.id, payload);
            await client.invalidateQueries({ queryKey: ["boq", projectId] });
            await query.refetch();
          });
          setSelectedRowId(null);
        }}
      />
    </BoqShell>
  );
}
