import { prisma } from "@/lib/prisma";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { getAuthenticatedUser } from "@/lib/auth-server";

export async function GET() {
  try {
    const user = await getAuthenticatedUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const cookieStore = await cookies();
    const currentDeviceToken = cookieStore.get("device_token")?.value || null;

    const devices = await prisma.trustedDevice.findMany({
      where: { userId: user.id },
      orderBy: { lastUsedAt: "desc" },
      select: {
        id: true,
        deviceToken: true,
        deviceName: true,
        ipAddress: true,
        userAgent: true,
        trustedAt: true,
        lastUsedAt: true,
      },
    });

    const recentUploads = await prisma.uploadedFile.findMany({
  where: { userId: user.id },
  orderBy: { createdAt: "desc" },
  take: 10,
  });
    return NextResponse.json({
      devices,
      currentDeviceToken,
      uploads: recentUploads || [],
    });
  } catch (error) {
    console.error("SESSIONS GET ERROR:", error);
    return NextResponse.json(
      { error: "Failed to load sessions" },
      { status: 500 }
    );
  }
}

export async function DELETE(req: Request) {
  try {
    const user = await getAuthenticatedUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { deviceId } = await req.json();

    if (!deviceId) {
      return NextResponse.json(
        { error: "Device ID is required" },
        { status: 400 }
      );
    }

    const existing = await prisma.trustedDevice.findFirst({
      where: {
        id: deviceId,
        userId: user.id,
      },
    });

    if (!existing) {
      return NextResponse.json(
        { error: "Trusted device not found" },
        { status: 404 }
      );
    }

    await prisma.trustedDevice.delete({
      where: { id: deviceId },
    });

    await prisma.activityLog.create({
      data: {
        userId: user.id,
        type: "TRUSTED_DEVICE_REMOVED",
        content: `Removed trusted device: ${existing.deviceName || existing.id}`,
      },
    });

    return NextResponse.json({
      success: true,
      message: "Trusted device removed",
    });
  } catch (error) {
    console.error("SESSIONS DELETE ERROR:", error);
    return NextResponse.json(
      { error: "Failed to remove trusted device" },
      { status: 500 }
    );
  }
}

export async function POST() {
  try {
    const user = await getAuthenticatedUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const cookieStore = await cookies();
    const currentDeviceToken = cookieStore.get("device_token")?.value || null;

    if (!currentDeviceToken) {
      await prisma.trustedDevice.deleteMany({
        where: { userId: user.id },
      });
    } else {
      await prisma.trustedDevice.deleteMany({
        where: {
          userId: user.id,
          NOT: {
            deviceToken: currentDeviceToken,
          },
        },
      });
    }

    await prisma.activityLog.create({
      data: {
        userId: user.id,
        type: "TRUSTED_DEVICES_CLEARED",
        content: "Removed all other trusted devices",
      },
    });

    return NextResponse.json({
      success: true,
      message: "All other trusted devices removed",
    });
  } catch (error) {
    console.error("SESSIONS POST ERROR:", error);
    return NextResponse.json(
      { error: "Failed to remove other devices" },
      { status: 500 }
    );
  }
}