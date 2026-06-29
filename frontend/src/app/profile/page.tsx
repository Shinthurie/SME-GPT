"use client";
// Profile page has been consolidated into /settings
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function ProfilePage() {
  const router = useRouter();
  useEffect(() => { router.replace("/settings"); }, [router]);
  return null;
}
