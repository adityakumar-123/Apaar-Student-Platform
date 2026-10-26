import { useEffect, useState } from "react";
import { API, apiFetch } from "./api";

const BADGE = { LOW: "ok", MEDIUM: "warn", HIGH: "bad" };

export default function RiskPanel() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch(`${API}/compliance/risk`);
      if (!res.ok) throw new Error();
      setRows(await res.json());
    } catch {
      setError("Cannot load risk scores. Are you logged in as AICTE and is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div>
      <div className="row-between">
        <h2>Institution risk scores</h2>
        <button onClick={load}>Refresh</button>
      </div>
      <p className="note">
        Scores come from transparent rules (intake excess, supernumerary share, special-category share,
        possible duplicate identities). A flag means "review", not a finding of wrongdoing.
      </p>

      {error && <p className="alert error">{error}</p>}
      {loading && <p>Loading...</p>}

      {!loading && !error && rows.length === 0 && <p>No institutions yet.</p>}

      {!loading &&
        !error &&
        rows.map((r) => (
          <div className="card" key={r.institution_code}>
            <div className="row-between">
              <div>
                <strong>{r.institution_name}</strong> ({r.institution_code}
                {r.state ? `, ${r.state}` : ""})
              </div>
              <span className={"badge " + BADGE[r.level]}>
                {r.level} · {r.score}
              </span>
            </div>
            <div className="bar wide">
              <div className={"fill" + (r.level === "HIGH" ? " over" : "")} style={{ width: r.score + "%" }} />
            </div>
            {r.reasons.length === 0 ? (
              <p className="note">No flags.</p>
            ) : (
              <ul className="reasons">
                {r.reasons.map((x, i) => (
                  <li key={i}>
                    <b>+{x.points}</b> {x.text}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
    </div>
  );
}