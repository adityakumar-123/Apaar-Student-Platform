import { useState } from "react";
import { API, apiFetch, errorText } from "./api";

export default function CertificateDownload({ credentialId }) {
  const [studentIdNo, setStudentIdNo] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function download() {
    setError("");
    setBusy(true);
    try {
      const q = studentIdNo.trim() ? `?student_id_no=${encodeURIComponent(studentIdNo.trim())}` : "";
      const res = await apiFetch(`${API}/credentials/${credentialId}/certificate${q}`);
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(errorText(data));
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `certificate-${credentialId.slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message || "Download failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ marginTop: 16 }}>
      <label>
        Institution's student ID (printed on the certificate, optional)
        <input value={studentIdNo} onChange={(e) => setStudentIdNo(e.target.value)} placeholder="e.g. CSE2025-001" />
      </label>
      <button onClick={download} disabled={busy}>
        {busy ? "Generating..." : "Download certificate (PDF)"}
      </button>
      {error && <p className="alert error">{error}</p>}
    </div>
  );
}