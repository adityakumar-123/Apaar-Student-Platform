import { useState } from "react";
import UploadPage from "./UploadPage";
import Dashboard from "./Dashboard";
import VerifyPage from "./VerifyPage";

export default function App() {
  const [tab, setTab] = useState(() =>
    new URLSearchParams(window.location.search).get("verify") ? "verify" : "upload"
  );
  const tabs = [
    ["upload", "Institution upload"],
    ["dashboard", "AICTE dashboard"],
    ["verify", "Verification"],
  ];
  return (
    <div className="app">
      <header>
        <h1>APAAR Student Data Platform</h1>
        <nav>
          {tabs.map(([key, label]) => (
            <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>
              {label}
            </button>
          ))}
        </nav>
      </header>
      <main>
        {tab === "upload" && <UploadPage />}
        {tab === "dashboard" && <Dashboard />}
        {tab === "verify" && <VerifyPage />}
      </main>
    </div>
  );
}