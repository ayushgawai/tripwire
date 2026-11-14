import { Suspense } from "react";
import PresenterClient from "./PresenterClient";

export const metadata = { title: "Tripwire · Presenter" };

export default function Page() {
  return (
    <Suspense>
      <PresenterClient />
    </Suspense>
  );
}
