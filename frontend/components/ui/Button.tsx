import type { ButtonHTMLAttributes } from "react";

export function Button({
  children,
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger";
}) {
  const variantClass =
    variant === "primary"
      ? "bg-emerald-400 text-slate-950 hover:bg-emerald-300"
      : variant === "danger"
        ? "bg-rose-500 text-white hover:bg-rose-400"
        : "border border-slate-600 bg-slate-900 text-slate-100 hover:bg-slate-800";
  return (
    <button
      {...props}
      className={`min-h-10 rounded-md px-3 py-2 text-sm font-semibold transition focus-visible:ring-2 focus-visible:ring-emerald-300 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:cursor-not-allowed disabled:opacity-50 ${variantClass} ${className}`}
    >
      {children}
    </button>
  );
}
