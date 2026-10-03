import React from "react";

/** One money convention everywhere: "PKR 125,000" with the currency set small (design `.money`). */
export function formatMinor(amountMinor: number): string {
  // Whole rupees show no decimals; amounts with paisa always show two.
  const digits = amountMinor % 100 === 0 ? 0 : 2;
  return (amountMinor / 100).toLocaleString("en-PK", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

interface MoneyProps {
  amountMinor: number;
  currency?: string;
  className?: string;
  style?: React.CSSProperties;
}

export function Money({ amountMinor, currency = "PKR", className = "", style }: MoneyProps) {
  const negative = amountMinor < 0;
  return (
    <span className={`money${negative ? " neg" : ""} ${className}`.trim()} style={style}>
      <span className="cur">{currency}</span>
      {negative ? "−" : ""}
      {formatMinor(Math.abs(amountMinor))}
    </span>
  );
}
