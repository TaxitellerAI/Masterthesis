/* eslint-disable @next/next/no-img-element */
"use client";

interface Props {
  /** Rendered pixel height; width follows the official logo's aspect ratio. */
  height?: number;
  className?: string;
}

// Official HFWU wordmark (public/hfwu-logo.png, 3840×1773 → 2.166:1).
// Kept in one component so every placement stays consistent; the .hfwu-logo
// class carries the subtle hover animation defined in globals.css.
const ASPECT = 3840 / 1773;

export default function HfwuLogo({ height = 48, className = "" }: Props) {
  return (
    <img
      src="/hfwu-logo.png"
      alt="Hochschule für Wirtschaft und Umwelt Nürtingen-Geislingen"
      height={height}
      width={Math.round(height * ASPECT)}
      className={`hfwu-logo ${className}`}
      style={{ height, width: "auto" }}
    />
  );
}
