import { Suspense } from "react";
import LoginVerifyClient from "./LoginVerifyClient";

export default function LoginVerifyPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  return (
    <Suspense fallback={<div className="p-6 text-center">Loading...</div>}>
      <LoginVerifyClient searchParams={searchParams} />
    </Suspense>
  );
}