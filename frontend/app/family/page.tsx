import { Suspense } from "react";
import FamilyClient from "./FamilyClient";

export const metadata = { title: "Tripwire · Family" };

export default function Page() {
  return (
    <Suspense>
      <FamilyClient />
    </Suspense>
  );
}
