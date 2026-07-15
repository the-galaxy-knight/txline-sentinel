import type { ReactNode } from "react";

export function Card({
  title,
  eyebrow,
  children,
  action,
  className = ""
}: {
  title?: string;
  eyebrow?: string;
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel rounded-lg p-5 ${className}`}>
      {(title || eyebrow || action) && (
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            {eyebrow && <p className="mb-1 text-xs uppercase tracking-wide text-muted">{eyebrow}</p>}
            {title && <h2 className="text-lg font-semibold text-white">{title}</h2>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
