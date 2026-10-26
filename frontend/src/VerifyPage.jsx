import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { API, errorText } from "./api";

async function call(path, options) {
  let res;
  try {
    res = await fetch(`${API}${path}`, options);
  } catch {
    throw new Error("Cannot reach the API. Is the backend running on port 8000?");
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(errorText(data));
  return data;
}

const postJson = (body) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

function Row({ k, v }) {
  return (
    <tr>
      <th>{k}</th>
      <td>{v ?? "-"}</td>
    </tr>
  );
}

export default function VerifyPage() {
  const [apaarId, setApaarId] = useState("");
  const [issued, setIssued] = useState(null);
  const [credId, setCredId] = useState("");
  const [result, setResult] = useState(null);
  const [verifier, setVerifier] = useState("Demo Employer Pvt Ltd");
  const [purpose, setPurpose] = useState("Employment background check");
  const [consent, setConsent] = useState(null);
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");

  async function run(fn) {
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    }
  }

  const issue = () =>
    run(async () => {
      const data = await call(`/credentials/${apaarId.trim()}`, { method: "POST" });
      setIssued(data);
      setCredId(data.credential_id);
      setResult(null);
      setConsent(null);
    });

  const check = (id = credId) =>
    run(async () => {
      setConsent(null);
      setResult(await call(`/verify/${id.trim()}`));
    });

  const requestConsent = () =>
    run(async () => {
      const data = await call(
        "/consent/request",
        postJson({ credential_id: credId.trim(), verifier_name: verifier, purpose })
      );
      setConsent(data);
      setOtp("");
    });

  const approve = () =>
    run(async () => {
      await call(`/consent/${consent.consent_id}/approve`, postJson({ otp }));
      setConsent({ ...consent, status: "approved" });
      setResult(await call(`/verify/${credId.trim()}?consent_id=${consent.consent_id}`));
    });

  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("verify");
    if (id) {
      setCredId(id);
      check(id);
    }
  }, []);

  return (
    <div>
      <h2>Verifiable student records</h2>
      {error && <p className="alert error">{error}</p>}

      <div className="card">
        <h3>1. Issue a signed credential</h3>
        <label>
          Student APAAR ID
          <input value={apaarId} onChange={(e) => setApaarId(e.target.value)} placeholder="12 digits" />
        </label>
        <button onClick={issue}>Issue credential</button>

        {issued && (
          <div className="qr">
            <QRCodeSVG value={`${window.location.origin}/?verify=${issued.credential_id}`} size={140} />
            <div>
              <p>Credential ID</p>
              <p className="mono">{issued.credential_id}</p>
              <p>Signature (HMAC-SHA256)</p>
              <p className="mono">{issued.signature.slice(0, 32)}...</p>
              <p>Scan the QR code to open the verification page.</p>
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <h3>2. Verify a credential</h3>
        <label>
          Credential ID
          <input value={credId} onChange={(e) => setCredId(e.target.value)} />
        </label>
        <button onClick={() => check()}>Verify</button>

        {result && (
          <div>
            <div className="row-between">
              <h3>Result</h3>
              <span className={"badge " + (result.valid ? "ok" : "bad")}>
                {result.valid ? "VALID" : "NOT VALID"}
              </span>
            </div>
            {result.reason && <p className="alert error">{result.reason}</p>}

            {result.signature_valid && (
              <table>
                <tbody>
                  <Row k="Institution" v={result.institution_name} />
                  <Row k="Programme" v={result.programme} />
                  <Row k="Academic year" v={result.academic_year} />
                  <Row k="Current status" v={result.current_status} />
                  <Row k="Issued at" v={result.issued_at} />
                  <Row k="APAAR ID" v={result.details ? result.details.apaar_id : result.apaar_id_masked} />
                  <Row k="Student name" v={result.details ? result.details.student_name : result.student_name_masked} />
                  {result.details && (
                    <>
                      <Row k="Date of birth" v={result.details.dob} />
                      <Row k="Category" v={result.details.category} />
                      <Row k="Nationality" v={result.details.nationality} />
                      <Row k="Shared with" v={result.details.verifier} />
                      <Row k="Purpose" v={result.details.purpose} />
                    </>
                  )}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {result && result.signature_valid && !result.details && (
        <div className="card">
          <h3>3. Request the student's consent for full details</h3>
          <div className="grid">
            <label>
              Verifier name
              <input value={verifier} onChange={(e) => setVerifier(e.target.value)} />
            </label>
            <label>
              Purpose
              <input value={purpose} onChange={(e) => setPurpose(e.target.value)} />
            </label>
          </div>
          <button onClick={requestConsent}>Request consent</button>

          {consent && consent.status === "pending" && (
            <div>
              {consent.demo_otp && (
                <p className="alert warn">
                  Demo mode: the OTP that would be sent to the student's mobile is <b>{consent.demo_otp}</b>
                </p>
              )}
              <label>
                Student enters OTP
                <input value={otp} onChange={(e) => setOtp(e.target.value)} placeholder="6 digits" />
              </label>
              <button onClick={approve}>Approve</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}