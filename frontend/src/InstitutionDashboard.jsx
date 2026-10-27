import { useEffect, useState } from "react";
import { API, apiFetch, errorText, getSession } from "./api";

const LEVEL_CLASS = { LOW: "ok", MEDIUM: "warn", HIGH: "bad" };

export default function InstitutionDashboard() {
  const session = getSession();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null); // { programme, academic_year }
  const [students, setStudents] = useState([]);
  const [notice, setNotice] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch(`${API}/institution/dashboard`);
      const body = await res.json();
      if (!res.ok) throw new Error(errorText(body));
      setData(body);
    } catch (e) {
      setError(e.message || "Cannot load data. Is the backend running on port 8000?");
    } finally {
      setLoading(false);
    }
  }

  async function loadStudents(p) {
    setSelected(p);
    setStudents([]);
    const q = new URLSearchParams({ programme: p.programme, academic_year: p.academic_year });
    const res = await apiFetch(`${API}/institution/admissions?${q}`);
    if (res.ok) setStudents(await res.json());
  }

  async function change(student, body, label) {
    const reason = window.prompt(`Reason for: ${label} (${student.name})`);
    if (!reason) return;
    setNotice("");
    const res = await apiFetch(`${API}/admissions/${student.apaar_id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        institution_code: session.institution_code,
        programme: selected.programme,
        academic_year: selected.academic_year,
        reason,
        ...body,
      }),
    });
    const out = await res.json();
    if (!res.ok) {
      setNotice(errorText(out));
      return;
    }
    setNotice(`Updated: ${label}`);
    await load();
    await loadStudents(selected);
  }

  useEffect(() => {
    load();
  }, []);

  if (loading) return <p>Loading...</p>;
  if (error) return <p className="alert error">{error}</p>;

  const { institution, programmes, risk, recent_activity } = data;
  const excessCount = programmes.filter((p) => p.status === "EXCESS").length;
  const totalEnrolled = programmes.reduce((sum, p) => sum + p.total_enrolled, 0);

  return (
    <div>
      <div className="row-between">
        <h2>{institution.name} <span className="note">({institution.code})</span></h2>
        <button onClick={load}>Refresh</button>
      </div>

      <div className="stats">
        <div className="stat"><div className="num">{programmes.length}</div><div className="lbl">Programmes</div></div>
        <div className="stat"><div className="num">{totalEnrolled}</div><div className="lbl">Students enrolled</div></div>
        <div className={"stat" + (excessCount ? " bad" : "")}><div className="num">{excessCount}</div><div className="lbl">Over intake</div></div>
        {risk && (
          <div className="stat">
            <div className="num">{risk.score}</div>
            <div className="lbl">Risk score <span className={"badge " + LEVEL_CLASS[risk.level]}>{risk.level}</span></div>
          </div>
        )}
      </div>

      {risk && risk.reasons.length > 0 && (
        <div className="card">
          <strong>Items AICTE may review</strong>
          <ul className="reasons">
            {risk.reasons.map((r, i) => <li key={i}>{r.text} <span className="note">(+{r.points})</span></li>)}
          </ul>
          <p className="note">A flag means review, not wrongdoing. Fix data errors from the student list below.</p>
        </div>
      )}

      <h3>Programmes</h3>
      {programmes.length === 0 && <p>No programmes defined yet. AICTE creates programmes and approved intake.</p>}
      {programmes.length > 0 && (
        <table>
          <thead>
            <tr><th>Programme</th><th>Year</th><th>Intake</th><th>Regular</th><th>Supernumerary</th><th>Fill</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {programmes.map((p, i) => {
              const pct = Math.min(100, Math.round((p.regular_enrolled / p.approved_intake) * 100));
              return (
                <tr key={i}>
                  <td>{p.programme}</td><td>{p.academic_year}</td><td>{p.approved_intake}</td>
                  <td>{p.regular_enrolled}</td><td>{p.supernumerary_enrolled}</td>
                  <td><div className="bar"><div className={"fill" + (p.status === "EXCESS" ? " over" : "")} style={{ width: pct + "%" }} /></div></td>
                  <td><span className={"badge " + (p.status === "EXCESS" ? "bad" : "ok")}>{p.status === "EXCESS" ? `EXCESS +${p.excess}` : "OK"}</span></td>
                  <td><button onClick={() => loadStudents(p)}>Students</button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {selected && (
        <div className="card">
          <h3>{selected.programme} {selected.academic_year}: students</h3>
          {notice && <p className={"alert " + (notice.startsWith("Updated") ? "ok" : "error")}>{notice}</p>}
          <table>
            <thead><tr><th>APAAR ID</th><th>Name</th><th>Category</th><th>Seat</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>
              {students.map((s) => (
                <tr key={s.apaar_id}>
                  <td className="mono">{s.apaar_id}</td>
                  <td>{s.name}</td>
                  <td>{s.category || "-"}</td>
                  <td>{s.is_supernumerary ? "Supernumerary" : "Regular"}</td>
                  <td><span className={"badge " + (s.status === "admitted" ? "ok" : "warn")}>{s.status}</span></td>
                  <td className="row-actions">
                    {s.status === "admitted" ? (
                      <>
                        <button onClick={() => change(s, { is_supernumerary: !s.is_supernumerary }, s.is_supernumerary ? "make regular seat" : "make supernumerary")}>
                          {s.is_supernumerary ? "Make regular" : "Make supernumerary"}
                        </button>
                        <button onClick={() => change(s, { status: "withdrawn" }, "withdraw admission")}>Withdraw</button>
                      </>
                    ) : (
                      <button onClick={() => change(s, { status: "admitted" }, "re-admit")}>Re-admit</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="note">Every change asks for a reason and is recorded in the audit log.</p>
        </div>
      )}

      <h3>Recent activity</h3>
      {recent_activity.length === 0 && <p className="note">No activity yet.</p>}
      {recent_activity.length > 0 && (
        <table>
          <thead><tr><th>Time (UTC)</th><th>User</th><th>Action</th><th>Details</th></tr></thead>
          <tbody>
            {recent_activity.map((a, i) => (
              <tr key={i}><td>{(a.time || "").replace("T", " ")}</td><td>{a.actor}</td><td>{a.action}</td><td>{a.details}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
