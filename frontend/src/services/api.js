import axios from "axios";

export const TOKEN_KEY = "grounded_access_token";
export const api = axios.create({ baseURL: "/api", timeout: 240000 });
api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      !["/auth/login", "/auth/register"].includes(error.config?.url)
    ) {
      sessionStorage.removeItem(TOKEN_KEY);
      window.dispatchEvent(new Event("grounded-auth-expired"));
    }
    return Promise.reject(error);
  },
);

export function errorMessage(error) {
  const payload = error.response?.data?.error;
  if (
    payload?.code === "validation_error" &&
    Array.isArray(payload.details) &&
    payload.details.length
  ) {
    return payload.details
      .map(
        (detail) => `${detail.field.replace(/^body\./, "")}: ${detail.message}`,
      )
      .join(" · ");
  }
  if (payload?.message) return payload.message;
  if (error.code === "ECONNABORTED")
    return "The request timed out. Check processing status before trying again.";
  if (!error.response)
    return "Unable to reach the server. Check your connection and try again.";
  return "The request could not be completed. Please try again.";
}

export async function downloadFile(path, fallback) {
  let response;
  try {
    response = await api.get(path, { responseType: "blob" });
  } catch (error) {
    if (error.response?.data instanceof Blob) {
      try {
        error.response.data = JSON.parse(await error.response.data.text());
      } catch {
        /* original HTTP error remains */
      }
    }
    throw error;
  }
  const match = /filename="?([^";]+)"?/.exec(
    response.headers["content-disposition"] || "",
  );
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = match?.[1] || fallback;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      /* fall back when iframe permissions deny Clipboard */
    }
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  const copied = document.execCommand("copy");
  area.remove();
  if (!copied)
    throw new Error(
      "Your browser did not allow clipboard access. Select the text and copy it manually.",
    );
}
