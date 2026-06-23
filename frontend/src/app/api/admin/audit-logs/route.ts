import { prisma } from "@/lib/prisma";
import { NextResponse } from "next/server";
import { getAuthenticatedUser } from "@/lib/auth-server";

export async function GET() {
  try {
    const user = await getAuthenticatedUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    if (user.role !== "admin") {
      return NextResponse.json({ error: "Admin role required." }, { status: 403 });
    }

    const logs = await prisma.activityLog.findMany({
      include: { user: { select: { email: true } } },
      take: 200,
      orderBy: { createdAt: "desc" },
    });

    return NextResponse.json({ logs });
  } catch (error) {
    console.error("ADMIN AUDIT LOGS GET ERROR:", error);
    return NextResponse.json({ error: "Failed to load audit logs" }, { status: 500 });
  }
}
