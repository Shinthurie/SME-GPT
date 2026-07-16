"use client";

// The AI Assistant chat moved to /query itself (Phase 3 Stage B). This route
// remains only to redirect old links/bookmarks from the Phase 2 location.

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function ChatRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/query");
  }, [router]);
  return null;
}
