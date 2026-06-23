import { prisma } from "@/lib/prisma";
import bcrypt from "bcryptjs";
import { NextResponse } from "next/server";

export async function POST(req: Request) {
  try {
    const { token, password } = await req.json();

    console.log("RESET TOKEN RECEIVED:", token);

    if (!token || !password) {
      return NextResponse.json(
        { error: "Token and password are required" },
        { status: 400 }
      );
    }

    const user = await prisma.user.findFirst({
      where: {
        resetToken: token,
        resetTokenExpiry: {
          gt: new Date(),
        },
      },
    });

    console.log("RESET USER FOUND:", user?.email);

    if (!user) {
      return NextResponse.json(
        { error: "Invalid or expired token" },
        { status: 400 }
      );
    }

    const hashedPassword = await bcrypt.hash(password, 10);

    await prisma.user.update({
      where: { id: user.id },
      data: {
        password: hashedPassword,
        resetToken: null,
        resetTokenExpiry: null,
        // Invalidate every existing session/JWT (cookie or localStorage) --
        // getAuthenticatedUser() rejects any token whose sessionVersion
        // claim doesn't match the current value. Without this, resetting
        // your password (e.g. because you suspected someone else had
        // access) would leave their session logged in.
        sessionVersion: { increment: 1 },
      },
    });

    console.log("PASSWORD UPDATED FOR:", user.email);

    try {
      await prisma.activityLog.create({
        data: {
          userId: user.id,
          type: "PASSWORD_RESET",
          content: `Password reset for ${user.email}`,
        },
      });
    } catch (logError) {
      console.error("PASSWORD_RESET AUDIT LOG ERROR:", logError);
    }

    return NextResponse.json({
      success: true,
      message: "Password reset successful",
    });
  } catch (error) {
    console.error("RESET PASSWORD ERROR:", error);

    return NextResponse.json(
      { error: "Failed to reset password" },
      { status: 500 }
    );
  }
}