import { useState } from "react";
import { API, apiFetch, errorText } from "./api";

export default function ReportDownload() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  async function download(path, filename) {
    setError("");
    setBusy(filename);
    try {
      const res = await apiFetch(`${API}${path}`);
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(errorText(data));
      }
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message || "Download failed");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="card">
      <h3>Reports</h3>
      <div className="row-actions">
        <button disabled={!!busy} onClick={() => download("/reports/intake.csv", "intake-report.csv")}>
          {busy === "intake-report.csv" ? "Preparing..." : "Download intake report (CSV)"}
        </button>
        <button disabled={!!busy} onClick={() => download("/reports/risk.csv", "risk-report.csv")}>
          {busy === "risk-report.csv" ? "Preparing..." : "Download risk report (CSV)"}
        </button>
      </div>
      {error && <p className="alert error">{error}</p>}
    </div>
  );
}