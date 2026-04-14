import { prisma } from "@/lib/prisma";
import { NextResponse } from "next/server";

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

    return NextResponse.json({
      approved: verification.approved,
      trusted: verification.trusted,
      used: verification.used,
    });
  } catch (error) {
    console.error("VERIFICATION STATUS ERROR:", error);
    return NextResponse.json(
      { error: "Failed to check verification status" },
      { status: 500 }
    );
  }
}