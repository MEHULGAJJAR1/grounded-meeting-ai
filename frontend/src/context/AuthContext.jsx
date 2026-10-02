import { createContext, useContext, useEffect, useState } from "react";
import { api, TOKEN_KEY } from "../services/api";

const AuthContext = createContext(null);
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [configuration, setConfiguration] = useState(null);
  useEffect(() => {
    let active = true;
    async function restore() {
      if (sessionStorage.getItem(TOKEN_KEY)) {
        try {
          const { data } = await api.get("/auth/me");
          if (active) setUser(data);
        } catch {
          sessionStorage.removeItem(TOKEN_KEY);
        }
      }
      if (active) setLoading(false);
    }
    restore();
    const expired = () => {
      setUser(null);
      setConfiguration(null);
    };
    window.addEventListener("grounded-auth-expired", expired);
    return () => {
      active = false;
      window.removeEventListener("grounded-auth-expired", expired);
    };
  }, []);
  useEffect(() => {
    if (user)
      api
        .get("/auth/configuration")
        .then(({ data }) => setConfiguration(data))
        .catch(() => setConfiguration(null));
  }, [user?.id]);
  async function authenticate(path, values) {
    const { data } = await api.post(path, values);
    sessionStorage.setItem(TOKEN_KEY, data.access_token);
    setUser(data.user);
    return data.user;
  }
  async function logout(server = true) {
    try {
      if (server) await api.post("/auth/logout");
    } finally {
      sessionStorage.removeItem(TOKEN_KEY);
      setUser(null);
      setConfiguration(null);
    }
  }
  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        configuration,
        setUser,
        logout,
        login: (values) => authenticate("/auth/login", values),
        register: (values) => authenticate("/auth/register", values),
        demo: () => authenticate("/dev/demo-session", {}),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
export function useAuth() {
  return useContext(AuthContext);
}
