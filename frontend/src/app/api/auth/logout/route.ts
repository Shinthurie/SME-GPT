import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import * as jwt from "jsonwebtoken";
import { prisma } from "@/lib/prisma";

export async function POST() {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get("token")?.value;

    if (token) {
      try {
        const payload = jwt.verify(token, process.env.JWT_SECRET as string) as {
          userId?: string;
        };
        if (payload.userId) {
          await prisma.activityLog.create({
            data: {
              userId: payload.userId,
              type: "LOGOUT",
              content: "User logged out",
            },
          });
        }
      } catch (logError) {
        // Expired/invalid token -- still proceed to clear the cookie, just skip the log.
        console.error("LOGOUT AUDIT LOG ERROR:", logError);
      }
    }

    // Log logout before clearing the token
    const token = cookieStore.get("token")?.value;
    if (token) {
      try {
        const decoded = jwt.verify(token, process.env.JWT_SECRET as string) as { userId: string };
        await prisma.activityLog.create({
          data: { userId: decoded.userId, type: "LOGOUT", content: "User logged out" },
        });
      } catch {
        // expired / invalid token — still proceed with logout
      }
    }

    cookieStore.set("token", "", {
      httpOnly: true,
      expires: new Date(0),
      path: "/",
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("LOGOUT ERROR:", error);
    return NextResponse.json({ error: "Logout failed" }, { status: 500 });
  }
}
