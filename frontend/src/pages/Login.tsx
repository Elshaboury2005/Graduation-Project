import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { login as apiLogin } from '../api/system';
import { setApiToken } from '../api/client';

export default function Login() {
  const [username, setUsername] = useState('mohamed');
  const [password, setPassword] = useState('123456');
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      const { access_token } = await apiLogin(username, password);
      // Rationale: JWT is stored IN MEMORY ONLY in AuthContext.
      // localStorage is vulnerable to XSS. Losing token on refresh is an acceptable 
      // trade-off here. In production, use httpOnly cookies.
      // setApiToken updates the module-level Axios interceptor variable so all
      // subsequent API calls include the Authorization: Bearer header.
      setApiToken(access_token);
      login(access_token, username);
      navigate('/');
    } catch {
      setError('Invalid credentials or server error.');
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-slate-800 p-8 rounded-xl border border-slate-700 shadow-xl">
        <h2 className="text-2xl font-bold text-slate-100 text-center mb-6">Platform Login</h2>
        {error && <div className="bg-rose-500/10 border border-rose-500/20 text-rose-400 p-3 rounded mb-4 text-sm">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">Username</label>
            <input
              type="text" required
              className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:border-indigo-500 focus:outline-none"
              value={username} onChange={e => setUsername(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">Password</label>
            <input
              type="password" required
              className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:border-indigo-500 focus:outline-none"
              value={password} onChange={e => setPassword(e.target.value)}
            />
          </div>
          <button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2 rounded transition-colors">
            Sign In
          </button>
        </form>
      </div>
    </div>
  );
}
