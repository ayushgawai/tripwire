import { Suspense } from "react";
import CallerClient from "./CallerClient";

export const metadata = { title: "Tripwire · Caller" };

export default function Page() {
  return (
    <Suspense>
      <CallerClient />
    </Suspense>
  );
}
