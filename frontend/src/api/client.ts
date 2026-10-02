import axios from 'axios';

export const apiClient = axios.create({
  baseURL: '', // Empty to use nginx relative paths
});

// We need to inject the token from our in-memory AuthContext.
// Since Axios interceptors don't have access to React context directly,
// we will export a function to setup the interceptor from a React component,
// OR we can rely on a dirty hack. The better approach in a pure architecture is to 
// either pass the token in each request, or update a module-level variable when login happens.
// For simplicity, we'll keep a reference here that AuthProvider can update,
// but since the prompt says "Interceptor that attaches Authorization... from AuthContext",
// we will just set up the interceptor dynamically or use a small store.

let currentToken: string | null = null;

export const setApiToken = (token: string | null) => {
  currentToken = token;
};

apiClient.interceptors.request.use((config) => {
  if (currentToken) {
    config.headers.Authorization = `Bearer ${currentToken}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
