// Demo sign-in: one fixed account, prefilled on the sign-in page. This is not security (the credentials
// are in the page itself); real login, with MFA, comes with the platform's auth provider.
export const DEMO_USER = { username: "admin123", password: "1234" };

const KEY = "migryr-signed-in";

export function isSignedIn(): boolean {
  try { return localStorage.getItem(KEY) === "1" || sessionStorage.getItem(KEY) === "1"; } catch { return true; }
}

export function signIn(username: string, password: string, remember: boolean): boolean {
  if (username.trim() !== DEMO_USER.username || password !== DEMO_USER.password) return false;
  try { (remember ? localStorage : sessionStorage).setItem(KEY, "1"); } catch { /* storage blocked: stay signed in for this page */ }
  return true;
}

export function signOut() {
  try { localStorage.removeItem(KEY); sessionStorage.removeItem(KEY); } catch { /* nothing stored */ }
}
