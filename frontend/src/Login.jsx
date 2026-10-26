import { useState } from "react";
import { API, errorText, saveSession } from "./api";

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API}/auth/login`, {
        method: "POST",
        body: new URLSearchParams({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(errorText(data));
        return;
      }
      const session = {
        token: data.access_token,
        username: data.username,
        role: data.role,
        institution_code: data.institution_code,
      };
      saveSession(session);
      onLogin(session);
    } catch {
      setError("Cannot reach the API. Is the backend running on port 8000?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h2>Login</h2>
      <form onSubmit={submit} className="card">
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        </label>
        <button disabled={loading}>{loading ? "Signing in..." : "Sign in"}</button>
      </form>
      {error && <p className="alert error">{error}</p>}
    </div>
  );
}