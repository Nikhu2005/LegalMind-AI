import { useEffect, useState } from "react";
import { AlertCircle, Loader2, Scale } from "lucide-react";

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const MIN_PASSWORD_LENGTH = 8;

const MODES = {
  signup: {
    title: "Create your account",
    subtitle: "Save your research in one place.",
    submitLabel: "Create account",
    busyLabel: "Creating account…",
    endpoint: "/api/auth/signup",
  },
  signin: {
    title: "Sign in",
    subtitle: "Welcome back to LegalMind.",
    submitLabel: "Sign in",
    busyLabel: "Signing in…",
    endpoint: "/api/auth/login",
  },
};

const GOOGLE_ERROR_MESSAGES = {
  state: "Google sign-in expired. Please try again.",
  unverified: "Your Google email is not verified. Use another account.",
  google: "Google sign-in failed. Please try again.",
};

const EMPTY_FORM = { name: "", email: "", password: "", confirmPassword: "" };

function validate(form, mode) {
  const errors = {};

  if (mode === "signup" && !form.name.trim()) {
    errors.name = "Enter your name.";
  }

  if (!EMAIL_PATTERN.test(form.email.trim())) {
    errors.email = "Enter a valid email address.";
  }

  if (mode === "signup" && form.password.length < MIN_PASSWORD_LENGTH) {
    errors.password = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
  }

  if (mode === "signin" && !form.password) {
    errors.password = "Enter your password.";
  }

  if (mode === "signup" && form.confirmPassword !== form.password) {
    errors.confirmPassword = "Passwords do not match.";
  }

  return errors;
}

function requestBody(form, mode) {
  const credentials = { email: form.email.trim(), password: form.password };
  return mode === "signup"
    ? { name: form.name.trim(), ...credentials }
    : credentials;
}

async function readErrorDetail(response) {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail) && data.detail[0]?.msg) return data.detail[0].msg;
  } catch {
    // Non-JSON responses fall through to the generic message below.
  }
  return "Something went wrong. Please try again.";
}

function googleErrorFromUrl() {
  const reason = new URLSearchParams(window.location.search).get("auth_error");
  return GOOGLE_ERROR_MESSAGES[reason] || "";
}

export default function AuthPage({ onAuthenticated }) {
  const [mode, setMode] = useState("signup");
  const [form, setForm] = useState(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState({});
  const [serverError, setServerError] = useState(googleErrorFromUrl);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (window.location.search.includes("auth_error")) {
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  const copy = MODES[mode];

  const switchMode = (nextMode) => {
    setMode(nextMode);
    setFieldErrors({});
    setServerError("");
  };

  const updateField = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    const errors = validate(form, mode);
    setFieldErrors(errors);
    setServerError("");

    if (Object.keys(errors).length > 0) return;

    setIsSubmitting(true);

    try {
      const response = await fetch(copy.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody(form, mode)),
      });

      if (!response.ok) {
        setServerError(await readErrorDetail(response));
        return;
      }

      onAuthenticated(await response.json());
    } catch {
      setServerError("Cannot reach the server. Check that LegalMind is running.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-5 py-10">
      <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-7 flex flex-col items-center text-center">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-700 text-white shadow-md shadow-blue-200">
            <Scale size={24} strokeWidth={2.2} />
          </div>
          <h1 className="text-xl font-semibold text-slate-900">{copy.title}</h1>
          <p className="mt-1 text-sm text-slate-500">{copy.subtitle}</p>
        </div>

        <div className="mb-6 grid grid-cols-2 rounded-xl bg-slate-100 p-1" role="tablist">
          {Object.entries(MODES).map(([key, value]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={mode === key}
              onClick={() => switchMode(key)}
              className={`rounded-lg py-2 text-sm font-semibold transition ${
                mode === key ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"
              }`}
            >
              {value.submitLabel}
            </button>
          ))}
        </div>

        <a
          href="/api/auth/google/login"
          className="flex w-full items-center justify-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
        >
          <GoogleMark />
          Continue with Google
        </a>

        <div className="my-6 flex items-center gap-3 text-xs uppercase tracking-wider text-slate-400">
          <span className="h-px flex-1 bg-slate-200" />
          or with email
          <span className="h-px flex-1 bg-slate-200" />
        </div>

        {serverError && (
          <div
            role="alert"
            className="mb-5 flex items-start gap-2 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            <AlertCircle size={17} className="mt-0.5 shrink-0" />
            <span>{serverError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          {mode === "signup" && (
            <Field
              id="auth-name"
              label="Full name"
              autoComplete="name"
              value={form.name}
              onChange={updateField("name")}
              error={fieldErrors.name}
            />
          )}
          <Field
            id="auth-email"
            label="Email"
            type="email"
            autoComplete="email"
            value={form.email}
            onChange={updateField("email")}
            error={fieldErrors.email}
          />
          <Field
            id="auth-password"
            label="Password"
            type="password"
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
            hint={mode === "signup" ? `At least ${MIN_PASSWORD_LENGTH} characters` : undefined}
            value={form.password}
            onChange={updateField("password")}
            error={fieldErrors.password}
          />
          {mode === "signup" && (
            <Field
              id="auth-confirm"
              label="Confirm password"
              type="password"
              autoComplete="new-password"
              value={form.confirmPassword}
              onChange={updateField("confirmPassword")}
              error={fieldErrors.confirmPassword}
            />
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-2 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blue-700 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting && <Loader2 size={16} className="animate-spin" />}
            {isSubmitting ? copy.busyLabel : copy.submitLabel}
          </button>
        </form>
      </section>
    </div>
  );
}

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.5l6.7-6.7C35.6 2.4 30.2 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.8 6.1C12.3 13.5 17.7 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4 7.1-10 7.1-17.5z" />
      <path fill="#FBBC05" d="M10.4 28.7A14.5 14.5 0 0 1 9.5 24c0-1.6.3-3.2.8-4.7l-7.8-6.1A24 24 0 0 0 0 24c0 3.9.9 7.5 2.6 10.8l7.8-6.1z" />
      <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.8 2.3-8.4 2.3-6.3 0-11.7-4-13.6-9.8l-7.8 6.1C6.5 42.6 14.6 48 24 48z" />
    </svg>
  );
}

function Field({ id, label, hint, error, ...inputProps }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
        className={`w-full rounded-xl border bg-white px-3.5 py-3 text-sm text-slate-800 outline-none transition focus:ring-2 ${
          error
            ? "border-red-300 focus:border-red-500 focus:ring-red-100"
            : "border-slate-200 focus:border-blue-500 focus:ring-blue-100"
        }`}
        {...inputProps}
      />
      {error ? (
        <p id={`${id}-error`} className="mt-1.5 text-xs text-red-600">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className="mt-1.5 text-xs text-slate-400">
            {hint}
          </p>
        )
      )}
    </div>
  );
}
