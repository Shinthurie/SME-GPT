import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export async function POST() {
  try {
    const cookieStore = await cookies();

    cookieStore.set("token", "", {
      httpOnly: true,
      expires: new Date(0),
      path: "/",
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("LOGOUT ERROR:", error);
    return NextResponse.json({ error: "Logout failed" }, { status: 500 });
  }
}