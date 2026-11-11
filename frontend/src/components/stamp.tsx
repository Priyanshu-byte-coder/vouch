import { STATUS_META, type Status } from "@/lib/types";

/** A rubber-stamp verdict: rotated, double-ruled, slightly uneven ink. */
export function Stamp({
  status,
  size = "md",
  animate = false,
}: {
  status: Status;
  size?: "sm" | "md" | "lg";
  animate?: boolean;
}) {
  const m = STATUS_META[status];
  const sizes = {
    sm: "px-1.5 py-[1px] text-[0.6rem] tracking-[0.14em]",
    md: "px-2 py-0.5 text-[0.68rem] tracking-[0.18em]",
    lg: "px-3 py-1 text-sm tracking-[0.2em]",
  };
  return (
    <span
      className={`stamp inline-block -rotate-3 rounded-[3px] border-2 font-sans font-bold whitespace-nowrap uppercase ${sizes[size]} ${animate ? "stamp-in" : ""}`}
      style={{ color: m.color, borderColor: m.color, boxShadow: `inset 0 0 0 1.5px var(--card), inset 0 0 0 2.5px ${m.color}` }}
      title={m.blurb}
    >
      {m.stamp}
    </span>
  );
}

export function RetractedStamp({ nature }: { nature: string }) {
  const label = nature === "Retraction" ? "Retracted" : nature === "Expression of concern" ? "Concern" : nature;
  return (
    <span
      className="stamp inline-block rotate-2 rounded-[3px] border-2 border-retracted bg-retracted px-2 py-0.5 font-sans text-[0.68rem] font-bold tracking-[0.18em] text-card uppercase"
      title={`${nature} notice in the Retraction Watch database`}
    >
      {label}
    </span>
  );
}
