"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

function tokenFromInput(value: string): string | null {
  const input = value.trim();
  if (!input) return null;

  let candidate = input;
  if (input.startsWith("/q/")) {
    candidate = input.slice(3).replace(/\/$/, "");
  } else if (/^https?:\/\//i.test(input)) {
    try {
      const url = new URL(input);
      const match = url.pathname.match(/^\/q\/([^/]+)\/?$/);
      if (!match) return null;
      candidate = decodeURIComponent(match[1]);
    } catch {
      return null;
    }
  }

  if (candidate.length > 128 || !/^[A-Za-z0-9_-]+$/.test(candidate)) {
    return null;
  }
  return candidate;
}

export default function QrLookupForm() {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [error, setError] = useState("");

  function openProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = tokenFromInput(value);
    if (!token) {
      setError("Enter a valid QR link or code to continue.");
      return;
    }
    setError("");
    router.push(`/q/${encodeURIComponent(token)}`);
  }

  return (
    <form onSubmit={openProduct} className="w-full">
      <label htmlFor="qr-code" className="mb-2 block text-sm font-semibold text-slate-800">
        Enter a QR link or code
      </label>
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          id="qr-code"
          autoComplete="url"
          maxLength={2048}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            if (error) setError("");
          }}
          placeholder="Paste the product QR link or code"
          aria-invalid={Boolean(error)}
          aria-describedby={error ? "qr-code-error" : "qr-code-help"}
          className="min-h-12 min-w-0 flex-1 rounded-xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-[#2b4557] focus:ring-4 focus:ring-[#2b4557]/10"
        />
        <button
          type="submit"
          className="min-h-12 rounded-xl bg-[#243b4a] px-6 text-sm font-semibold text-white transition hover:bg-[#182d3a] focus:outline-none focus:ring-4 focus:ring-[#243b4a]/20"
        >
          Open product
        </button>
      </div>
      {error ? (
        <p id="qr-code-error" role="alert" className="mt-2 text-sm text-rose-700">
          {error}
        </p>
      ) : (
        <p id="qr-code-help" className="mt-2 text-xs leading-5 text-slate-500">
          You can paste the full link printed in your QR code or enter its code.
        </p>
      )}
    </form>
  );
}
