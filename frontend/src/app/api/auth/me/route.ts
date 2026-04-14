import { NextResponse } from "next/server";
import { getAuthenticatedUser } from "@/lib/auth-server";

export async function GET() {
  try {
    const user = await getAuthenticatedUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    return NextResponse.json({
      user: {
        id: user.id,
        email: user.email,
        fullName: user.fullName,
        companyName: user.companyName,
      },
    });
  } catch (error) {
    console.error("ME ERROR:", error);
    return NextResponse.json(
      { error: "Failed to load session" },
      { status: 500 }
    );
  }
}