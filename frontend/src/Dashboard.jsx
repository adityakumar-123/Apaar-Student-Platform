import { useEffect, useState } from "react";
import { API, apiFetch } from "./api";

export default function Dashboard() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch(`${API}/compliance/intake`);
      if (!res.ok) throw new Error();
      setRows(await res.json());
    } catch {
      setError("Cannot load data. Is the backend running on port 8000?");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const excessCount = rows.filter((r) => r.status === "EXCESS").length;
  const totalEnrolled = rows.reduce((sum, r) => sum + r.total_enrolled, 0);

  return (
    <div>
      <div className="row-between">
        <h2>Intake vs enrolment</h2>
        <button onClick={load}>Refresh</button>
      </div>

      {error && <p className="alert error">{error}</p>}
      {loading && <p>Loading...</p>}

      {!loading && !error && (
        <>
          <div className="stats">
            <div className="stat"><div className="num">{rows.length}</div><div className="lbl">Programmes</div></div>
            <div className="stat"><div className="num">{totalEnrolled}</div><div className="lbl">Students enrolled</div></div>
            <div className={"stat" + (excessCount ? " bad" : "")}>
              <div className="num">{excessCount}</div><div className="lbl">Over intake</div>
            </div>
          </div>

          {rows.length === 0 && <p>No programmes yet. Create one with POST /programmes in the API docs.</p>}

          {rows.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Institution</th><th>Programme</th><th>Year</th>
                  <th>Intake</th><th>Regular</th><th>Supernumerary</th><th>Fill</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const pct = Math.min(100, Math.round((r.regular_enrolled / r.approved_intake) * 100));
                  return (
                    <tr key={i}>
                      <td>{r.institution_code}</td>
                      <td>{r.programme}</td>
                      <td>{r.academic_year}</td>
                      <td>{r.approved_intake}</td>
                      <td>{r.regular_enrolled}</td>
                      <td>{r.supernumerary_enrolled}</td>
                      <td>
                        <div className="bar">
                          <div className={"fill" + (r.status === "EXCESS" ? " over" : "")} style={{ width: pct + "%" }} />
                        </div>
                      </td>
                      <td>
                        <span className={"badge " + (r.status === "EXCESS" ? "bad" : "ok")}>
                          {r.status === "EXCESS" ? `EXCESS +${r.excess}` : "OK"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}