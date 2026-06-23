import { prisma } from "@/lib/prisma";
import bcrypt from "bcryptjs";
import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const body = await req.json();
  const { email, password, fullName, companyName } = body;

  const existing = await prisma.user.findUnique({ where: { email } });

  if (existing) {
    return NextResponse.json({ error: "User exists" }, { status: 400 });
  }

  const hashed = await bcrypt.hash(password, 10);

  const user = await prisma.user.create({
    data: {
      email,
      password: hashed,
      fullName,
      companyName,
    },
  });

  try {
    await prisma.activityLog.create({
      data: {
        userId: user.id,
        type: "SIGNUP",
        content: `New account created for ${user.email}`,
      },
    });
  } catch (logError) {
    console.error("SIGNUP AUDIT LOG ERROR:", logError);
  }

  return NextResponse.json({ user });
}