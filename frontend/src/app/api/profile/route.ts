import { prisma } from "@/lib/prisma";
import { NextResponse } from "next/server";
import { getAuthenticatedUser } from "@/lib/auth-server";

export async function GET() {
  try {
    const user = await getAuthenticatedUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const fullUser = await prisma.user.findUnique({
      where: { id: user.id },
      select: {
        id: true,
        fullName: true,
        email: true,
        companyName: true,
        businessUnit: true,
        department: true,
        primaryLanguage: true,
        autoClassify: true,
        twoFactorEnabled: true,
        phone: true,
        jobTitle: true,
        country: true,
      },
    });

    return NextResponse.json({ user: fullUser });
  } catch (error) {
    console.error("PROFILE GET ERROR:", error);
    return NextResponse.json(
      { error: "Failed to load profile" },
      { status: 500 }
    );
  }
}

export async function PUT(req: Request) {
  try {
    const user = await getAuthenticatedUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const body = await req.json();

    const updatedUser = await prisma.user.update({
      where: { id: user.id },
      data: {
        companyName: body.companyName || null,
        businessUnit: body.businessUnit || null,
        department: body.department || null,
        primaryLanguage: body.primaryLanguage || "en",
        autoClassify: Boolean(body.autoClassify),
        phone: body.phone || null,
        jobTitle: body.jobTitle || null,
        country: body.country || null,
      },
      select: {
        id: true,
        fullName: true,
        email: true,
        companyName: true,
        businessUnit: true,
        department: true,
        primaryLanguage: true,
        autoClassify: true,
        twoFactorEnabled: true,
        phone: true,
        jobTitle: true,
        country: true,
      },
    });

    await prisma.activityLog.create({
      data: {
        userId: user.id,
        type: "PROFILE_UPDATE",
        content: "User updated profile settings",
      },
    });

    return NextResponse.json({
      success: true,
      user: updatedUser,
    });
  } catch (error) {
    console.error("PROFILE UPDATE ERROR:", error);
    return NextResponse.json(
      { error: "Failed to update profile" },
      { status: 500 }
    );
  }
}