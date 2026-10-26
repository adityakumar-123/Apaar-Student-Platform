export const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export function errorText(data) {
  if (!data) return "Request failed";
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join("; ");
  return "Request failed";
}