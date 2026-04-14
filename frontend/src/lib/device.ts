import crypto from "crypto";

export function generateDeviceToken() {
  return crypto.randomBytes(32).toString("hex");
}

export function getDeviceName(userAgent?: string | null) {
  if (!userAgent) return "Unknown Device";

  if (userAgent.includes("Windows")) return "Windows Device";
  if (userAgent.includes("Mac")) return "Mac Device";
  if (userAgent.includes("Android")) return "Android Device";
  if (userAgent.includes("iPhone")) return "iPhone";
  if (userAgent.includes("iPad")) return "iPad";

  return "Browser Device";
}