import React, { createContext, useState, ReactNode } from 'react';

// JWT stored IN MEMORY ONLY in React context (not localStorage/sessionStorage).
// Rationale: localStorage is vulnerable to XSS — any injected script can read it.
// In-memory storage means the token is lost on page refresh (user must re-login),
// which is an acceptable trade-off for this academic/internal platform.
// Production systems should use httpOnly cookies set by the server.

interface AuthContextType {
  token: string | null;
  username: string | null;
  login: (token: string, username: string) => void;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState<string | null>(null);

  const login = (newToken: string, newUsername: string) => {
    setToken(newToken);
    setUsername(newUsername);
  };

  const logout = () => {
    setToken(null);
    setUsername(null);
  };

  return (
    <AuthContext.Provider value={{ token, username, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
