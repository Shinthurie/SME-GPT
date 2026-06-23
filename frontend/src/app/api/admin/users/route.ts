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

    const users = await prisma.user.findMany({
      select: { id: true, email: true, fullName: true, role: true, createdAt: true },
      orderBy: { createdAt: "desc" },
    });

    return NextResponse.json({ users });
  } catch (error) {
    console.error("ADMIN USERS GET ERROR:", error);
    return NextResponse.json({ error: "Failed to load users" }, { status: 500 });
  }
}

export async function PUT(req: Request) {
  try {
    const user = await getAuthenticatedUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    if (user.role !== "admin") {
      return NextResponse.json({ error: "Admin role required." }, { status: 403 });
    }

    const { userId, role } = await req.json();
    const allowedRoles = ["owner", "accountant", "admin", "auditor"];

    if (!userId || !allowedRoles.includes(role)) {
      return NextResponse.json({ error: "Invalid userId or role." }, { status: 400 });
    }

    const updated = await prisma.user.update({
      where: { id: userId },
      data: { role },
      select: { id: true, email: true, fullName: true, role: true, createdAt: true },
    });

    try {
      await prisma.activityLog.create({
        data: {
          userId: user.id,
          type: "ADMIN_ROLE_CHANGED",
          content: `Set role of ${updated.email} (${updated.id}) to '${role}'`,
        },
      });
    } catch (logError) {
      console.error("ADMIN_ROLE_CHANGED AUDIT LOG ERROR:", logError);
    }

    return NextResponse.json({ user: updated });
  } catch (error) {
    console.error("ADMIN USERS PUT ERROR:", error);
    return NextResponse.json({ error: "Failed to update user role" }, { status: 500 });
  }
}
