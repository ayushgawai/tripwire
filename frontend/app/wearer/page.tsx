import { Suspense } from "react";
import WearerClient from "./WearerClient";

export const metadata = { title: "Tripwire · Wearer" };

export default function Page() {
  return (
    <Suspense>
      <WearerClient />
    </Suspense>
  );
}
