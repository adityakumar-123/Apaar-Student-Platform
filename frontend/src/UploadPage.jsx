import { useState } from "react";
import { API, errorText, apiFetch, getSession } from "./api";

export default function UploadPage() {
  const [institution, setInstitution] = useState(getSession()?.institution_code || "INST001");
  const [programme, setProgramme] = useState("B.Tech CSE");
  const [year, setYear] = useState("2025-26");
  const [dryRun, setDryRun] = useState(true);
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setResult(null);
    if (!file) {
      setError("Please choose a CSV file");
      return;
    }
    const form = new FormData();
    form.append("institution_code", institution);
    form.append("programme", programme);
    form.append("academic_year", year);
    form.append("dry_run", dryRun ? "true" : "false");
    form.append("file", file);

    setLoading(true);
    try {
      const res = await apiFetch(`${API}/admissions/upload`, { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) setError(errorText(data));
      else setResult(data);
    } catch {
      setError("Cannot reach the API. Is the backend running on port 8000?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h2>Upload student admissions</h2>
      <form onSubmit={submit} className="card">
        <div className="grid">
          <label>
            Institution code
            <input value={institution} onChange={(e) => setInstitution(e.target.value)} />
          </label>
          <label>
            Programme
            <input value={programme} onChange={(e) => setProgramme(e.target.value)} />
          </label>
          <label>
            Academic year
            <input value={year} onChange={(e) => setYear(e.target.value)} />
          </label>
        </div>
        <label>
          CSV file
          <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files[0])} />
        </label>
        <label className="check">
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
          Dry run (validate only, do not save)
        </label>
        <button disabled={loading}>{loading ? "Uploading..." : dryRun ? "Validate" : "Upload and save"}</button>
      </form>

      {error && <p className="alert error">{error}</p>}

      {result && (
        <div className="card">
          <h3>{result.dry_run ? "Dry run result" : "Upload result"}</h3>
          <div className="stats">
            <Stat label="Rows" value={result.total_rows} />
            <Stat label="Accepted" value={result.accepted} />
            <Stat label="Rejected" value={result.rejected} bad={result.rejected > 0} />
            <Stat label="Approved intake" value={result.approved_intake} />
            <Stat label="Projected enrolment" value={result.projected_regular_enrolment} />
            <Stat label="Supernumerary" value={result.projected_supernumerary} />
          </div>
          {result.warnings.map((w) => (
            <p key={w} className="alert warn">{w}</p>
          ))}
          {result.errors.length > 0 && (
            <table>
              <thead>
                <tr><th>Row</th><th>APAAR ID</th><th>Problems</th></tr>
              </thead>
              <tbody>
                {result.errors.map((er, i) => (
                  <tr key={i}>
                    <td>{er.row ?? "-"}</td>
                    <td>{er.apaar_id ?? "-"}</td>
                    <td>{er.errors.join("; ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, bad }) {
  return (
    <div className={"stat" + (bad ? " bad" : "")}>
      <div className="num">{value}</div>
      <div className="lbl">{label}</div>
    </div>
  );
}