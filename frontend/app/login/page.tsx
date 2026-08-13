"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { appRoutes } from "@/shared/constants/appRoutes";
import { login, register } from "@/features/auth/services/authService";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (!email.trim() || !password) {
      setError("Enter your email and password.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setIsSubmitting(true);

    try {
      if (mode === "login") {
        await login(email, password);
        setSuccessMessage("Signed in successfully. Redirecting to dashboard...");
      } else {
        await register(email, password);
        setSuccessMessage("Account created successfully. Redirecting to dashboard...");
      }

      window.setTimeout(() => {
        router.replace(appRoutes.dashboard);
      }, 1300);
    } catch (authError) {
      setError(authError instanceof Error ? authError.message : "Authentication failed.");
      setIsSubmitting(false);
    }
  }

  return (
    <main
      className="h-screen overflow-y-auto bg-slate-950 px-6 py-10 text-white"
      style={{
        background:
          "radial-gradient(circle at 16% 16%, rgba(59, 130, 246, 0.42), transparent 32%), radial-gradient(circle at 84% 18%, rgba(14, 165, 233, 0.28), transparent 28%), linear-gradient(135deg, #0f172a 0%, #111827 48%, #1e293b 100%)"
      }}
    >
      <section className="mx-auto grid min-h-[calc(100vh-5rem)] max-w-6xl items-center gap-8 lg:grid-cols-[minmax(0,1fr)_420px]">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-blue-200">
            AutoBOQ
          </p>
          <h1 className="mt-5 max-w-3xl text-4xl font-semibold tracking-tight md:text-6xl">
            Connected construction takeoff and BOQ workspace.
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-slate-300">
            Manage projects, drawings, takeoff data, and quantity workflows from one professional workspace.
          </p>

          <div className="mt-8 grid max-w-2xl gap-3 sm:grid-cols-3">
            {[
              ["Drawings", "Connected source documents"],
              ["Floors", "Multi-floor project structure"],
              ["BOQ", "Versioned quantity workflows"]
            ].map(([title, description]) => (
              <div
                key={title}
                className="rounded-2xl border border-white/10 bg-white/8 p-4 shadow-xl shadow-black/10 backdrop-blur"
              >
                <p className="text-sm font-semibold text-white">{title}</p>
                <p className="mt-2 text-xs leading-5 text-slate-300">{description}</p>
              </div>
            ))}
          </div>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-3xl border border-white/10 bg-white p-7 text-ink shadow-2xl shadow-black/30"
        >
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-primary">
              Account Access
            </p>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight">
              {mode === "login" ? "Sign in" : "Create account"}
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted">
              Use your account to access saved AutoBOQ projects.
            </p>
          </div>

          <div className="mt-6 space-y-4">
            <label className="block">
              <span className="text-sm font-medium">Email</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="mt-2 w-full rounded-xl border border-border bg-white px-3 py-3 text-sm outline-none transition focus:border-primary focus:ring-4 focus:ring-blue-100"
                autoComplete="email"
                disabled={isSubmitting}
              />
            </label>

            <label className="block">
              <span className="text-sm font-medium">Password</span>
              <div className="relative mt-2">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="w-full rounded-xl border border-border bg-white px-3 py-3 pr-12 text-sm outline-none transition focus:border-primary focus:ring-4 focus:ring-blue-100"
                  autoComplete={mode === "login" ? "current-password" : "new-password"}
                  disabled={isSubmitting}
                />
                <button
                  type="button"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword((currentValue) => !currentValue)}
                  className="absolute right-3 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={isSubmitting}
                >
                  {showPassword ? (
                    <svg
                      viewBox="0 0 24 24"
                      className="h-5 w-5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <path d="M3 3l18 18" />
                      <path d="M10.58 10.58A2 2 0 0 0 12 14a2 2 0 0 0 1.42-.58" />
                      <path d="M9.88 4.24A9.7 9.7 0 0 1 12 4c5.5 0 9 5 9 8a9.7 9.7 0 0 1-1.67 3.94" />
                      <path d="M6.12 6.12C4.17 7.43 3 9.53 3 12c0 3 3.5 8 9 8a9.7 9.7 0 0 0 4.23-.96" />
                    </svg>
                  ) : (
                    <svg
                      viewBox="0 0 24 24"
                      className="h-5 w-5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <path d="M2.5 12s3.5-7 9.5-7 9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </label>
          </div>

          {error && (
            <div className="mt-4">
              <ErrorMessage message={error} />
            </div>
          )}

          {successMessage && (
            <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
              {successMessage}
            </div>
          )}

          <Button className="mt-6 w-full justify-center rounded-xl py-3" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Please wait" : mode === "login" ? "Sign In" : "Create Account"}
          </Button>

          <a href={appRoutes.forgotPassword} className="mt-4 block text-center text-sm font-medium text-slate-500 transition hover:text-primary">Forgot password</a>

          <button
            type="button"
            className="mt-4 w-full text-center text-sm font-medium text-primary transition hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            onClick={() => {
              setError(null);
              setSuccessMessage(null);
              setShowPassword(false);
              setMode(mode === "login" ? "register" : "login");
            }}
            disabled={isSubmitting}
          >
            {mode === "login" ? "Create a new account" : "Use an existing account"}
          </button>
        </form>
      </section>
    </main>
  );
}