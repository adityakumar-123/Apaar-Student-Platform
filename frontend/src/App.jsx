import { useState } from "react";
import UploadPage from "./UploadPage";
import Dashboard from "./Dashboard";

export default function App() {
  const [tab, setTab] = useState("upload");
  return (
    <div className="app">
      <header>
        <h1>APAAR Student Data Platform</h1>
        <nav>
          <button className={tab === "upload" ? "active" : ""} onClick={() => setTab("upload")}>
            Institution upload
          </button>
          <button className={tab === "dashboard" ? "active" : ""} onClick={() => setTab("dashboard")}>
            AICTE dashboard
          </button>
        </nav>
      </header>
      <main>{tab === "upload" ? <UploadPage /> : <Dashboard />}</main>
    </div>
  );
}