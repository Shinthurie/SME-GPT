import { prisma } from "@/lib/prisma";
import { NextResponse } from "next/server";
import * as jwt from "jsonwebtoken";

export async function POST(req: Request) {
  try {
    const { verificationToken } = await req.json();

    if (!verificationToken) {
      return NextResponse.json(
        { error: "Verification token is required" },
        { status: 400 }
      );
    }

    const verification = await prisma.loginVerification.findUnique({
      where: { token: verificationToken },
      include: { user: true },
    });

    if (!verification) {
      return NextResponse.json(
        { error: "Verification not found" },
        { status: 404 }
      );
    }

    if (verification.expiresAt <= new Date()) {
      return NextResponse.json(
        { error: "Verification expired" },
        { status: 400 }
      );
    }

    if (!verification.approved) {
      return NextResponse.json(
        { error: "Login not approved yet" },
        { status: 400 }
      );
    }

    if (verification.used) {
      return NextResponse.json(
        { error: "Verification already used" },
        { status: 400 }
      );
    }

    const jwtToken = jwt.sign(
      {
        userId: verification.user.id,
        sessionVersion: verification.user.sessionVersion,
      },
      process.env.JWT_SECRET as string,
      { expiresIn: "7d" }
    );

    const response = NextResponse.json({ success: true });

    response.cookies.set("token", jwtToken, {
      httpOnly: true,
      path: "/",
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      maxAge: 60 * 60 * 24 * 7,
    });

    response.cookies.set("device_token", verification.deviceToken, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
    });

    if (verification.trusted) {
      const existingDevice = await prisma.trustedDevice.findFirst({
        where: {
          userId: verification.user.id,
          deviceToken: verification.deviceToken,
        },
      });

      if (!existingDevice) {
        await prisma.trustedDevice.create({
          data: {
            userId: verification.user.id,
            deviceToken: verification.deviceToken,
            deviceName: verification.deviceName,
            ipAddress: verification.ipAddress,
            userAgent: verification.userAgent,
          },
        });
      } else {
        await prisma.trustedDevice.update({
          where: { id: existingDevice.id },
          data: {
            lastUsedAt: new Date(),
          },
        });
      }
    }

    await prisma.loginVerification.update({
      where: { id: verification.id },
      data: { used: true },
    });

    return response;
  } catch (error) {
    console.error("COMPLETE LOGIN ERROR:", error);
    return NextResponse.json(
      { error: "Failed to complete login" },
      { status: 500 }
    );
  }
}