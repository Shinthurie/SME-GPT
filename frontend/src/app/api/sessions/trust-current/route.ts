import { prisma } from "@/lib/prisma";
import { cookies, headers } from "next/headers";
import { NextResponse } from "next/server";
import { getAuthenticatedUser } from "@/lib/auth-server";
import { getDeviceName } from "@/lib/device";

export async function POST() {
  try {
    const user = await getAuthenticatedUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const cookieStore = await cookies();
    const headersList = await headers();

    const deviceToken = cookieStore.get("device_token")?.value;

    if (!deviceToken) {
      return NextResponse.json(
        { error: "No device token found" },
        { status: 400 }
      );
    }

    const existing = await prisma.trustedDevice.findFirst({
      where: { userId: user.id, deviceToken },
    });

    if (existing) {
      return NextResponse.json({
        success: true,
        message: "Device already trusted",
      });
    }

    const userAgent = headersList.get("user-agent");
    const ipAddress = headersList.get("x-forwarded-for") || "unknown";

    await prisma.trustedDevice.create({
      data: {
        userId: user.id,
        deviceToken,
        deviceName: getDeviceName(userAgent),
        ipAddress,
        userAgent,
      },
    });

    await prisma.activityLog.create({
      data: {
        userId: user.id,
        type: "CURRENT_DEVICE_TRUSTED",
        content: "User trusted current device manually",
      },
    });

    return NextResponse.json({
      success: true,
      message: "Device trusted successfully",
    });
  } catch (error) {
    console.error("TRUST CURRENT DEVICE ERROR:", error);
    return NextResponse.json(
      { error: "Failed to trust device" },
      { status: 500 }
    );
  }
}