import { prisma } from "@/lib/prisma";
import { NextResponse } from "next/server";

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const tokenParam = searchParams.get("token");

    if (!tokenParam) {
      return new NextResponse("<h2>Invalid verification link.</h2>", {
        headers: { "Content-Type": "text/html" },
      });
    }

    const verification = await prisma.loginVerification.findFirst({
      where: {
        token: tokenParam,
        used: false,
        expiresAt: {
          gt: new Date(),
        },
      },
    });

    if (!verification) {
      return new NextResponse(
        "<h2>This trust link is invalid or expired.</h2>",
        { headers: { "Content-Type": "text/html" } }
      );
    }

    await prisma.loginVerification.update({
      where: { id: verification.id },
      data: {
        approved: true,
        trusted: true,
      },
    });

    return new NextResponse(
      `
      <html>
        <body style="font-family: Arial, sans-serif; padding: 40px;">
          <h2>Device Trusted</h2>
          <p>The requested device can now continue to the dashboard.</p>
          <p>That device will also be trusted for future logins.</p>
        </body>
      </html>
      `,
      {
        headers: { "Content-Type": "text/html" },
      }
    );
  } catch (error) {
    console.error("TRUST DEVICE ERROR:", error);
    return new NextResponse("<h2>Trust request failed.</h2>", {
      headers: { "Content-Type": "text/html" },
      status: 500,
    });
  }
}