import { useState } from "react";
import UploadPage from "./UploadPage";
import Dashboard from "./Dashboard";
import RiskPanel from "./RiskPanel";
import VerifyPage from "./VerifyPage";
import Login from "./Login";
import { getSession, clearSession } from "./api";

export default function App() {
  const [session, setSession] = useState(getSession());
  const role = session?.role;

  const tabs = [];
  if (role === "institution" || role === "aicte") tabs.push(["upload", "Institution upload"]);
  if (role === "aicte") tabs.push(["dashboard", "AICTE dashboard"]);
  if (role === "aicte") tabs.push(["risk", "Risk scores"]);
  tabs.push(["verify", "Verification"]);

  const [tab, setTab] = useState(() => {
    if (new URLSearchParams(window.location.search).get("verify")) return "verify";
    const s = getSession();
    if (s?.role === "aicte") return "dashboard";
    if (s?.role === "institution") return "upload";
    return "verify";
  });

  const active = tab === "login" && !session ? "login" : tabs.some(([k]) => k === tab) ? tab : "verify";

  function logout() {
    clearSession();
    setSession(null);
    setTab("verify");
  }

  return (
    <div className="app">
      <header>
        <h1>APAAR Student Data Platform</h1>
        <nav>
          {tabs.map(([key, label]) => (
            <button key={key} className={active === key ? "active" : ""} onClick={() => setTab(key)}>
              {label}
            </button>
          ))}
          {session ? (
            <button onClick={logout}>Logout ({session.username})</button>
          ) : (
            <button className={active === "login" ? "active" : ""} onClick={() => setTab("login")}>
              Login
            </button>
          )}
        </nav>
      </header>
      <main>
        {active === "login" && (
          <Login onLogin={(s) => {
            setSession(s);
            setTab(s.role === "aicte" ? "dashboard" : s.role === "institution" ? "upload" : "verify");
          }} />
        )}
        {active === "upload" && <UploadPage />}
        {active === "dashboard" && <Dashboard />}
        {active === "risk" && <RiskPanel />}
        {active === "verify" && <VerifyPage />}
      </main>
    </div>
  );
}