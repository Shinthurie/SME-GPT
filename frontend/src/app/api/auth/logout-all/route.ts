import { prisma } from "@/lib/prisma";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { getAuthenticatedUser } from "@/lib/auth-server";

export async function POST() {
  try {
    const user = await getAuthenticatedUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    await prisma.user.update({
      where: { id: user.id },
      data: {
        sessionVersion: {
          increment: 1,
        },
      },
    });

    await prisma.activityLog.create({
      data: {
        userId: user.id,
        type: "LOGOUT_ALL",
        content: "User logged out from all devices",
      },
    });

    const cookieStore = await cookies();
    cookieStore.set("token", "", {
      httpOnly: true,
      expires: new Date(0),
      path: "/",
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
    });

    return NextResponse.json({
      success: true,
      message: "Logged out from all devices",
    });
  } catch (error) {
    console.error("LOGOUT ALL ERROR:", error);
    return NextResponse.json(
      { error: "Failed to logout from all devices" },
      { status: 500 }
    );
  }
}