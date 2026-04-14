import { prisma } from "@/lib/prisma";
import { NextResponse } from "next/server";
import { getAuthenticatedUser } from "@/lib/auth-server";

export async function PUT(req: Request) {
  try {
    const user = await getAuthenticatedUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { enabled } = await req.json();

    const updated = await prisma.user.update({
      where: { id: user.id },
      data: {
        twoFactorEnabled: Boolean(enabled),
      },
      select: {
        twoFactorEnabled: true,
      },
    });

    await prisma.activityLog.create({
      data: {
        userId: user.id,
        type: "TWO_FACTOR_UPDATE",
        content: updated.twoFactorEnabled
          ? "Enabled two-factor authentication"
          : "Disabled two-factor authentication",
      },
    });

    return NextResponse.json({
      success: true,
      twoFactorEnabled: updated.twoFactorEnabled,
    });
  } catch (error) {
    console.error("2FA UPDATE ERROR:", error);
    return NextResponse.json(
      { error: "Failed to update two-factor setting" },
      { status: 500 }
    );
  }
}