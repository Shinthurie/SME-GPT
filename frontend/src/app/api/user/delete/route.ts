import { prisma } from "@/lib/prisma";
import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { getAuthenticatedUser } from "@/lib/auth-server";

export async function DELETE() {
  try {
    const user = await getAuthenticatedUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    // Cascades to TrustedDevice/LoginVerification/ActivityLog/UploadedFile
    // (all `onDelete: Cascade` in schema.prisma). The backend's own
    // DELETE /user/account call (made in parallel by the caller) owns the
    // tables Prisma can't reach: FinancialDocument/LineItem/ChunkEmbedding/
    // Entity/EntityAlias/DocLink/query_history.
    await prisma.user.delete({ where: { id: user.id } });

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
    console.error("USER DELETE ERROR:", error);
    return NextResponse.json({ error: "Failed to delete account" }, { status: 500 });
  }
}
