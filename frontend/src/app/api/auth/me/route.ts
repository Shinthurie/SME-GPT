import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { getAuthenticatedUser } from "@/lib/auth-server";

export async function GET() {
  try {
    const user = await getAuthenticatedUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    // The httpOnly `token` cookie is the source of truth for "are you logged
    // in" (checked above via getAuthenticatedUser), but pages also need the
    // raw token in localStorage to call the FastAPI backend directly with a
    // Bearer header. Echo it back here so getSession() can re-sync
    // localStorage whenever the cookie session is valid but localStorage
    // isn't (e.g. the login page auto-redirecting past the login form
    // because a 7-day-old cookie is still valid).
    const cookieStore = await cookies();
    const token = cookieStore.get("token")?.value ?? null;

    return NextResponse.json({
      user: {
        id: user.id,
        email: user.email,
        fullName: user.fullName,
        companyName: user.companyName,
        role: (user as { role?: string }).role ?? "owner",
      },
      token,
    });
  } catch (error) {
    console.error("ME ERROR:", error);
    return NextResponse.json(
      { error: "Failed to load session" },
      { status: 500 }
    );
  }
}